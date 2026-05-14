from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


ARTICLE_SPLIT_PATTERN = re.compile(r"(?=Điều\s+\d+[A-Za-z0-9-]*[\.:])", re.IGNORECASE)
TITLE_PATTERN = re.compile(r"^(Luật[^\n]+|Bộ luật[^\n]+)", re.IGNORECASE | re.MULTILINE)
TOKEN_PATTERN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
ALNUM_BOUNDARY_PATTERN = re.compile(r"(?<=[A-Za-zÀ-ỹ])(?=\d)|(?<=\d)(?=[A-Za-zÀ-ỹ])")
STOPWORDS = {
    "và",
    "là",
    "của",
    "theo",
    "cho",
    "trong",
    "một",
    "những",
    "các",
    "được",
    "không",
    "về",
    "tại",
    "này",
    "that",
}


@dataclass(slots=True)
class LegalChunk:
    content: str
    article: str | None
    clause: str | None


class LegalTextService:
    def guess_title(self, content: str, fallback: str) -> str:
        match = TITLE_PATTERN.search(content)
        if match:
            return match.group(1).strip()
        return fallback

    def split_legal_text(self, content: str) -> list[str]:
        parts = [part.strip() for part in ARTICLE_SPLIT_PATTERN.split(content) if part.strip()]
        return parts or [content.strip()]

    def summarize(self, content: str, max_length: int = 180) -> str:
        single_line = " ".join(content.split())
        return single_line[: max_length - 3] + "..." if len(single_line) > max_length else single_line

    def normalize_query(self, query: str) -> str:
        prepared = ALNUM_BOUNDARY_PATTERN.sub(" ", query)
        return re.sub(r"\s+", " ", prepared).strip()

    def tokenize(self, text: str) -> set[str]:
        prepared = self.normalize_query(text)
        tokens = {token.lower() for token in TOKEN_PATTERN.findall(prepared)}
        expanded_tokens: set[str] = set()
        for token in tokens:
            if len(token) > 1 and token not in STOPWORDS:
                expanded_tokens.add(token)
            folded = self._fold_text(token)
            if len(folded) > 1 and folded not in STOPWORDS:
                expanded_tokens.add(folded)
        return expanded_tokens

    def lexical_overlap(self, query: str, content: str) -> float:
        query_tokens = self.tokenize(query)
        content_tokens = self.tokenize(content)
        if not query_tokens or not content_tokens:
            return 0.0
        overlap = len(query_tokens & content_tokens)
        return overlap / len(query_tokens)

    @staticmethod
    def _fold_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
        return "".join(char for char in normalized if not unicodedata.combining(char)).lower()
