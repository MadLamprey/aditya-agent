# Project AMA — Ask Me Anything

An AI-powered interview assistant that answers questions about Aditya Misra.

A LangGraph agentic RAG pipeline routes each question to the relevant knowledge source (résumé, LinkedIn, GitHub, blog, values doc), retrieves context with hybrid search and cross-encoder reranking, and generates a grounded first-person answer.

---

## Prerequisites

- Python 3.11+
- An OpenAI API key (`gpt-4o-mini` for the pipeline, `gpt-4o` for the eval judge)
- Node.js 18+ (frontend only)

---

## Setup

**1. Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

The first run will also download two local models (~90MB total):
- `BAAI/bge-small-en-v1.5` — embedding model (runs on CPU)
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — reranker (runs on CPU)

Both are downloaded automatically by `sentence-transformers` on first use.

**3. Configure environment variables**

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required:

```
OPENAI_API_KEY=sk-...
```

Optional (with defaults):

```
GITHUB_USERNAME=MadLamprey          # GitHub profile to ingest
MEDIUM_USERNAME=https://medium.com/@adityamisra_68704  # Medium blog RSS username
GITHUB_TOKEN=ghp_...                # Raises rate limit from 60 to 5000 req/hr
KB_DIR=knowledge_base               # Path to markdown knowledge base files
CHROMA_DIR=chroma_db                # Path for ChromaDB vector store
```

---

## Running

### Step 1 — Ingest the knowledge base

Embeds all five sources into per-source ChromaDB collections. Run once before starting the server.

```bash
python -m src.ingest                   # ingest all sources
python -m src.ingest --source github   # ingest one source
python -m src.ingest --clear           # clear and reingest
```

Sources ingested:
| Source | File / Method |
|--------|---------------|
| Résumé | `knowledge_base/resume.md` |
| LinkedIn | `knowledge_base/linkedin.md` |
| GitHub | GitHub REST API (live, uses `GITHUB_USERNAME`) |
| Blog | Medium RSS feed (live, uses `MEDIUM_USERNAME`) |
| Values doc | `knowledge_base/personality.md` |

### Step 2 — Start the API server

```bash
uvicorn api.server:app --reload --port 8000
```

The server exposes:
- `POST /ask` — main query endpoint
- `GET /health` — health check

### Step 3 — (Optional) Start the frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
```

See `frontend/README.md` for details.

### Step 4 — (Optional) CLI

```bash
python main.py                              # interactive mode
python main.py --audience recruiter         # declare audience upfront
python main.py -q "Tell me about your Python experience"   # single-shot
```

---

## Evaluation

Run all evaluation layers:

```bash
python -m eval.run_eval
```

Run a specific layer:

```bash
python -m eval.run_eval --layer routing
python -m eval.run_eval --layer adversarial
python -m eval.run_eval --layer generation
python -m eval.run_eval --layer persona
```

Run the dynamic 3-bot evaluation (interviewer + candidate + judge):

```bash
python -m eval.three_bot_eval
python -m eval.three_bot_eval --persona technical --turns 10
```

Results are written to:
- `eval/results/eval_report.md` — human-readable summary with scores
- `eval/results/eval_results.json` — full structured audit log
- `eval/results/three_bot_recruiter.json` — 3-bot session transcript and scores

---

## Project structure

```
aditya-agent/
  api/
    server.py           FastAPI server — CORS, /ask endpoint
  src/
    chain.py            Full pipeline: route → retrieve → generate
    router.py           LangGraph StateGraph router
    retriever.py        3-stage retrieval: hybrid search → rerank → grade
    prompts.py          Router + generator prompt templates
    ingest.py           Ingestion pipeline: all sources → ChromaDB
    loaders/
      resume.py         Loads knowledge_base/resume.md
      linkedin.py       Loads knowledge_base/linkedin.md
      github.py         Fetches repos via GitHub REST API
      blog.py           Fetches posts via Medium RSS feed
      values.py         Loads knowledge_base/personality.md
    helper/
      chunker.py        Markdown-aware chunker with metadata parsing
      pdf_to_md.py      PDF → structured Markdown (one-time conversion tool)
  eval/
    datasets/           Evaluation ground-truth datasets (JSON)
    metrics/            Evaluator modules (routing, retrieval, generation, adversarial, session)
    run_eval.py         Single entrypoint for all evaluation layers
    three_bot_eval.py   Dynamic 3-bot persona simulation
    results/            Eval output (report + audit log)
  knowledge_base/
    resume.md           Résumé (structured Markdown)
    linkedin.md         LinkedIn profile (structured Markdown)
    personality.md      Hand-authored values and working style doc
  main.py               CLI entrypoint
  requirements.txt      Python dependencies
  .env.example          Environment variable template
```

---
