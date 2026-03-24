"""
This is the retriever.

Architecture:
  Stage 1 — Hybrid retrieval (per source collection)
    Dense: ChromaDB similarity search (BGE embeddings)
    Sparse: BM25 keyword search on the same chunks
    Fusion: Reciprocal Rank Fusion (RRF) merges both ranked lists

  Stage 2 — Cross-encoder reranking
    After fusion, a cross-encoder scores each (query, chunk) pair jointly.
    This is more accurate than bi-encoder similarity because the cross-encoder
    sees query and document together, but too slow for first-stage retrieval.
    Uses cross-encoder/ms-marco-MiniLM-L-6-v2 — lightweight, runs on CPU.

  Stage 3 — Relevance grading
    Checks whether the top-ranked chunk is actually relevant to the query.
    If the best reranker score is below a threshold, flags the result as
    low-confidence. The generator can then say "I don't have that information"
    rather than hallucinating from marginally relevant context.

Audience filtering:
  Applied as a metadata soft filter during Stage 1 dense retrieval. If the
  filter is too restrictive (returns < k//2 results), falls back to unfiltered.
  BM25 stage is always unfiltered (keyword relevance is audience-agnostic).
"""

import os
from typing import NamedTuple

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Retrieval config
K_PER_SOURCE = 6          # candidates per source per method (dense + BM25)
TOP_K_AFTER_RERANK = 4    # final chunks returned to the generator per source
RRF_K = 60                # RRF constant — standard default, robust across domains

RELEVANCE_THRESHOLD = -8.0


class RetrievalResult(NamedTuple):
    """Structured return from the retriever for auditability."""
    docs: list[Document]
    is_low_confidence: bool  # True if best chunk scored below threshold
    debug: dict              # scores, rankings, timings — for eval and audit


_embeddings: HuggingFaceEmbeddings | None = None
_reranker = None
_reranker_available: bool | None = None  # None = not checked yet


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings

def get_reranker():
    """
    Load cross-encoder reranker. Returns None if not installed.
    """
    global _reranker, _reranker_available
    if _reranker_available is False:
        return None
    if _reranker is not None:
        return _reranker

    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            max_length=512,
        )
        _reranker_available = True
        return _reranker
    except (ImportError, Exception) as e:
        print(f"[retriever] Cross-encoder not available ({e}). Using RRF-only ranking.")
        _reranker_available = False
        return None

def _dense_search(
    query: str,
    collection_name: str,
    audience: str,
    k: int,
) -> list[tuple[Document, float]]:
    """
    ChromaDB similarity search with optional audience metadata filter.
    """
    embeddings = get_embeddings()
    try:
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )
    except Exception:
        return []

    # Try audience-filtered search first
    docs_with_scores = []
    if audience:
        try:
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=k, filter={"audience": {"$contains": audience}},
            )
        except Exception:
            pass

    # Fallback to unfiltered if too few results
    if len(docs_with_scores) < max(1, k // 2):
        try:
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=k,
            )
        except Exception:
            return []

    return docs_with_scores


def _bm25_search(
    query: str,
    collection_name: str,
    k: int,
) -> list[tuple[Document, float]]:
    """
    BM25 keyword search over all documents in a ChromaDB collection.
    """
    embeddings = get_embeddings()
    try:
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=CHROMA_DIR,
        )
        # Fetch all documents from the collection
        result = vectorstore.get(include=["documents", "metadatas"])
    except Exception:
        return []

    if not result["documents"]:
        return []

    # Build BM25 index
    corpus = result["documents"]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)

    # Score the query
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Build Document objects with scores
    scored_docs = []
    for i, score in enumerate(scores):
        if score > 0:
            doc = Document(
                page_content=corpus[i],
                metadata=result["metadatas"][i] if result["metadatas"] else {},
            )
            scored_docs.append((doc, float(score)))

    # Sort by score descending, return top k
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    return scored_docs[:k]


def _reciprocal_rank_fusion(
    dense_results: list[tuple[Document, float]],
    bm25_results: list[tuple[Document, float]],
    k: int = RRF_K,
) -> list[Document]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.
    """
    # Map doc content → RRF score (using content as dedup key)
    rrf_scores: dict[str, float] = {}
    doc_lookup: dict[str, Document] = {}

    for rank, (doc, _score) in enumerate(dense_results):
        key = doc.page_content[:300]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
        doc_lookup[key] = doc

    for rank, (doc, _score) in enumerate(bm25_results):
        key = doc.page_content[:300]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
        doc_lookup.setdefault(key, doc)

    # Sort by fused score
    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
    return [doc_lookup[k] for k in sorted_keys]


def _rerank(
    query: str,
    docs: list[Document],
    top_k: int = TOP_K_AFTER_RERANK,
) -> list[tuple[Document, float]]:
    """
    Rerank documents using a cross-encoder model.
    """
    reranker = get_reranker()

    if reranker is None or not docs:
        # Fallback: return in RRF order with no scores
        return [(doc, 0.0) for doc in docs[:top_k]]

    # Cross-encoder expects list of [query, passage] pairs
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker.predict(pairs)

    # Cast to Python float — cross-encoder returns numpy floats which
    # serialize as strings in JSON and compare incorrectly with thresholds
    scored = [(doc, float(score)) for doc, score in zip(docs, scores)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

def _check_relevance(
    scored_docs: list[tuple[Document, float]],
    threshold: float = RELEVANCE_THRESHOLD,
) -> bool:
    """
    Check if the top result meets the relevance threshold.
    """
    if not scored_docs:
        return False  # no results = low confidence

    top_score = scored_docs[0][1]

    # If scores are all 0.0, cross-encoder wasn't available — skip grading
    if all(score == 0.0 for _, score in scored_docs):
        return True

    return top_score >= threshold

def retrieve(
    query: str,
    sources: list[str],
    audience: str = "general",
    k_per_source: int = K_PER_SOURCE,
    top_k_final: int = TOP_K_AFTER_RERANK,
    use_reranker: bool = True,
) -> RetrievalResult:
    """
    Run the full 3-stage retrieval pipeline.
    """
    all_candidates: list[Document] = []
    debug = {"stages": {}, "sources_queried": sources}

    # Stage 1: Hybrid retrieval across selected sources
    for source_id in sources:
        collection_name = f"ama_{source_id}"

        dense_results = _dense_search(query, collection_name, audience, k_per_source)
        bm25_results = _bm25_search(query, collection_name, k_per_source)
        fused = _reciprocal_rank_fusion(dense_results, bm25_results)

        debug["stages"][source_id] = {
            "dense_count": len(dense_results),
            "bm25_count": len(bm25_results),
            "fused_count": len(fused),
        }

        all_candidates.extend(fused)

    # Stage 2: Cross-encoder reranking across all candidates
    if use_reranker:
        reranked = _rerank(query, all_candidates, top_k=top_k_final * len(sources))
    else:
        reranked = [(doc, 0.0) for doc in all_candidates[:top_k_final * len(sources)]]
    debug["reranked_count"] = len(reranked)
    debug["reranker_available"] = _reranker_available or False
    debug["top_score"] = reranked[0][1] if reranked else None

    # Stage 3: Relevance grading
    is_confident = _check_relevance(reranked)
    debug["is_low_confidence"] = not is_confident

    # Extract final docs
    final_docs = [doc for doc, _score in reranked]

    return RetrievalResult(
        docs=final_docs,
        is_low_confidence=not is_confident,
        debug=debug,
    )