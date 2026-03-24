"""
This is the evaluation runner.

It runs all evaluation layers and produces a structured report. The layers are:
router, retrieval, generation, adversarial, multi-turn.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chain import ask, AMAResponse
from eval.metrics.routing_evaluator import (
    evaluate_routing, compute_routing_summary, RoutingResult,
)
from eval.metrics.retrieval_evaluator import (
    evaluate_retrieval_single, evaluate_ablation_single,
    compute_retrieval_summary, compute_ablation_summary,
    RetrievalEvalResult, AblationComparison,
)
from eval.metrics.generation_evaluator import (
    evaluate_faithfulness, evaluate_factual_correctness,
    evaluate_answer_quality, compute_generation_summary, GenerationResult,
)
from eval.metrics.adversarial_evaluator import (
    evaluate_adversarial, compute_adversarial_summary, AdversarialResult,
)
from eval.metrics.session_evaluator import (
    evaluate_session, SessionEvalResult,
)

EVAL_DIR = Path(__file__).resolve().parent
DATASETS_DIR = EVAL_DIR / "datasets"
RESULTS_DIR = EVAL_DIR / "results"

def run_routing_eval() -> tuple[list[RoutingResult], dict]:
    """
    Evaluate routing decisions against ground truth.
    Runs each query through the router only (not full pipeline) to isolate
    routing accuracy from retrieval/generation quality.
    """
    with open(DATASETS_DIR / "routing_ground_truth.json") as f:
        test_cases = json.load(f)

    results = []
    for i, tc in enumerate(test_cases):
        query = tc["query"]
        print(f"  [{i+1}/{len(test_cases)}] {query[:60]}...", end=" ", flush=True)

        response = ask(query)

        required = tc.get("required_sources", tc.get("expected_sources", []))
        optional = tc.get("optional_sources", [])

        metrics = evaluate_routing(
            required_sources=required,
            optional_sources=optional,
            actual_sources=response.sources_used,
            expected_audience=tc["expected_audience"],
            actual_audience=response.audience,
        )

        result = RoutingResult(
            query=query,
            required_sources=required,
            optional_sources=optional,
            actual_sources=response.sources_used,
            expected_audience=tc["expected_audience"],
            actual_audience=response.audience,
            full_match=metrics["full_match"],
            required_covered=metrics["required_covered"],
            required_precision=metrics["required_precision"],
            required_recall=metrics["required_recall"],
            overall_precision=metrics["overall_precision"],
            overall_recall=metrics["overall_recall"],
            audience_correct=metrics["audience_correct"],
            off_topic_correct=metrics["off_topic_correct"],
        )
        results.append(result)

        status = "Done."
        print(f"{status} sources={response.sources_used} aud={response.audience}")

    summary = compute_routing_summary(results)
    print(f"\n  Full Match:  {summary['full_match']:.1%}")
    print(f"  Route Required Precision:    {summary['route_required_precision']:.1%}")
    print(f"  Route Overall Precision:     {summary['route_overall_precision']:.1%}")
    print(f"  Route Required Recall:       {summary['route_required_recall']:.1%}")
    print(f"  Route Overall Recall:        {summary['route_overall_recall']:.1%}")
    print(f"  Audience accuracy:  {summary['audience_accuracy']:.1%}")

    return results, summary

def run_retrieval_eval() -> tuple[
    list[RetrievalEvalResult], list[AblationComparison], dict, dict
]:
    """
    Evaluate retrieval quality in isolation from routing and generation.
    Also runs the reranker ablation: same queries with and without the
    cross-encoder, comparing Context Sufficiency, MRR, and latency.
    """
    with open(DATASETS_DIR / "faq_gold_set.json") as f:
        test_cases = json.load(f)

    # With reranker
    results = []
    for i, tc in enumerate(test_cases):
        query = tc["query"]
        expected_facts = tc.get("expected_facts", [])
        expected_sources = tc.get("likely_sources", [])
 
        if not expected_facts or not expected_sources:
            continue
 
        print(f"  [{i+1}/{len(test_cases)}] {query[:55]}...", end=" ", flush=True)
 
        result = evaluate_retrieval_single(
            query=query,
            expected_sources=expected_sources,
            expected_facts=expected_facts,
            use_reranker=True,
        )
        results.append(result)
 
        status = "Done."
        print(f"suff={status} mrr={result.mrr_at_k:.2f} rank={result.first_relevant_rank}")
 
    retrieval_summary = compute_retrieval_summary(results)
    print(f"\n  Avg sufficiency:   {retrieval_summary.get('avg_context_sufficiency', 0):.2f}")
    print(f"  Avg MRR@k:         {retrieval_summary.get('avg_mrr_at_k', 0):.2f}")
    print(f"  Perfect suff rate: {retrieval_summary.get('perfect_sufficiency_rate', 0):.1%}")

    # Without reranker
    ablations = []
    for i, tc in enumerate(test_cases):
        query = tc["query"]
        expected_facts = tc.get("expected_facts", [])
        expected_sources = tc.get("likely_sources", [])
 
        if not expected_facts or not expected_sources:
            continue
 
        print(f"  [{i+1}/{len(test_cases)}] {query[:55]}...", end=" ", flush=True)
 
        comparison = evaluate_ablation_single(
            query=query,
            expected_sources=expected_sources,
            expected_facts=expected_facts,
        )
        ablations.append(comparison)
 
        delta_mrr = comparison.mrr_with - comparison.mrr_without
        delta_sym = "+" if delta_mrr > 0 else ("=" if delta_mrr == 0 else "")
        print(
            f"suff delta={comparison.sufficiency_with - comparison.sufficiency_without:+.2f} "
            f"mrr delta={delta_sym}{delta_mrr:.2f} "
            f"lat +{comparison.latency_with_ms - comparison.latency_without_ms:.0f}ms"
        )
 
    ablation_summary = compute_ablation_summary(ablations)
    print(f"\n  Sufficiency:  with={ablation_summary.get('avg_sufficiency_with_reranker', 0):.2f}"
          f"  without={ablation_summary.get('avg_sufficiency_without_reranker', 0):.2f}"
          f"  Δ={ablation_summary.get('sufficiency_delta', 0):+.3f}")
    print(f"  MRR:          with={ablation_summary.get('avg_mrr_with_reranker', 0):.2f}"
          f"  without={ablation_summary.get('avg_mrr_without_reranker', 0):.2f}"
          f"  Δ={ablation_summary.get('mrr_delta', 0):+.3f}")
    print(f"  Latency overhead: {ablation_summary.get('latency_overhead_ms', 0):+.0f}ms avg")
    print(f"  Reranker helped sufficiency: {ablation_summary.get('reranker_helped_sufficiency_rate', 0):.0%} of queries")
    print(f"  Reranker helped MRR:         {ablation_summary.get('reranker_helped_mrr_rate', 0):.0%} of queries")
 
    return results, ablations, retrieval_summary, ablation_summary

def run_generation_eval() -> tuple[list[GenerationResult], dict]:
    """
    Evaluate answer quality using the FAQ gold set.
    """
    with open(DATASETS_DIR / "faq_gold_set.json") as f:
        test_cases = json.load(f)
 
    results = []
    for i, tc in enumerate(test_cases):
        query = tc["query"]
        print(f"  [{i+1}/{len(test_cases)}] {query[:60]}...", end=" ", flush=True)
 
        response = ask(query)
 
        context_chunks = [doc.page_content for doc in response.retrieved_chunks]
        faithfulness = evaluate_faithfulness(query, response.answer, context_chunks)
 
        factual_score, found, missing = evaluate_factual_correctness(
            response.answer, tc.get("expected_facts", []),
        )
 
        quality_score, quality_reasoning = evaluate_answer_quality(
            query, response.answer, response.audience,
        )
 
        result = GenerationResult(
            query=query,
            answer=response.answer,
            faithfulness_score=faithfulness,
            factual_score=factual_score,
            quality_score=quality_score,
            quality_reasoning=quality_reasoning,
            facts_found=found,
            facts_missing=missing,
            is_low_confidence=response.is_low_confidence,
            latency_ms=response.latency_ms,
        )
        results.append(result)
 
        print(f"faith={faithfulness:.2f} facts={factual_score:.2f} quality={quality_score:.1f}")
 
    summary = compute_generation_summary(results)
    print(f"\n  Avg faithfulness:      {summary['avg_faithfulness']:.2f}")
    print(f"  Avg factual correct:   {summary['avg_factual_correctness']:.2f}")
    print(f"  Avg quality score:     {summary['avg_quality_score']:.1f}/2")
    dist = summary.get("quality_score_distribution", {})
    print(f"  Quality distribution:  Good={dist.get('good',0):.0%}  Acceptable={dist.get('acceptable',0):.0%}  Poor={dist.get('poor',0):.0%}")
    print(f"  Low confidence rate:   {summary['low_confidence_rate']:.1%}")
    print(f"  Avg latency:           {summary['avg_latency_ms']:.0f}ms")
    print(f"  P95 latency:           {summary['p95_latency_ms']:.0f}ms")
 
    return results, summary

def run_adversarial_eval() -> tuple[list[AdversarialResult], dict]:
    """
    Run adversarial test cases — hallucination traps, refusals, edge cases.
    """
    with open(DATASETS_DIR / "adversarial_set.json") as f:
        test_cases = json.load(f)
 
    results = []
    for i, tc in enumerate(test_cases):
        query = tc["query"]
        print(f"  [{i+1}/{len(test_cases)}] {query[:55]}...", end=" ", flush=True)
 
        response = ask(query)
 
        result = evaluate_adversarial(
            query=query,
            answer=response.answer,
            test_type=tc["type"],
            expected_behavior=tc["expected_behavior"],
            is_off_topic=response.is_off_topic,
            notes=tc.get("notes", ""),
        )
        results.append(result)
 
        status = "Done."
        print(f"{status} ({result.test_type})")
 
    summary = compute_adversarial_summary(results)
    print(f"\n  Overall pass rate: {summary['pass_rate']:.1%}")
    for t, info in summary.get("by_type", {}).items():
        print(f"  {t}: {info['pass_rate']:.0%} ({info['count']} tests)")
 
    return results, summary

def run_persona_eval() -> tuple[list[GenerationResult], dict, SessionEvalResult | None]:
    """
    Run a simulated recruiter interview — multi-turn persona script.
    """
    with open(DATASETS_DIR / "recruiter_set.json") as f:
        turns = json.load(f)
 
    results = []
    history: list[tuple[str, str]] = []
 
    for turn in turns:
        query = turn["query"]
        audience_hint = turn.get("audience_hint", "recruiter")
        print(f"  [Turn {turn['turn']}] {query[:55]}...", end=" ", flush=True)
 
        response = ask(query, audience_hint=audience_hint, history=history)
 
        history.append((query, response.answer))
 
        context_chunks = [doc.page_content for doc in response.retrieved_chunks]
        faithfulness = evaluate_faithfulness(query, response.answer, context_chunks)
 
        factual_score, found, missing = evaluate_factual_correctness(
            response.answer, turn.get("expected_facts", []),
        )
 
        quality_score, quality_reasoning = evaluate_answer_quality(
            query, response.answer, response.audience,
        )
 
        result = GenerationResult(
            query=query,
            answer=response.answer,
            faithfulness_score=faithfulness,
            factual_score=factual_score,
            quality_score=quality_score,
            quality_reasoning=quality_reasoning,
            facts_found=found,
            facts_missing=missing,
            is_low_confidence=response.is_low_confidence,
            latency_ms=response.latency_ms,
        )
        results.append(result)
        print(f"faith={faithfulness:.2f} facts={factual_score:.2f} quality={quality_score:.1f}")
 
    summary = compute_generation_summary(results)
    print(f"\n  Per-turn avg faithfulness:  {summary['avg_faithfulness']:.2f}")
    print(f"  Per-turn avg quality:       {summary['avg_quality_score']:.1f}/2")
    print(f"  Per-turn avg latency:       {summary['avg_latency_ms']:.0f}ms")
 
    print(f"\n  --- Session-Level Evaluation ---")
    session_result = evaluate_session(history)
    print(f"  Consistency:  {session_result.consistency.upper()}")
    if session_result.consistency_issues:
        for issue in session_result.consistency_issues:
            print(f"    ↳ {issue}")
    print(f"  Coreference:  {session_result.coreference.upper()}")
    if session_result.coreference_issues:
        for issue in session_result.coreference_issues:
            print(f"    ↳ {issue}")
    print(f"  Completeness: {session_result.completeness.upper()}")
    print(f"  Overall:      {session_result.overall.upper()}")
    print(f"  Reasoning:    {session_result.reasoning}")
 
    summary["session"] = {
        "consistency": session_result.consistency,
        "consistency_issues": session_result.consistency_issues,
        "coreference": session_result.coreference,
        "coreference_issues": session_result.coreference_issues,
        "completeness": session_result.completeness,
        "overall": session_result.overall,
        "reasoning": session_result.reasoning,
    }
 
    return results, summary, session_result

def generate_report(all_results: dict) -> str:
    """Generate a markdown evaluation report."""
    lines = [
        "# AMA Bot — Evaluation Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # Deployment readiness checklist
    lines.append("## Deployment Readiness Checklist")
    lines.append("")
    lines.append("| Metric | Threshold | Actual | Status |")
    lines.append("|--------|-----------|--------|--------|")

    routing = all_results.get("routing_summary", {})
    generation = all_results.get("generation_summary", {})
    adversarial = all_results.get("adversarial_summary", {})

    lines.append("")

    lines.append("## Layer 1: Router Evaluation")
    lines.append("")
    if routing:
        lines.append(f"- **Full Match:** {routing.get('full_match', 0):.1%}")
        lines.append(f"- **Route Precision:** {routing.get('overall_precision', 0):.1%}")
        lines.append(f"- **Route Recall:** {routing.get('overall_recall', 0):.1%}")
        lines.append(f"- **Audience Accuracy:** {routing.get('audience_accuracy', 0):.1%}")
        lines.append(f"- **Off-topic Detection:** {routing.get('off_topic_correct', 0):.0%}")
        lines.append("")
        lines.append("### By Category")
        lines.append("| Category | Count | Exact Match | Precision | Recall |")
        lines.append("|----------|-------|-------------|-----------|--------|")
        for cat, info in routing.get("by_category", {}).items():
            lines.append(
                f"| {cat} | {info['count']} | {info['full_match']:.0%} | "
                f"{info['overall_precision']:.0%} | {info['overall_recall']:.0%} |"
            )
    lines.append("")

    retrieval = all_results.get("retrieval_summary", {})
    ablation = all_results.get("ablation_summary", {})
    lines.append("## Layer 2: Retrieval Evaluation")
    lines.append("")
    if retrieval:
        lines.append(f"- **Avg Context Sufficiency:** {retrieval.get('avg_context_sufficiency', 0):.2f}")
        lines.append(f"- **Avg MRR@k:** {retrieval.get('avg_mrr_at_k', 0):.2f}")
        lines.append(f"- **Perfect Sufficiency Rate:** {retrieval.get('perfect_sufficiency_rate', 0):.1%}")
        lines.append(f"- **Zero Sufficiency Rate:** {retrieval.get('zero_sufficiency_rate', 0):.1%}")
    lines.append("")
    if ablation:
        lines.append("### Reranker Ablation")
        lines.append("")
        lines.append("| Metric | With Reranker | Without Reranker | Delta |")
        lines.append("|--------|---------------|------------------|-------|")
        lines.append(
            f"| Context Sufficiency | {ablation.get('avg_sufficiency_with_reranker', 0):.2f} "
            f"| {ablation.get('avg_sufficiency_without_reranker', 0):.2f} "
            f"| {ablation.get('sufficiency_delta', 0):+.3f} |"
        )
        lines.append(
            f"| MRR@k | {ablation.get('avg_mrr_with_reranker', 0):.2f} "
            f"| {ablation.get('avg_mrr_without_reranker', 0):.2f} "
            f"| {ablation.get('mrr_delta', 0):+.3f} |"
        )
        lines.append(
            f"| Avg Latency | {ablation.get('avg_latency_with_ms', 0):.0f}ms "
            f"| {ablation.get('avg_latency_without_ms', 0):.0f}ms "
            f"| {ablation.get('latency_overhead_ms', 0):+.0f}ms |"
        )
        lines.append("")
        helped_suff = ablation.get('reranker_helped_sufficiency_rate', 0)
        helped_mrr = ablation.get('reranker_helped_mrr_rate', 0)
        lines.append(f"Reranker improved sufficiency on {helped_suff:.0%} of queries "
                      f"and MRR on {helped_mrr:.0%} of queries.")
    lines.append("")

    lines.append("## Layer 2-3: Generation Evaluation")
    lines.append("")
    if generation:
        lines.append(f"- **Avg Faithfulness:** {generation.get('avg_faithfulness', 0):.2f}")
        lines.append(f"- **Avg Factual Correctness:** {generation.get('avg_factual_correctness', 0):.2f}")
        lines.append(f"- **Avg Quality Score:** {generation.get('avg_quality_score', 0):.1f}/5")
        lines.append(f"- **Low Confidence Rate:** {generation.get('low_confidence_rate', 0):.1%}")
    lines.append("")

    lines.append("## Layer 4c: Adversarial Evaluation")
    lines.append("")
    if adversarial:
        lines.append(f"- **Overall Pass Rate:** {adversarial.get('pass_rate', 0):.1%}")
        lines.append("")
        lines.append("| Test Type | Count | Pass Rate |")
        lines.append("|-----------|-------|-----------|")
        for t, info in adversarial.get("by_type", {}).items():
            lines.append(f"| {t} | {info['count']} | {info['pass_rate']:.0%} |")
            for failure in info.get("failures", []):
                lines.append(f"|  ↳ FAIL: {failure['query'][:40]}... | | {failure['reasoning'][:40]}... |")
    lines.append("")

    persona = all_results.get("persona_summary", {})
    lines.append("## Layer 4b: Persona Simulation (Recruiter)")
    lines.append("")
    if persona:
        lines.append(f"- **Avg Faithfulness:** {persona.get('avg_faithfulness', 0):.2f}")
        lines.append(f"- **Avg Quality Score:** {persona.get('avg_quality_score', 0):.1f}/5")
        lines.append(f"- **Avg Latency:** {persona.get('avg_latency_ms', 0):.0f}ms")
    lines.append("")

    # Layer 5
    lines.append("## Layer 5: Non-Functional Metrics")
    lines.append("")
    if generation:
        lines.append(f"- **Avg Latency:** {generation.get('avg_latency_ms', 0):.0f}ms")
        lines.append(f"- **P95 Latency:** {generation.get('p95_latency_ms', 0):.0f}ms")
    lines.append("")

    return "\n".join(lines)

def run_all_evals(layers: list[str] | None = None):
    """Run all evaluation layers and produce reports."""
    all_layers = ["routing", "retrieval", "generation", "adversarial", "persona"]
    targets = layers or all_layers

    t_start = time.perf_counter()
    all_results = {}
    all_detailed = {}

    if "routing" in targets:
        routing_results, routing_summary = run_routing_eval()
        all_results["routing_summary"] = routing_summary
        all_detailed["routing"] = [
            {
                "query": r.query, "required_sources": r.required_sources,
                "optional_sources": r.optional_sources,
                "actual_sources": r.actual_sources, "expected_audience": r.expected_audience,
                "actual_audience": r.actual_audience,
                "full_match": r.full_match, "required_precision": r.required_precision,
                "required_recall": r.required_recall, "overall_precision": r.overall_precision,
                "overall_recall": r.overall_recall, "audience_correct": r.audience_correct,
                "off_topic_correct": r.off_topic_correct
            }
            for r in routing_results
        ]

    if "retrieval" in targets:
        ret_results, ablations, ret_summary, abl_summary = run_retrieval_eval()
        all_results["retrieval_summary"] = ret_summary
        all_results["ablation_summary"] = abl_summary
        all_detailed["retrieval"] = [
            {
                "query": r.query, "sources": r.sources,
                "context_sufficiency": r.context_sufficiency,
                "mrr_at_k": r.mrr_at_k,
                "first_relevant_rank": r.first_relevant_rank,
                "facts_found": r.facts_found_in_context,
                "facts_missing": r.facts_missing_from_context,
                "num_chunks": r.num_chunks_retrieved,
                "latency_ms": r.latency_ms,
            }
            for r in ret_results
        ]
        all_detailed["ablation"] = [
            {
                "query": a.query,
                "sufficiency_with": a.sufficiency_with,
                "sufficiency_without": a.sufficiency_without,
                "mrr_with": a.mrr_with,
                "mrr_without": a.mrr_without,
                "latency_with_ms": a.latency_with_ms,
                "latency_without_ms": a.latency_without_ms,
                "reranker_helped_sufficiency": a.reranker_helped_sufficiency,
                "reranker_helped_mrr": a.reranker_helped_mrr,
            }
            for a in ablations
        ]
    
    if "generation" in targets:
        gen_results, gen_summary = run_generation_eval()
        all_results["generation_summary"] = gen_summary
        all_detailed["generation"] = [
            {
                "query": r.query, "answer": r.answer[:200] + "...",
                "faithfulness": r.faithfulness_score, "factual_score": r.factual_score,
                "quality_score": r.quality_score, "quality_reasoning": r.quality_reasoning,
                "facts_found": r.facts_found, "facts_missing": r.facts_missing,
                "is_low_confidence": r.is_low_confidence, "latency_ms": r.latency_ms,
            }
            for r in gen_results
        ]

    if "adversarial" in targets:
        adv_results, adv_summary = run_adversarial_eval()
        all_results["adversarial_summary"] = adv_summary
        all_detailed["adversarial"] = [
            {
                "query": r.query, "answer": r.answer[:200] + "...",
                "test_type": r.test_type, "expected_behavior": r.expected_behavior,
                "passed": r.passed, "reasoning": r.reasoning,
            }
            for r in adv_results
        ]
    
    if "persona" in targets:
        persona_results, persona_summary, session_result = run_persona_eval()
        all_results["persona_summary"] = persona_summary
        all_detailed["persona"] = [
            {
                "query": r.query, "answer": r.answer[:200] + "...",
                "faithfulness": r.faithfulness_score, "factual_score": r.factual_score,
                "quality_score": r.quality_score, "latency_ms": r.latency_ms,
            }
            for r in persona_results
        ]

    total_time = time.perf_counter() - t_start

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_eval_time_seconds": round(total_time, 1),
        "summaries": all_results,
        "detailed_results": all_detailed,
    }
    with open(RESULTS_DIR / "eval_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    report = generate_report(all_results)
    with open(RESULTS_DIR / "eval_report.md", "w") as f:
        f.write(report)

    print(f"\n{'=' * 60}")
    print(f"Evaluation complete in {total_time:.1f}s")
    print(f"Results: {RESULTS_DIR / 'eval_results.json'}")
    print(f"Report:  {RESULTS_DIR / 'eval_report.md'}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AMA Bot evaluation suite")
    parser.add_argument(
        "--layer",
        choices=["routing", "retrieval", "generation", "persona", "adversarial"],
        help="Run a specific evaluation layer (default: all)",
    )
    args = parser.parse_args()
    run_all_evals(layers=[args.layer] if args.layer else None)