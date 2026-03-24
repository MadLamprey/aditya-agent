"""
This is the full AMA pipeline: route -> retrieve -> generate.
"""

import os
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document

from src.router import run_router
from src.prompts import build_system_prompt

load_dotenv()

@dataclass
class AMAResponse:
    """
    Structured response from the AMA pipeline.
    """
    answer: str
    sources_used: list[str]             # collections that were queried
    audience: str                       # inferred or declared audience
    routing_reasoning: str              # why those sources were selected
    is_off_topic: bool                  # router flagged as out of scope
    is_low_confidence: bool             # retriever flagged as weak results
    retrieved_chunks: list[Document]    # raw retrieved docs
    retrieval_debug: dict               # scores, counts, timings from retriever
    latency_ms: float                   # end-to-end latency

OFF_TOPIC_RESPONSES = [
    "Ha — that's a bit outside my wheelhouse. Happy to talk about my work, "
    "projects, or background though!",
    "That one's outside what I can speak to here — but feel free to ask me "
    "anything about my experience or how I work.",
    "I'm probably not the best person to ask about that! I can talk about "
    "my projects, skills, or what I'm looking for in my next role though.",
]

def _get_off_topic_response(query: str) -> str:
    """
    Select an off-topic refusal response.
    """
    idx = hash(query) % len(OFF_TOPIC_RESPONSES)
    return OFF_TOPIC_RESPONSES[idx]

_generator_llm: ChatOpenAI | None = None

def get_generator_llm() -> ChatOpenAI:
    """
    Generator LLM — separate instance from the router LLM.
    temperature=0.3: low enough to stay grounded in context and not hallucinate,
    high enough for natural conversational variation.
    """
    global _generator_llm
    if _generator_llm is None:
        _generator_llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
    return _generator_llm

def format_context(docs: list[Document]) -> str:
    if not docs:
        return "No relevant information was found in the knowledge base for this query."

    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        section = doc.metadata.get("section", "")
        label = f"[{source}" + (f" — {section}]" if section else "]")
        parts.append(f"{label}\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)

def ask(query: str, audience_hint: str = "", history: list[tuple[str, str]] | None = None) -> AMAResponse:
    """
    Run the full AMA pipeline for a single query.
    """
    t_start = time.perf_counter()
    history = history or []

    state = run_router(query, audience_hint=audience_hint, history=history)

    sources = state["sources"]
    audience = state["audience"]
    reasoning = state["routing_reasoning"]
    is_off_topic = state.get("is_off_topic", False)
    is_low_confidence = state.get("is_low_confidence", False)
    docs = state["retrieved_docs"]
    retrieval_debug = state.get("retrieval_debug", {})

    if is_off_topic:
        latency_ms = (time.perf_counter() - t_start) * 1000
        return AMAResponse(
            answer=_get_off_topic_response(query),
            sources_used=[],
            audience=audience,
            routing_reasoning=reasoning,
            is_off_topic=True,
            is_low_confidence=False,
            retrieved_chunks=[],
            retrieval_debug={},
            latency_ms=round(latency_ms, 1),
        )

    context = format_context(docs)
    system_prompt = build_system_prompt(context=context, audience=audience)

    llm = get_generator_llm()
    messages = [SystemMessage(content=system_prompt)]
    for prior_query, prior_answer in history[-3:]:
        messages.append(HumanMessage(content=prior_query))
        messages.append(AIMessage(content=prior_answer))
    messages.append(HumanMessage(content=query))
    response = llm.invoke(messages)

    latency_ms = (time.perf_counter() - t_start) * 1000

    return AMAResponse(
        answer=response.content,
        sources_used=sources,
        audience=audience,
        routing_reasoning=reasoning,
        is_off_topic=False,
        is_low_confidence=is_low_confidence,
        retrieved_chunks=docs,
        retrieval_debug=retrieval_debug,
        latency_ms=round(latency_ms, 1),
    )