"""
Loader for personality document.
"""

import os
from langchain_core.documents import Document
from .base import BaseLoader
 
class ValuesLoader(BaseLoader):
    source_id = "values"
    default_audience = ["recruiter", "general"]
 
    FILENAMES = ["personality.md", "values.md", "values_and_working_style.md"]
 
    def __init__(self, kb_dir: str = "knowledge_base"):
        self.kb_dir = kb_dir
 
    def _find_file(self) -> str:
        for name in self.FILENAMES:
            path = os.path.join(self.kb_dir, name)
            if os.path.exists(path):
                return path
        raise FileNotFoundError(f"Values/personality doc not found in Knowledge Base.")
 
    def load(self) -> list[Document]:
        path = self._find_file()
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return [self._make_doc(text)]
