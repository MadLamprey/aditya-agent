"""
This is the evaluator for retrieval.

It evaluates whether the retriever surfaces chunks containing the information
needed to answer a query through these metrics:
  - Context Sufficiency: fraction of expected_facts found in retrieved chunks.
    It's a proxy for RAGAS "Context Recall" but fully deterministic, with no LLM calls.
  - MRR@k (Mean Reciprocal Rank): at what rank position does the first
    chunk containing any expected fact appear?
  - Reranker ablation: runs retrieval with and without the cross-encoder
    reranker on the same queries, comparing sufficiency, MRR, and latency.
    This validates whether the reranker earns its latency cost on our corpus.
"""

import time
from dataclasses import dataclass, field

from src.retriever import retrieve, RetrievalResult

@dataclass
class RetrievalEvalResult:
    """Result for a single retrieval evaluation query."""
    query: str
    sources: list[str]
    expected_facts: list[str]
    use_reranker: bool

    context_sufficiency: float      # 0-1: fraction of facts found in chunks
    mrr_at_k: float                 # 0-1: reciprocal rank of first relevant chunk
    facts_found_in_context: list[str]
    facts_missing_from_context: list[str]
    first_relevant_rank: int | None  # 1-indexed rank, None if no relevant chunk
    num_chunks_retrieved: int
    latency_ms: float

    chunk_previews: list[str] = field(default_factory=list)


@dataclass
class AblationComparison:
    """For side-by-side comparison of retrieval with and without reranker."""
    query: str
    sufficiency_with: float
    sufficiency_without: float
    mrr_with: float
    mrr_without: float
    latency_with_ms: float
    latency_without_ms: float
    reranker_helped_sufficiency: bool
    reranker_helped_mrr: bool

def context_sufficiency(
    chunks: list[str],
    expected_facts: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Fraction of expected facts present in the retrieved chunks.
    """
    if not expected_facts:
        return 1.0, [], []

    context_text = " ".join(chunks).lower() # case-insensitive matching
    found = [f for f in expected_facts if f.lower() in context_text]
    missing = [f for f in expected_facts if f.lower() not in context_text]
    score = len(found) / len(expected_facts)
    return score, found, missing


def mrr_at_k(
    chunks: list[str],
    expected_facts: list[str],
    k: int = 5,
) -> tuple[float, int | None]:
    """
    Mean Reciprocal Rank: reciprocal of the rank of the first chunk
    containing any expected fact.
    """
    if not expected_facts:
        return 1.0, None

    for i, chunk in enumerate(chunks[:k]):
        chunk_lower = chunk.lower()
        if any(f.lower() in chunk_lower for f in expected_facts):
            return 1.0 / (i + 1), i + 1

    return 0.0, None

def evaluate_retrieval_single(
    query: str,
    expected_sources: list[str],
    expected_facts: list[str],
    use_reranker: bool = True,
    k: int = 5,
) -> RetrievalEvalResult:
    """
    Evaluate retrieval quality for a single query.
    """
    t0 = time.perf_counter()
    result = retrieve(
        query=query,
        sources=expected_sources,
        audience="general",
        use_reranker=use_reranker,
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    chunk_texts = [doc.page_content for doc in result.docs]

    suff_score, found, missing = context_sufficiency(chunk_texts, expected_facts)
    mrr_score, first_rank = mrr_at_k(chunk_texts, expected_facts, k=k)

    return RetrievalEvalResult(
        query=query,
        sources=expected_sources,
        expected_facts=expected_facts,
        use_reranker=use_reranker,
        context_sufficiency=suff_score,
        mrr_at_k=mrr_score,
        facts_found_in_context=found,
        facts_missing_from_context=missing,
        first_relevant_rank=first_rank,
        num_chunks_retrieved=len(chunk_texts),
        latency_ms=latency_ms,
        chunk_previews=[c[:120] + "..." for c in chunk_texts[:5]],
    )

def evaluate_ablation_single(
    query: str,
    expected_sources: list[str],
    expected_facts: list[str],
) -> AblationComparison:
    """
    Run retrieval with and without the reranker on the same query.
    """
    result_with = evaluate_retrieval_single(
        query, expected_sources, expected_facts, use_reranker=True,
    )
    result_without = evaluate_retrieval_single(
        query, expected_sources, expected_facts, use_reranker=False,
    )

    return AblationComparison(
        query=query,
        sufficiency_with=result_with.context_sufficiency,
        sufficiency_without=result_without.context_sufficiency,
        mrr_with=result_with.mrr_at_k,
        mrr_without=result_without.mrr_at_k,
        latency_with_ms=result_with.latency_ms,
        latency_without_ms=result_without.latency_ms,
        reranker_helped_sufficiency=(
            result_with.context_sufficiency > result_without.context_sufficiency
        ),
        reranker_helped_mrr=(
            result_with.mrr_at_k > result_without.mrr_at_k
        ),
    )

def compute_retrieval_summary(results: list[RetrievalEvalResult]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    latencies = sorted(r.latency_ms for r in results)

    return {
        "total_queries": n,
        "avg_context_sufficiency": sum(r.context_sufficiency for r in results) / n,
        "avg_mrr_at_k": sum(r.mrr_at_k for r in results) / n,
        "perfect_sufficiency_rate": sum(
            1 for r in results if r.context_sufficiency == 1.0
        ) / n,
        "zero_sufficiency_rate": sum(
            1 for r in results if r.context_sufficiency == 0.0
        ) / n,
        "avg_latency_ms": sum(r.latency_ms for r in results) / n,
        "p95_latency_ms": latencies[int(n * 0.95)] if n > 1 else latencies[0],
    }


def compute_ablation_summary(comparisons: list[AblationComparison]) -> dict:
    n = len(comparisons)
    if n == 0:
        return {}

    return {
        "total_queries": n,

        "avg_sufficiency_with_reranker": sum(
            c.sufficiency_with for c in comparisons
        ) / n,
        "avg_sufficiency_without_reranker": sum(
            c.sufficiency_without for c in comparisons
        ) / n,
        "sufficiency_delta": sum(
            c.sufficiency_with - c.sufficiency_without for c in comparisons
        ) / n,
        "reranker_helped_sufficiency_rate": sum(
            c.reranker_helped_sufficiency for c in comparisons
        ) / n,

        "avg_mrr_with_reranker": sum(c.mrr_with for c in comparisons) / n,
        "avg_mrr_without_reranker": sum(c.mrr_without for c in comparisons) / n,
        "mrr_delta": sum(c.mrr_with - c.mrr_without for c in comparisons) / n,
        "reranker_helped_mrr_rate": sum(
            c.reranker_helped_mrr for c in comparisons
        ) / n,

        "avg_latency_with_ms": sum(c.latency_with_ms for c in comparisons) / n,
        "avg_latency_without_ms": sum(
            c.latency_without_ms for c in comparisons
        ) / n,
        "latency_overhead_ms": sum(
            c.latency_with_ms - c.latency_without_ms for c in comparisons
        ) / n,
    }