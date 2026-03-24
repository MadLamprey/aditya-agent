"""
This is the evaluator for routing.

It measures whether the routing agent selects appropriate sources and audience.

Dataset format:
  - query
  - required_sources
  - optional_sources
  - expected_audience

The metrics are:
  - Required covered: were all required sources selected?
  - Required Precision: of the sources selected, how many were in required sources?
  - Required Recall: of the required sources, how many were selected?
  - Overall Precision: of the sources selected, how many were in required or optional sources?
  - Overall Recall: of the required + optional sources, how many were selected?
  - Full match: did the router pick exactly the union of required and optional sources?
    This is diagnostic only and not the main metric.
  - Audience accuracy: did the router infer the correct audience?
  - Off-topic detection: for queries with no required or optional sources,
    did it correctly return empty sources?
"""

from dataclasses import dataclass

@dataclass
class RoutingResult:
    """Result for a single routing evaluation."""
    query: str
    required_sources: list[str]
    optional_sources: list[str]
    actual_sources: list[str]
    expected_audience: str
    actual_audience: str
    full_match: bool
    required_covered: bool
    required_precision: float
    required_recall: float
    overall_precision: float
    overall_recall: float
    audience_correct: bool
    off_topic_correct: bool


def evaluate_routing(
    required_sources: list[str],
    optional_sources: list[str],
    actual_sources: list[str],
    expected_audience: str,
    actual_audience: str,
) -> dict:
    """
    Evaluate a single routing decision.
    """
    required_set = set(required_sources)
    optional_set = set(optional_sources)
    valid_set = required_set | optional_set
    actual_set = set(actual_sources)

    is_off_topic = len(valid_set) == 0
    off_topic_correct = is_off_topic and len(actual_set) == 0

    # Off-topic
    if is_off_topic:
        return {
            "full_match": len(actual_set) == 0,
            "required_covered": True,
            "required_precision": 1.0 if len(actual_set) == 0 else 0.0,
            "required_recall": 1.0,
            "overall_precision": 1.0 if len(actual_set) == 0 else 0.0,
            "overall_recall": 1.0,
            "audience_correct": expected_audience == actual_audience,
            "off_topic_correct": off_topic_correct,
        }

    required_precision = len(actual_set & required_set) / len(actual_set) if actual_set else 1.0
    overall_precision = len(actual_set & valid_set) / len(actual_set) if actual_set else 1.0

    required_recall = len(actual_set & required_set) / len(required_set) if required_set else 1.0
    overall_recall = len(actual_set & valid_set) / len(valid_set) if valid_set else 1.0

    required_covered = required_set.issubset(actual_set)

    full_match = actual_set == valid_set

    return {
        "full_match": full_match,
        "required_covered": required_covered,
        "required_precision": required_precision,
        "required_recall": required_recall,
        "overall_precision": overall_precision,
        "overall_recall": overall_recall,
        "audience_correct": expected_audience == actual_audience,
        "off_topic_correct": off_topic_correct,
    }

def compute_routing_summary(results: list[RoutingResult]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    off_topic_count = sum(
        1
        for r in results
        if len(r.required_sources) == 0 and len(r.optional_sources) == 0
    )

    return {
        "total_queries": n,
        "required_coverage_rate": sum(r.required_covered for r in results) / n,
        "route_required_precision": sum(r.required_precision for r in results) / n,
        "route_overall_precision": sum(r.overall_precision for r in results) / n,
        "route_required_recall": sum(r.required_recall for r in results) / n,
        "route_overall_recall": sum(r.overall_recall for r in results) / n,
        "audience_accuracy": sum(r.audience_correct for r in results) / n,
        "full_match": sum(r.full_match for r in results) / n,
        "off_topic_correct": (
            sum(r.off_topic_correct for r in results
                if len(r.required_sources) == 0 and len(r.optional_sources) == 0)
            / max(1, off_topic_count)
        )
    }