"""
CLI entrypoint for the AMA Bot.

Usage:
    python main.py                          # interactive mode
    python main.py --audience recruiter     # declare audience upfront
    python main.py -q "Tell me about your Python experience"  # single shot

First run: ingest the knowledge base before starting.
    python -m src.ingest
"""

import argparse
import json
import sys
import os
from dotenv import load_dotenv

from src.chain import ask, AMAResponse

load_dotenv()

CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "Aditya Misra")

BANNER = f"""
╔═══════════════════════════════════════════╗
║     AMA Bot — Ask Me Anything             ║
║     Interview assistant for Aditya Misra. ║
╚═══════════════════════════════════════════╝
Type 'quit' or Ctrl+C to exit.
Type '/help' for commands.
"""

HELP_TEXT = """
Commands:
  /recruiter    Switch to recruiter mode
  /technical    Switch to technical interviewer mode
  /general      Switch to general visitor mode (default)
  /sources      Show routing + retrieval details for last answer
  /help         Show this message
  quit          Exit

Audience modes are optional — the bot infers who you are
from your questions if you don't set one explicitly.
"""

def print_response(response: AMAResponse, verbose: bool = False):
    print(f"\n{response.answer}")

    parts = []
    if response.sources_used:
        parts.append(f"Sources: {', '.join(response.sources_used)}")
    parts.append(f"Audience: {response.audience}")
    parts.append(f"{response.latency_ms:.0f}ms")

    if response.is_low_confidence:
        parts.append("low confidence")

    print(f"  [{' | '.join(parts)}]\n")


def print_sources(response: AMAResponse):
    if response.is_off_topic:
        print(" Query was flagged as off-topic. No retrieval was performed.")
        return

    print(f"Sources:   {response.sources_used}")
    print(f"Audience:  {response.audience}")
    print(f"Reasoning: {response.routing_reasoning}")

    print(f"\n  Retrieved {len(response.retrieved_chunks)} chunk(s):")
    for i, chunk in enumerate(response.retrieved_chunks, 1):
        source = chunk.metadata.get("source", "?")
        section = chunk.metadata.get("section", "")
        preview = chunk.page_content[:100].replace("\n", " ")
        label = f"{source}/{section}" if section else source
        print(f"    {i}. [{label}] {preview}...")
    print()

def interactive_mode(audience: str = ""):
    print(BANNER)
    if audience:
        print(f"Audience set to: {audience}\n")

    current_audience = audience
    last_response: AMAResponse | None = None
    history: list[tuple[str, str]] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            sys.exit(0)

        if not user_input:
            continue

        lower = user_input.lower()

        # Exit
        if lower in ("quit", "exit", "q"):
            print("Goodbye!")
            sys.exit(0)

        # Commands
        if lower == "/help":
            print(HELP_TEXT)
            continue

        if lower in ("/recruiter", "/technical", "/general"):
            current_audience = lower[1:]
            print(f"  [Switched to {current_audience} mode]\n")
            continue

        if lower == "/sources":
            if last_response:
                print_sources(last_response)
            else:
                print("  No previous response to inspect.\n")
            continue

        # Query
        print(f"\n{CANDIDATE_NAME}: ", end="", flush=True)
        try:
            response = ask(user_input, audience_hint=current_audience, history=history)
            last_response = response
            history.append((user_input, response.answer))
            print_response(response)
        except Exception as e:
            print(f"\n  [Error: {e}]\n")


def single_query_mode(query: str, audience: str = "", debug: bool = False):
    """Run a single query and exit. Used for scripting and eval."""
    response = ask(query, audience_hint=audience)
    print_response(response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AMA Bot — AI-powered interview assistant",
    )
    parser.add_argument(
        "--audience", "-a",
        choices=["recruiter", "technical", "general"],
        default="",
        help="Declare your audience role (optional — bot infers if not set)",
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default="",
        help="Single question mode (non-interactive)",
    )
    args = parser.parse_args()

    if args.query:
        single_query_mode(args.query, audience=args.audience)
    else:
        interactive_mode(audience=args.audience)