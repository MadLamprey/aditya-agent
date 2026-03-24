# AMA Bot — Evaluation Report
Generated: 2026-03-23 17:36:19

## Deployment Readiness Checklist

| Metric | Threshold | Actual | Status |
|--------|-----------|--------|--------|

## Layer 1: Router Evaluation

- **Full Match:** 55.2%
- **Route Precision:** 0.0%
- **Route Recall:** 0.0%
- **Audience Accuracy:** 77.0%
- **Off-topic Detection:** 75%

### By Category
| Category | Count | Exact Match | Precision | Recall |
|----------|-------|-------------|-----------|--------|

## Layer 2: Retrieval Evaluation

- **Avg Context Sufficiency:** 0.80
- **Avg MRR@k:** 0.84
- **Perfect Sufficiency Rate:** 63.0%
- **Zero Sufficiency Rate:** 11.1%

### Reranker Ablation

| Metric | With Reranker | Without Reranker | Delta |
|--------|---------------|------------------|-------|
| Context Sufficiency | 0.80 | 0.67 | +0.131 |
| MRR@k | 0.84 | 0.59 | +0.247 |
| Avg Latency | 324ms | 73ms | +251ms |

Reranker improved sufficiency on 26% of queries and MRR on 41% of queries.

## Layer 2-3: Generation Evaluation

- **Avg Faithfulness:** 0.93
- **Avg Factual Correctness:** 0.42
- **Avg Quality Score:** 1.9/5
- **Low Confidence Rate:** 16.7%

## Layer 4c: Adversarial Evaluation

- **Overall Pass Rate:** 88.9%

| Test Type | Count | Pass Rate |
|-----------|-------|-----------|
| absent_info | 4 | 100% |
| fabrication_risk | 3 | 67% |
|  ↳ FAIL: Compare yourself to other candidates you... | | The system did not acknowledge the lack ... |
| hallucination_trap | 4 | 75% |
|  ↳ FAIL: Tell me about your experience at Google... | | The system fabricated details about work... |
| identity_challenge | 1 | 100% |
| off_topic | 4 | 100% |
| prompt_injection | 1 | 100% |
| sensitive | 1 | 100% |

## Layer 4b: Persona Simulation (Recruiter)

- **Avg Faithfulness:** 0.77
- **Avg Quality Score:** 1.9/5
- **Avg Latency:** 7924ms

## Layer 5: Non-Functional Metrics

- **Avg Latency:** 6763ms
- **P95 Latency:** 14164ms
