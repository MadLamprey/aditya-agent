"""
3-Bot Evaluation System (Experimental).

Architecture:
  Bot 1 — Interviewer: LLM-powered, generates dynamic follow-up questions
  Bot 2 — Candidate: the existing ask() pipeline (route -> retrieve -> generate)
  Bot 3 — Evaluator: session_evaluator (consistency, coreference, completeness)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from dotenv import load_dotenv

from src.chain import ask
from eval.metrics.session_evaluator import evaluate_session
from eval.metrics.generation_evaluator import (
    evaluate_faithfulness, evaluate_answer_quality,
)

load_dotenv()

RESULTS_DIR = Path(__file__).resolve().parent / "results"

INTERVIEWER_PERSONAS = {
    "recruiter": """\
You are a recruiter conducting a 30-minute screening interview with a \
software engineering / AI candidate. Your goal is to understand:
- Their background and career trajectory
- What motivates them and what kind of team they thrive in
- Whether they'd be a good culture fit
- Their communication style and self-awareness

Start with a warm opening. Ask one question at a time. Listen to their \
answers and ask natural follow-ups — "tell me more about that," "what \
did you learn from that experience," "how did that shape how you work now."

Do NOT ask rapid-fire unrelated questions. A good interview has flow — \
each question should connect to something the candidate just said. \
Aim for a mix of biographical, behavioral, and motivational questions.

You are interviewing for a position at Manulife, an insurance and \
financial services company building AI systems for Asia.""",

    "technical": """\
You are a senior engineer conducting a technical interview with a \
candidate who has experience in AI systems, data pipelines, and \
full-stack development. Your goal is to understand:
- Technical depth: do they understand the systems they've built?
- Decision-making: why did they make specific architectural choices?
- Trade-offs: can they reason about trade-offs, not just describe tools?
- Growth areas: where are they honest about what they don't know?

Start by asking about a project on their resume. Then go deeper — \
ask about specific technical decisions, what they'd do differently, \
how they evaluated quality. Ask one question at a time and follow up \
based on their answers.

Don't quiz them on trivia. Focus on judgment and reasoning.""",
}

def generate_interviewer_question(
    history: list[dict],
    persona: str = "recruiter",
    turn_number: int = 1,
    max_turns: int = 8,
) -> str:
    """
    Generate the next interviewer question based on conversation history.
    """
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )

    persona_prompt = INTERVIEWER_PERSONAS.get(persona, INTERVIEWER_PERSONAS["recruiter"])

    messages = [
        {"role": "system", "content": (
            f"{persona_prompt}\n\n"
            f"This is turn {turn_number} of {max_turns}. "
            f"{'Start with a warm opening question.' if turn_number == 1 else ''}"
            f"{'This is your last question — make it a good closing question.' if turn_number == max_turns else ''}"
            f"\nRespond with ONLY the question, no preamble or stage directions."
        )},
    ]

    # Add conversation history
    for msg in history:
        if msg["role"] == "user":
            messages.append({"role": "assistant", "content": msg["content"]})
        elif msg["role"] == "assistant":
            messages.append({"role": "user", "content": msg["content"]})

    response = client.chat.completions.create(
        model=os.getenv("JUDGE_MODEL", "gpt-4o"),
        temperature=0.7,  # some variety in questions
        max_tokens=150,
        messages=messages,
    )

    return response.choices[0].message.content.strip()

def run_three_bot_eval(
    max_turns: int = 8,
    persona: str = "recruiter",
) -> dict:
    """
    Run the full 3-bot evaluation loop.
    """
    history_tuples: list[tuple[str, str]] = [] 
    history_dicts: list[dict] = []
    per_turn_metrics = []
    audience_hint = persona if persona in ("recruiter", "technical") else "general"

    for turn in range(1, max_turns + 1):
        question = generate_interviewer_question(
            history_dicts, persona=persona, turn_number=turn, max_turns=max_turns,
        )
        print(f"\n  [Turn {turn}/{max_turns}]")
        print(f"  Q: {question}")

        response = ask(question, audience_hint=audience_hint, history=history_tuples)
        answer = response.answer
        print(f"  A: {answer[:200]}{'...' if len(answer) > 200 else ''}")

        history_tuples.append((question, answer))
        history_dicts.append({"role": "user", "content": question})
        history_dicts.append({"role": "assistant", "content": answer})

        context_chunks = [doc.page_content for doc in response.retrieved_chunks]
        faithfulness = evaluate_faithfulness(question, answer, context_chunks)
        quality, quality_reasoning = evaluate_answer_quality(question, answer, audience_hint)

        per_turn_metrics.append({
            "turn": turn,
            "question": question,
            "answer": answer[:300],
            "faithfulness": faithfulness,
            "quality": quality,
            "sources": response.sources_used,
            "is_off_topic": response.is_off_topic,
            "latency_ms": response.latency_ms,
        })

        status = f"faith={faithfulness:.2f} quality={quality:.0f}"
        print(f"  [{status}] sources={response.sources_used}")

    print(f"\n  {'─'*50}")
    print(f"  Session-Level Evaluation")
    print(f"  {'─'*50}")

    session_result = evaluate_session(history_tuples)
    print(f"  Consistency:  {session_result.consistency.upper()}")
    print(f"  Coreference:  {session_result.coreference.upper()}")
    print(f"  Completeness: {session_result.completeness.upper()}")
    print(f"  Overall:      {session_result.overall.upper()}")
    print(f"  Reasoning:    {session_result.reasoning}")

    n = len(per_turn_metrics)
    avg_faith = sum(m["faithfulness"] for m in per_turn_metrics) / n
    avg_quality = sum(m["quality"] for m in per_turn_metrics) / n
    avg_latency = sum(m["latency_ms"] for m in per_turn_metrics) / n

    results = {
        "persona": persona,
        "max_turns": max_turns,
        "per_turn": per_turn_metrics,
        "summary": {
            "avg_faithfulness": avg_faith,
            "avg_quality": avg_quality,
            "avg_latency_ms": avg_latency,
        },
        "session": {
            "consistency": session_result.consistency,
            "coreference": session_result.coreference,
            "completeness": session_result.completeness,
            "overall": session_result.overall,
            "reasoning": session_result.reasoning,
        },
        "full_transcript": history_dicts,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"three_bot_{persona}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n  Avg faithfulness: {avg_faith:.2f}")
    print(f"  Avg quality:      {avg_quality:.1f}/2")
    print(f"  Avg latency:      {avg_latency:.0f}ms")
    print(f"\n  Results saved to: {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 3-bot evaluation")
    parser.add_argument("--turns", type=int, default=8,
                        help="Number of interview turns (default: 8)")
    parser.add_argument("--persona", choices=["recruiter", "technical"],
                        default="recruiter", help="Interviewer persona")
    args = parser.parse_args()
    run_three_bot_eval(max_turns=args.turns, persona=args.persona)