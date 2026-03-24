"""
This script converts a PDF to structured markdown for RAG ingestion.

Pipeline:
  1. PyMuPDF extracts raw text with font metadata from the PDF.
  2. An LLM imposes semantic structure: ## headers, audience metadata, clean prose.
  3. Output is a markdown file ready for the chunker.
"""

import argparse
import sys
from pathlib import Path
 
import fitz
from openai import OpenAI
 
def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracting text from PDF using PyMuPDF.
    """
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)
 
    doc.close()
 
    if not pages:
        print("No text extracted from PDF.", file=sys.stderr)
        return ""
 
    return "\n\n--- PAGE BREAK ---\n\n".join(pages)
 
SYSTEM_PROMPT = """\
You are a document structuring assistant. Your job is to convert raw text \
extracted from a PDF into clean, well-structured markdown optimised for a \
RAG (Retrieval-Augmented Generation) knowledge base.
 
Rules:
 
1. STRUCTURE: Use ## headers to separate each logical section. Each section \
should be a self-contained unit that can be retrieved independently to \
answer a specific type of question. When a section contains multiple \
distinct entries (e.g. multiple jobs, multiple projects, multiple \
education entries), create a SEPARATE ## section for each entry.
 
2. METADATA: Above each ## header, add HTML comment metadata in this exact format:
   <!-- audience: {comma-separated tags} -->
   <!-- queries: {comma-separated natural-language questions this section answers} -->
   Valid audience tags: technical, recruiter, general
   The "queries" field should contain 3-5 realistic questions a person might \
   ask that this section would help answer The queries should be short and specific.
 
3. FIDELITY: Preserve ALL factual content — names, dates, metrics, \
technologies, descriptions. Do not invent, summarise away, or omit any \
information. Keep the original phrasing wherever possible.
 
4. CLEANUP: Fix formatting artifacts (broken lines, bullet fragments, \
column-merge artifacts, header/footer repetitions, page numbers) but do \
not rewrite or editorialize the content.
 
5. OUTPUT: Return ONLY the structured markdown. No preamble, no commentary, \
no explanation, no code fences wrapping the output.
"""

def structure_with_llm(
    raw_text: str,
    context: str | None = None,
    model: str = "gpt-4o-mini",
) -> str:
    """
    Invoke LLM for structuring extracted texts.
 
    Args:
        raw_text: The raw text extracted from the PDF.
        context: Optional one-liner describing the document. This helps the LLM
                 make better structuring decisions without requiring separate
                 prompts per document type.
        model: OpenAI model to use. Default: gpt-4o-mini.
 
    Returns:
        Structured markdown.
    """
    client = OpenAI()
 
    user_message = "Convert the following raw PDF text into structured markdown."
    if context:
        user_message += f"\n\nContext about this document: {context}"
    user_message += f"\n\n---\n{raw_text}\n---"
 
    response = client.chat.completions.create(
        model=model,
        temperature=0, # To ensure deterministic output
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
 
    return response.choices[0].message.content
 
def main():
    parser = argparse.ArgumentParser(
        description="Convert any PDF to structured markdown for RAG ingestion.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input PDF file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path for the output markdown file.",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="Optional description of the document.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model for structuring.",
    )
    args = parser.parse_args()
 
    input_path = Path(args.input)
    output_path = Path(args.output)
 
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
 
    print(f"Extracting text from {input_path}...")
    raw_text = extract_text_from_pdf(str(input_path))
 
    if not raw_text:
        print("No text extracted.", file=sys.stderr)
        sys.exit(1)
 
    print(f"  Extracted {len(raw_text.split())} words.")
 
    print(f"Structuring with {args.model}...")
    if args.context:
        print(f"  Context: {args.context}")
    structured_md = structure_with_llm(
        raw_text,
        context=args.context,
        model=args.model,
    )
 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(structured_md, encoding="utf-8")
 
    sections = [line for line in structured_md.split("\n") if line.startswith("## ")]
    print("\nDone.")
 
if __name__ == "__main__":
    main()