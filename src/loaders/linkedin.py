"""
Loader for LinkedIn profile (retrieved as profile PDF export from LinkedIn).
"""

import os
from langchain_core.documents import Document
from .base import BaseLoader

class LinkedInLoader(BaseLoader):
    source_id = "linkedin"
    default_audience = ["recruiter", "general"]

    def __init__(self, kb_dir: str = "knowledge_base"):
        self.kb_dir = kb_dir
        self.md_path = os.path.join(kb_dir, "linkedin.md")

    def _find_pdf(self) -> str | None:
        """Find any linkedin*.pdf in the KB dir — handles dated filenames like linkedin_22032026.pdf."""
        for fname in sorted(os.listdir(self.kb_dir), reverse=True):
            if fname.startswith("linkedin") and fname.endswith(".pdf"):
                return os.path.join(self.kb_dir, fname)
        return None

    def load(self) -> list[Document]:
        if os.path.exists(self.md_path):
            return self._load_markdown()

        pdf_path = self._find_pdf()
        if pdf_path:
            self._convert_pdf(pdf_path)
            return self._load_markdown()

        raise FileNotFoundError("LinkedIn profile not found in Knowledge Base.")

    def _load_markdown(self) -> list[Document]:
        with open(self.md_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [self._make_doc(text)]

    def _convert_pdf(self, pdf_path: str):
        from src.helper.pdf_to_md import extract_text_from_pdf, structure_with_llm

        raw_text = extract_text_from_pdf(pdf_path)
        if not raw_text:
            raise RuntimeError("Failed to extract text from LinkedIn PDF.")

        structured_md = structure_with_llm(
            raw_text,
            context="This is a LinkedIn profile PDF export",
        )
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(structured_md)
