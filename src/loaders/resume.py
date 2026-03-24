"""
Loader for resume.
"""

import os
from langchain_core.documents import Document
from .base import BaseLoader
 
class ResumeLoader(BaseLoader):
    source_id = "resume"
    default_audience = ["recruiter", "technical", "general"]
 
    def __init__(self, kb_dir: str = "knowledge_base"):
        self.kb_dir = kb_dir
        self.md_path = os.path.join(kb_dir, "resume.md")
        self.pdf_path = os.path.join(kb_dir, "resume.pdf")
 
    def load(self) -> list[Document]:
        if os.path.exists(self.md_path):
            return self._load_markdown()
 
        if os.path.exists(self.pdf_path):
            self._convert_pdf()
            return self._load_markdown()
 
        raise FileNotFoundError(f"Resume not found in Knowledge Base.")
 
    def _load_markdown(self) -> list[Document]:
        with open(self.md_path, "r", encoding="utf-8") as f:
            text = f.read()
        return [self._make_doc(text)]
 
    def _convert_pdf(self):
        """Convert resume.pdf to resume.md using pdf_to_md pipeline."""
        from src.helper.pdf_to_md import extract_text_from_pdf, structure_with_llm
 
        raw_text = extract_text_from_pdf(self.pdf_path)
        if not raw_text:
            raise RuntimeError("Failed to extract text from resume PDF.")
 
        structured_md = structure_with_llm(raw_text, context="This is a resume")
        with open(self.md_path, "w", encoding="utf-8") as f:
            f.write(structured_md)
