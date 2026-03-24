"""
This is the evaluator for multi-turn conversations.

It evaluates the full conversation transcript as a unit, catching problems
that per-turn evaluation misses:
  - Consistency: does the bot contradict itself across turns?
  - Coreference: does the bot resolve references?
  - Goal completion: by the end, would an interviewer have a clear picture?
"""

import os
import json
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SessionEvalResult:
    """Result of evaluating a full multi-turn conversation."""
    consistency: str            # "pass" or "fail"
    consistency_issues: list[str]
    coreference: str            # "pass" or "fail"
    coreference_issues: list[str]
    completeness: str           # "pass" or "fail"
    overall: str                # "pass" or "fail"
    reasoning: str


def evaluate_session(history: list[tuple[str, str]]) -> SessionEvalResult:
    """
    Evaluate a full multi-turn conversation transcript.
    """
    transcript_lines = []
    for user_msg, assistant_msg in history:
        transcript_lines.append(f"Interviewer: {user_msg}")
        transcript_lines.append(f"Candidate: {assistant_msg}")
    transcript = "\n\n".join(transcript_lines)

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )

    response = client.chat.completions.create(
        model=os.getenv("JUDGE_MODEL", "gpt-4o"),
        temperature=0,
        messages=[
            {"role": "system", "content": SESSION_JUDGE_PROMPT},
            {"role": "user", "content": (
                f"TRANSCRIPT:\n{transcript}\n\n"
                f"Evaluate this conversation. Reason through each dimension, "
                f"then return JSON."
            )},
        ],
    )

    try:
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)
        return SessionEvalResult(
            consistency=result.get("consistency", "fail"),
            consistency_issues=result.get("consistency_issues", []),
            coreference=result.get("coreference", "fail"),
            coreference_issues=result.get("coreference_issues", []),
            completeness=result.get("completeness", "fail"),
            overall=result.get("overall", "fail"),
            reasoning=result.get("reasoning", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return SessionEvalResult(
            consistency="fail",
            consistency_issues=["Judge parse failure"],
            coreference="fail",
            coreference_issues=["Judge parse failure"],
            completeness="fail",
            overall="fail",
            reasoning="Judge parse failure",
        )


def _parse_json_response(raw: str) -> dict:
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
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("No valid JSON found", raw, 0)


SESSION_JUDGE_PROMPT = """\
You are evaluating a multi-turn interview transcript between an Interviewer \
and a Candidate (an AI assistant representing a job candidate).

Read the FULL conversation and evaluate three dimensions:

1. CONSISTENCY: Does the candidate contradict themselves across turns?
   - Same facts (GPA, company names, dates, project details) should be consistent.
   - Opinions and values should not flip between turns.
   - PASS if no contradictions. FAIL if any factual claim conflicts with an earlier one.

2. COREFERENCE: When the interviewer uses pronouns or references like "that project," \
"tell me more about that," "the one you mentioned," does the candidate respond about \
the correct referent from prior turns?
   - PASS if all references are resolved correctly.
   - FAIL if the candidate talks about the wrong project/topic when following up.
   - If no coreference situations arise, PASS by default.

3. COMPLETENESS: By the end of the conversation, would a recruiter have a reasonable \
picture of the candidate's background, skills, and personality?
   - This is a holistic judgment, not every detail needs to be covered.
   - PASS if the conversation covers at least: educational background, work experience, \
     technical skills, and one personality/values dimension.
   - FAIL only if major gaps remain (e.g., no mention of any work experience at all).

First reason through each dimension step by step. Then return JSON:
{
  "consistency": "pass" or "fail",
  "consistency_issues": ["list any contradictions found, empty if none"],
  "coreference": "pass" or "fail",
  "coreference_issues": ["list any misresolved references, empty if none"],
  "completeness": "pass" or "fail",
  "overall": "pass" or "fail",
  "reasoning": "One sentence summary"
}

"overall" is "pass" only if ALL three dimensions pass.
"""