"""
This is the LangGraph routing agent.

It classifies an incoming query, selects source collections and infers audience.

Architecture: LangGraph StateGraph with conditional routing:
  route_node     — calls LLM with routing prompt, parses JSON decision
  retrieve_node  — queries the selected ChromaDB collections
  conditional edge — if route_node returns empty sources (off-topic query),
                     skip retrieval and go straight to END
"""

import json
import os
from typing import TypedDict, Annotated
import operator

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END

from src.prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE, format_history_for_router
from src.retriever import retrieve

load_dotenv()

VALID_SOURCES = {"resume", "linkedin", "github", "blog", "values"}
VALID_AUDIENCES = {"recruiter", "technical", "general"}
DEFAULT_SOURCES = [] # default to empty list if parsing fails

_llm: ChatOpenAI | None = None

def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )
    return _llm

class RouteState(TypedDict):
    query: str
    audience_hint: str                  # declared by user ("" if not set)
    history: list                       # list of (query, answer) tuples from prior turns
    sources: list[str]                  # router output: which collections to query
    audience: str                       # router output: inferred or declared
    routing_reasoning: str              # one-sentence explanation
    is_off_topic: bool                  # True if router determined query is out of scope
    is_low_confidence: bool             # True if retrieval results are low-confidence
    retrieval_debug: dict               # debug info from retrieval
    retrieved_docs: Annotated[list[Document], operator.add]

def route_node(state: RouteState) -> dict:
    """
    Call the LLM to classify the query and decide which sources to search.

    Returns partial state update with sources, audience, reasoning, and
    off-topic flag.
    """
    history_block = format_history_for_router(state.get("history", []))
    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(
            content=ROUTER_USER_TEMPLATE.format(
                history_block=history_block,
                query=state["query"],
                audience_hint=state.get("audience_hint", ""),
            )
        ),
    ]

    response = get_llm().invoke(messages)
    raw = response.content.strip()

    decision = _parse_routing_json(raw)

    raw_sources = decision.get("sources", None)
    if raw_sources is None:
        # If router did not return a "sources" field, treats it as a parsing failure and use defaults
        sources = DEFAULT_SOURCES
        is_off_topic = False
    elif len(raw_sources) == 0:
        # If router explicitly returns an empty list, treats as off-topic
        sources = []
        is_off_topic = True
    else:
        sources = [s for s in raw_sources if s in VALID_SOURCES]
        is_off_topic = False
        if not sources:
            # If all returned sources were invalid
            sources = DEFAULT_SOURCES

    audience_hint = state.get("audience_hint", "")
    reasoning = decision.get("reasoning", "")

    if audience_hint and audience_hint in VALID_AUDIENCES:
        audience = audience_hint
        reasoning += f" [audience declared by user: {audience}]"
    else:
        audience = decision.get("audience", "general")
        if audience not in VALID_AUDIENCES:
            audience = "general"

    return {
        "sources": sources,
        "audience": audience,
        "routing_reasoning": reasoning,
        "is_off_topic": is_off_topic,
    }


def retrieve_node(state: RouteState) -> dict:
    """Query the selected ChromaDB collections and return retrieved chunks."""
    result = retrieve(
        query=state["query"],
        sources=state["sources"],
        audience=state["audience"],
    )
    return {"retrieved_docs": result.docs, "is_low_confidence": result.is_low_confidence, "retrieval_debug": result.debug}

def should_retrieve(state: RouteState) -> str:
    """
    Decision function for the conditional edge after routing.

    If the router flagged the query as off-topic (sources=[]), skip retrieval
    entirely.
    """
    if state.get("is_off_topic", False):
        return "end"
    return "retrieve"

def build_router_graph() -> StateGraph:
    graph = StateGraph(RouteState)

    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)

    graph.set_entry_point("route")

    graph.add_conditional_edges(
        "route",
        should_retrieve,
        {
            "retrieve": "retrieve",
            "end": END,
        },
    )
    graph.add_edge("retrieve", END)

    return graph.compile()

_router_graph = None

def run_router(query: str, audience_hint: str = "", history: list | None = None) -> RouteState:
    """
    Run the full routing and retrieval pipeline for a query.

    Returns the completed RouteState with:
      - sources: which collections were queried
      - audience: inferred or declared
      - routing_reasoning: human-readable explanation
      - is_off_topic: whether the query was rejected
      - retrieved_docs: chunks from ChromaDB (empty if off-topic)
    """
    global _router_graph
    if _router_graph is None:
        _router_graph = build_router_graph()

    return _router_graph.invoke({
        "query": query,
        "audience_hint": audience_hint,
        "history": history or [],
        "sources": [],
        "audience": "general",
        "routing_reasoning": "",
        "is_off_topic": False,
        "is_low_confidence": False,
        "retrieval_debug": {},
        "retrieved_docs": [],
    })


def _parse_routing_json(raw: str) -> dict:
    """
    Parse the router LLM's JSON output, handling common formatting issues.
    """
    cleaned = raw.strip() # remove leading/trailing whitespace

    # Based on a common output format seen while testing
    if cleaned.startswith("{{") and cleaned.endswith("}}"):
        cleaned = cleaned[1:-1]
 
    # Direct parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
 
    # JSON fences present
    try:
        if "```" in cleaned:
            inner = cleaned.split("```")[1]
            if inner.startswith("json"):
                inner = inner[4:]
            inner = inner.strip()
            if inner.startswith("{{") and inner.endswith("}}"):
                inner = inner[1:-1]
            return json.loads(inner)
    except (json.JSONDecodeError, IndexError):
        pass
 
    # Additional text present around JSON
    try:
        start = cleaned.index("{")
        end = cleaned.rindex("}") + 1
        candidate = cleaned[start:end]
        return json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        pass
    
    # If all parsing fails
    print(f"[router] Failed to parse routing JSON: {raw!r}")
    return {
        "sources": DEFAULT_SOURCES,
        "audience": "general",
        "reasoning": "Routing JSON parse failed — using defaults.",
    }