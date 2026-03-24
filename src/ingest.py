"""
This is the data ingestion pipeline.

It runs all loaders, chunks with markdown-aware splitter, embeds with bge-small-en-v1.5
and stores in per-source ChromaDB collections.

- Every loader outputs structured markdown with ## headers.
The chunker (src/chunker.py) splits on those headers, preserving semantic
boundaries.
- Per-source collections in ChromaDB (instead of one flat DB) keep retrieval scoped,
prevent noise from unrelated sources, and allow each source to be updated
independently without reprocessing the whole corpus.

- BAAI/bge-small-en-v1.5 embeddings run locally on CPU with no API cost, with
sufficient quality for retrieval tasks.

Usage:
    python3 -m src.ingest                  # To ingest all sources
    python3 -m src.ingest --source github  # To ingest a single source
    python3 -m src.ingest --clear          # To clear existing collections before ingesting
"""

import argparse
import os
import shutil
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src.helper.chunker import chunk_markdown
from src.loaders.resume import ResumeLoader
from src.loaders.linkedin import LinkedInLoader
from src.loaders.github import GitHubLoader
from src.loaders.blog import BlogLoader
from src.loaders.values import ValuesLoader

load_dotenv()

KB_DIR = os.getenv("KB_DIR", "knowledge_base")
CHROMA_DIR = os.getenv("CHROMA_DIR", "chroma_db")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

ALL_SOURCES = ["resume", "linkedin", "github", "blog", "values"]

def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

def get_loader(source_id: str, kb_dir: str = KB_DIR):
    loaders = {
        "resume":   ResumeLoader(kb_dir),
        "linkedin": LinkedInLoader(kb_dir),
        "github":   GitHubLoader(),
        "blog":     BlogLoader(),
        "values":   ValuesLoader(kb_dir),
    }
    if source_id not in loaders:
        raise ValueError(f"Unknown source '{source_id}'. Choose from: {ALL_SOURCES}")
    return loaders[source_id]

def ingest_source(source_id: str, embeddings: HuggingFaceEmbeddings) -> int:
    """
    Load, chunk, embed, and store one source. Returns number of chunks stored.
    """
    print(f"\n Ingesting [{source_id}]")
    loader = get_loader(source_id)

    try:
        docs = loader.load()
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[{source_id}] SKIPPED — {e}")
        return 0

    all_chunks = []
    # Chunking each document
    for doc in docs:
        chunks = chunk_markdown(doc.page_content, source=source_id)

        for chunk in chunks:
            # Preserve document metadata in each chunk
            for key, value in doc.metadata.items():
                chunk.metadata.setdefault(key, value)

        all_chunks.extend(chunks)

    print(f"[{source_id}] {len(docs)} document(s), {len(all_chunks)} chunk(s)")

    if not all_chunks:
        print(f"[{source_id}] No chunks produced.")
        return 0

    collection_name = f"ama_{source_id}"
    Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=collection_name,
    )
    print(f"[{source_id}] Stored in collection '{collection_name}'")
    return len(all_chunks)


def clear_collections(sources: list[str]):
    """Remove ChromaDB collections for the specified sources."""
    for source_id in sources:
        collection_dir = os.path.join(CHROMA_DIR, f"ama_{source_id}")
        if os.path.exists(collection_dir):
            print(f"Removing {collection_dir}/...")
            shutil.rmtree(collection_dir, ignore_errors=True)

def ingest_all(sources: list[str] | None = None, clear: bool = False):
    targets = sources or ALL_SOURCES

    if clear:
        clear_collections(targets)

    embeddings = get_embeddings()
    total = 0
    for src in targets:
        total += ingest_source(src, embeddings)

    print(f"Ingestion complete. Total chunks stored: {total}")
    print(f"ChromaDB directory: {CHROMA_DIR}")
    print(f"Collections: {['ama_' + s for s in targets]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=ALL_SOURCES,
        help="Ingest a single source (default: all)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing ChromaDB collections before ingesting",
    )
    args = parser.parse_args()
    ingest_all(
        sources=[args.source] if args.source else None,
        clear=args.clear,
    )