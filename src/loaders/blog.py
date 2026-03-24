"""
Loader for Medium blog posts (retrieved from official Medium RSS feeds).
"""

import os
import feedparser
import html2text
from langchain_core.documents import Document
from .base import BaseLoader
 
class BlogLoader(BaseLoader):
    source_id = "blog"
    default_audience = ["technical", "general"]
 
    def __init__(self, medium_username: str | None = None):
        self.username = medium_username or os.getenv("MEDIUM_USERNAME", "")
        if not self.username:
            raise ValueError("Medium username not provided.")
 
        self._h2t = html2text.HTML2Text()
        self._h2t.ignore_links = False
        self._h2t.ignore_images = True
        self._h2t.body_width = 0
        self._h2t.ignore_emphasis = False
 
    def load(self) -> list[Document]:
        feed_url = f"https://medium.com/feed/@{self.username}"
        feed = feedparser.parse(feed_url)
 
        if feed.bozo and not feed.entries:
            raise RuntimeError(
                f"Failed to parse Medium RSS feed.")
 
        docs = []
        for entry in feed.entries:
            content_blocks = entry.get("content", [])
            if content_blocks:
                raw_html = content_blocks[0].get("value", "")
            else:
                raw_html = entry.get("summary", "")
 
            if not raw_html:
                continue
 
            body_md = self._h2t.handle(raw_html).strip()
 
            title = entry.get("title", "Untitled")
            published = entry.get("published", "")[:10]
            link = entry.get("link", "")
 
            page_content = (
                f"# {title}\n\n"
                f"Published: {published}\n"
                f"URL: {link}\n\n"
                f"{body_md}"
            )
 
            doc = self._make_doc(
                page_content,
                title=title,
                published=published,
                url=link,
            )
            docs.append(doc)
 
        return docs
