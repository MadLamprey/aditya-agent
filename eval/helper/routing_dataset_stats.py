"""
This script computes statistics about the routing evaluation dataset (routing_ground_truth.json).
"""

import json
from collections import Counter

def compute_stats(data_path: str) -> dict:
    with open(data_path, "r") as f:
        data = json.load(f)

    stats = {
        "total_data_points": len(data),
        "audience_counts": Counter(),
        "source_counts": {source: {"required": 0, "optional": 0, "total": 0} for source in ["resume", "linkedin", "github", "blog", "values"]},
        "off_topic_count": 0,
    }

    for item in data:
        expected_audience = item.get("expected_audience", "")
        stats["audience_counts"][expected_audience] += 1

        required_sources = set(item.get("required_sources", []))
        optional_sources = set(item.get("optional_sources", []))

        if not required_sources and not optional_sources:
            stats["off_topic_count"] += 1

        for source in ["resume", "linkedin", "github", "blog", "values"]:
            if source in required_sources:
                stats["source_counts"][source]["required"] += 1
            if source in optional_sources:
                stats["source_counts"][source]["optional"] += 1
    
    for source, counts in stats["source_counts"].items():
        counts["total"] = counts["required"] + counts["optional"]

    return stats

def main():
    stats = compute_stats("eval/datasets/routing_ground_truth.json")
    for category, count in stats["audience_counts"].items():
        print(f"{category}: {count}")
    print(f"Total data points: {stats['total_data_points']}")
    print(f"Off-topic items: {stats['off_topic_count']}")
    for source, counts in stats["source_counts"].items():
        print(f"{source}: Required: {counts['required']}, Optional: {counts['optional']}, Total: {counts['total']}")

if __name__ == "__main__":
    main()