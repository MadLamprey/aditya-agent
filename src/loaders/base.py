"""
This is the base loader interface.

All loaders return List[Document] with standardised metadata.
Loaders produce one document per logical unit (one for the whole resume, one per
blog post, one per repo, etc.).
"""

from abc import ABC, abstractmethod
from langchain_core.documents import Document

class BaseLoader(ABC):
    source_id: str = ""    # To identify the source of each document
    default_audience: list[str] = ["general"]   # Default audience tag
    # This may be overridden by individual loaders

    @abstractmethod
    def load(self) -> list[Document]:
        """
        Load documents from source.

        Returns a list of LangChain Document objects. Each Document contains:
          - page_content as structured markdown
          - metadata["source"] set to the source_id of the loader
        """
        raise NotImplementedError

    def _make_doc(self, content: str, **extra_metadata) -> Document:
        """Create a Document with standard metadata."""
        metadata = {"source": self.source_id}
        metadata.update(extra_metadata)
        return Document(page_content=content, metadata=metadata)