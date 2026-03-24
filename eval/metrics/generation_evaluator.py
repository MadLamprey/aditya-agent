"""
This is the evaluator for generation.

It measures answer quality through these metrics:
  - Faithfulness: is the answer grounded in the retrieved context?
    Score 0-1 based on whether claims can be traced to context chunks.
  - Factual correctness: does the answer contain expected key facts?
    Binary check per fact, aggregated to a score. Deterministic, no LLM.
  - Answer quality: 3-point rubric (0=Poor, 1=Acceptable, 2=Good).
"""

import os
import json
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class GenerationResult:
    """Result for a single generation evaluation."""
    query: str
    answer: str
    faithfulness_score: float       # 0-1: is the answer grounded in context?
    factual_score: float            # 0-1: fraction of expected facts present
    quality_score: float            # 0-2: overall answer quality (3-point rubric)
    quality_reasoning: str          # explanation from the judge (CoT, before score)
    facts_found: list[str]          # which expected facts were present
    facts_missing: list[str]        # which expected facts were absent
    is_low_confidence: bool         # from the retriever
    latency_ms: float


def _get_judge_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )

def _parse_json_response(raw: str) -> dict:
    """
    Robust JSON parser with fallback chain.
    """
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if "```" in raw:
        inner = raw.split("```")[1]
        if inner.startswith("json"):
            inner = inner[4:]
        try:
            return json.loads(inner.strip())
        except json.JSONDecodeError:
            pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = raw.find(start_char)
        end = raw.rfind(end_char)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("No valid JSON found", raw, 0)

def evaluate_faithfulness(
    query: str,
    answer: str,
    context_chunks: list[str],
) -> float:
    """
    Score faithfulness: is every claim in the answer supported by the context?
    """
    if not answer or not context_chunks:
        return 0.0

    # If the answer is a refusal, it's faithful by definition
    refusal_markers = [
        "don't have that information", "outside my", "can't speak to",
        "not something I've covered", "not the best person to ask",
    ]
    if any(m in answer.lower() for m in refusal_markers):
        return 1.0

    context = "\n\n---\n\n".join(context_chunks)
    client = _get_judge_client()

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=0,
        messages=[
            {"role": "system", "content": FAITHFULNESS_PROMPT},
            {"role": "user", "content": (
                f"CONTEXT:\n{context}\n\n"
                f"ANSWER:\n{answer}\n\n"
                f"Evaluate faithfulness step by step, then return JSON."
            )},
        ],
    )

    try:
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)
        total = result.get("total_claims", 1)
        supported = result.get("supported_claims", 0)
        return supported / max(total, 1)
    except (json.JSONDecodeError, KeyError):
        return 0.5

def evaluate_factual_correctness(
    answer: str,
    expected_facts: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Check which expected key facts appear in the answer.
    """
    if not expected_facts:
        return 1.0, [], []

    answer_lower = answer.lower()
    found = [f for f in expected_facts if f.lower() in answer_lower]
    missing = [f for f in expected_facts if f.lower() not in answer_lower]
    score = len(found) / len(expected_facts)
    return score, found, missing

def evaluate_answer_quality(
    query: str,
    answer: str,
    audience: str,
) -> tuple[float, str]:
    """
    LLM judge scores overall answer quality on a 3-point rubric.
    0 = Poor, 1 = Acceptable, 2 = Good.
    """
    client = _get_judge_client()

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=0,
        messages=[
            {"role": "system", "content": QUALITY_PROMPT},
            {"role": "user", "content": (
                f"QUERY: {query}\n"
                f"AUDIENCE: {audience}\n"
                f"ANSWER: {answer}\n\n"
                f"Evaluate this answer step by step, then return JSON."
            )},
        ],
    )

    try:
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)
        return float(result.get("score", 1)), result.get("reasoning", "")
    except (json.JSONDecodeError, KeyError):
        return 1.0, "Judge parse failure"

def compute_generation_summary(results: list[GenerationResult]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    latencies = sorted(r.latency_ms for r in results)

    return {
        "total_queries": n,
        "avg_faithfulness": sum(r.faithfulness_score for r in results) / n,
        "avg_factual_correctness": sum(r.factual_score for r in results) / n,
        "avg_quality_score": sum(r.quality_score for r in results) / n,
        "quality_score_distribution": {
            "good": sum(1 for r in results if r.quality_score == 2) / n,
            "acceptable": sum(1 for r in results if r.quality_score == 1) / n,
            "poor": sum(1 for r in results if r.quality_score == 0) / n,
        },
        "low_confidence_rate": sum(r.is_low_confidence for r in results) / n,
        "avg_latency_ms": sum(r.latency_ms for r in results) / n,
        "p95_latency_ms": latencies[int(n * 0.95)] if n > 1 else latencies[0],
    }


FAITHFULNESS_PROMPT = """\
You are an evaluation judge. Your task is to assess whether an answer is \
faithful to (grounded in) the provided context.

INSTRUCTIONS:
1. Extract each distinct factual claim from the ANSWER.
2. For EACH claim, determine if the CONTEXT supports it:
   - SUPPORTED: context contains information that directly states or implies the claim.
   - UNSUPPORTED: context does not contain relevant information, or claim contradicts context.
   - Note: opinions, reasoning, and self-descriptions ("I believe...", "I care about...") \
are supported if the context contains similar sentiments, even if not word-for-word.
3. Write your reasoning for each claim FIRST.
4. THEN return the final JSON.

IMPORTANT: Do NOT favor longer answers. A short, accurate answer is more faithful \
than a long answer that adds unsupported details.

EXAMPLE:

CONTEXT: "I built a dashboard using Angular that monitored 120+ machine parameters. \
Data flowed from sensors through Redis into PostgreSQL."

ANSWER: "At Hutchinson, I built a real-time monitoring dashboard using Angular \
and PostgreSQL that tracked over 120 machine parameters. The system used Redis \
for data streaming and served about 50 users daily."

Step-by-step:
- Claim: "built a real-time monitoring dashboard using Angular" -> SUPPORTED (context mentions Angular dashboard)
- Claim: "PostgreSQL" -> SUPPORTED (context mentions PostgreSQL)
- Claim: "tracked over 120 machine parameters" -> SUPPORTED (context says "120+ machine parameters")
- Claim: "used Redis for data streaming" -> SUPPORTED (context says "through Redis")
- Claim: "served about 50 users daily" -> UNSUPPORTED (context says nothing about user count)

{"total_claims": 5, "supported_claims": 4, "unsupported_claims": ["served about 50 users daily"]}

Now evaluate the following. Reason through each claim first, then return JSON:
{"total_claims": <int>, "supported_claims": <int>, "unsupported_claims": [<list of strings>]}
"""

QUALITY_PROMPT = """\
You are an evaluation judge for an AI interview assistant that answers \
questions about a job candidate. Score the ANSWER on a 3-point scale.

SCORING RUBRIC:

Score 2 (Good): Directly answers the query with specific details (names, \
numbers, project specifics). Natural first-person voice. Appropriate depth \
for the audience. No fabrication.

Score 1 (Acceptable): Answers the query but is vague, overly generic, or \
misses key details that would make it convincing. May feel slightly robotic \
or lack personality.

Score 0 (Poor): Off-topic, factually wrong, breaks persona (third person, \
robotic "As an AI..."), or is a non-answer that doesn't address the query.

EXAMPLES:

--- Example 1 (Score 2 — Good) ---
QUERY: "What's your ML experience?"
AUDIENCE: technical
ANSWER: "I worked on SEA-LION at AI Singapore, building an ETL pipeline for \
15,000 hours of multilingual speech data. I also designed the ASR evaluation \
framework that computed WER and CER with per-language breakdowns — that's \
where I learned that aggregate metrics can hide failures."
Reasoning: Specific project name, concrete numbers, names the actual metrics. \
Natural first-person voice. Appropriate technical depth.
Score: 2

--- Example 2 (Score 1 — Acceptable) ---
QUERY: "What's your ML experience?"
AUDIENCE: technical
ANSWER: "I have experience with machine learning from my internship at AI \
Singapore where I worked on data pipelines and evaluation."
Reasoning: Answers the question and mentions the right company, but no \
specifics — no project name, no numbers, no concrete details. Generic.
Score: 1

--- Example 3 (Score 0 — Poor) ---
QUERY: "What's your ML experience?"
AUDIENCE: technical
ANSWER: "Machine learning is a subfield of artificial intelligence that \
uses statistical techniques to give computers the ability to learn."
Reasoning: Does not answer the question about the candidate's experience. \
This is a textbook definition, not a personal response.
Score: 0

INSTRUCTIONS:
1. Read the QUERY, AUDIENCE, and ANSWER.
2. Write your reasoning FIRST — explain which score level the answer matches and why.
3. THEN return the JSON.

IMPORTANT: Do NOT favor longer answers over shorter ones. A concise, specific \
answer that directly addresses the query scores higher than a lengthy but \
vague one. Judge by information quality, not quantity.

Return JSON: {"reasoning": "<your explanation>", "score": <0, 1, or 2>}
"""