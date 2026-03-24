"""
This does Markdown-aware chunking for the knowledge base.
"""

import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_MAX_CHUNK_CHARS = 3200
DEFAULT_FALLBACK_OVERLAP = 200


def _parse_metadata_comments(text: str) -> dict:
    """
    Extract <!-- key: value --> HTML comments from a text block.
    """
    metadata = {}
    pattern = r"<!--\s*(\w+)\s*:\s*(.+?)\s*-->"
    for match in re.finditer(pattern, text):
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key in ("audience", "queries"):
            metadata[key] = [v.strip() for v in value.split(",")]
        else:
            metadata[key] = value
    return metadata


def _strip_metadata_comments(text: str) -> str:
    """Remove <!-- ... --> HTML comments from text."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def _prepend_query_metadata(content: str, metadata: dict) -> str:
    """
    Prepend query-expansion terms from metadata to chunk text.
    """
    queries = metadata.get("queries", [])
    if not queries:
        return content
    prefix = f"[Related: {', '.join(queries)}]"
    return f"{prefix}\n\n{content}"


def _split_on_headers(markdown_text: str) -> list[dict]:
    """
    Split markdown text on ## headers, correctly associating metadata comments
    with the section they describe.
    """
    # Step 1: Split on ## headers
    raw_sections = re.split(r"(?=^## )", markdown_text, flags=re.MULTILINE)

    # Step 2: Move trailing <!-- --> comments from each section to the next
    fixed_sections = []
    carried_comments = ""

    for section in raw_sections:
        # Prepend any comments carried from the previous section
        section = carried_comments + section
        carried_comments = ""

        # Check if this section ends with <!-- --> comment lines
        # Extract trailing comments and carry them to the next section
        lines = section.rstrip().split("\n")
        trailing_start = len(lines)
        for j in range(len(lines) - 1, -1, -1):
            stripped = lines[j].strip()
            if re.match(r"^<!--.*-->$", stripped):
                trailing_start = j
            elif stripped == "":
                continue  # skip blank lines between comments
            else:
                break

        if trailing_start < len(lines):
            # Found trailing comments — carry them to next section
            carried_comments = "\n".join(lines[trailing_start:]) + "\n"
            section = "\n".join(lines[:trailing_start])

        fixed_sections.append(section)

    # Step 3: Parse each section
    results = []
    for section in fixed_sections:
        section = section.strip()
        if not section:
            continue

        # Find the ## header line
        header_line = None
        header_idx = None
        section_lines = section.split("\n")
        for idx, line in enumerate(section_lines):
            if line.strip().startswith("## "):
                header_line = line.strip()
                header_idx = idx
                break

        # No ## header — this is preamble content
        if header_line is None:
            content = _strip_metadata_comments(section)
            content = re.sub(r"^#\s+.*\n?", "", content).strip()
            if content and len(content.split()) > 10:
                metadata = _parse_metadata_comments(section)
                results.append({
                    "title": "_preamble",
                    "content": content,
                    "metadata": metadata,
                    "raw": section,
                })
            continue

        title = header_line.lstrip("# ").strip()

        # Parse metadata from the full section (comments above + below header)
        metadata = _parse_metadata_comments(section)

        # Content = everything after the header, with comments stripped
        body = "\n".join(section_lines[header_idx + 1:])
        content = _strip_metadata_comments(body).strip()

        results.append({
            "title": title,
            "content": content,
            "metadata": metadata,
            "raw": section,
        })

    return results


def chunk_markdown(
    markdown_text: str,
    source: str,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    fallback_overlap: int = DEFAULT_FALLBACK_OVERLAP,
) -> list[Document]:
    """
    Chunk structured markdown into LangChain Documents.

    Primary strategy: one chunk per ## section.
    Fallback: RecursiveCharacterTextSplitter for oversized sections.

    Each Document has metadata:
      - source: the source identifier (e.g., "resume", "values")
      - section: the ## header title
      - audience: list of audience tags (if present in HTML comments)
      - queries: list of example queries (if present in HTML comments)

    Args:
        markdown_text: The full structured markdown content.
        source: Source identifier (e.g., "resume", "linkedin", "values").
        max_chunk_chars: Max characters per chunk before fallback splitting.
        fallback_overlap: Character overlap for fallback splitting.

    Returns:
        List of LangChain Document objects ready for embedding.
    """
    sections = _split_on_headers(markdown_text)
    documents = []

    # Fallback splitter — only instantiated if needed
    fallback_splitter = None

    for section in sections:
        content = section["content"]
        if not content:
            continue

        # Build metadata for this section
        meta = {
            "source": source,
            "section": section["title"],
        }
        # Merge any parsed metadata (audience, queries, etc.)
        meta.update(section["metadata"])

        if len(content) <= max_chunk_chars:
            # Section fits in one chunk — keep it atomic
            searchable_content = _prepend_query_metadata(content, section["metadata"])
            documents.append(Document(page_content=searchable_content, metadata=meta))
        else:
            # Section is too large — fallback to recursive splitting
            if fallback_splitter is None:
                fallback_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=max_chunk_chars,
                    chunk_overlap=fallback_overlap,
                    separators=["\n\n", "\n", ". ", " ", ""],
                )
            # Prepend metadata only to the first sub-chunk to avoid duplication
            sub_chunks = fallback_splitter.split_text(content)
            for i, chunk_text in enumerate(sub_chunks):
                if i == 0:
                    chunk_text = _prepend_query_metadata(chunk_text, section["metadata"])
                chunk_meta = {**meta, "chunk_part": i}
                documents.append(Document(page_content=chunk_text, metadata=chunk_meta))

    return documents