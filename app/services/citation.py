from __future__ import annotations

import re

ARTICLE_PATTERN = re.compile(r"(?:điều|dieu)\s*(\d+[A-Za-z0-9-]*)", re.IGNORECASE)
CLAUSE_PATTERN = re.compile(r"(?:khoản|khoan)\s*(\d+)", re.IGNORECASE)
POINT_PATTERN = re.compile(r"(?:điểm|diem)\s*([a-z])", re.IGNORECASE)


class CitationService:
    def extract_references(self, text: str) -> list[str]:
        refs = [f"Điều {value}" for value in ARTICLE_PATTERN.findall(text)]
        refs.extend(f"khoản {value}" for value in CLAUSE_PATTERN.findall(text))
        refs.extend(f"điểm {value.lower()}" for value in POINT_PATTERN.findall(text))
        deduped: list[str] = []
        for item in refs:
            normalized = item.strip()
            if normalized not in deduped:
                deduped.append(normalized)
        return deduped

    def extract_primary_article(self, text: str) -> str | None:
        match = ARTICLE_PATTERN.search(text)
        return f"Điều {match.group(1)}" if match else None

    def extract_primary_clause(self, text: str) -> str | None:
        match = CLAUSE_PATTERN.search(text)
        return f"khoản {match.group(1)}" if match else None

    def validate_answer_citations(self, answer: str, contexts: list[dict]) -> list[str]:
        referenced_articles = {ref for ref in self.extract_references(answer) if ref.lower().startswith("điều")}
        available_articles = {item.get("article") for item in contexts if item.get("article")}
        invalid_articles = sorted(article for article in referenced_articles if article not in available_articles)
        warnings: list[str] = []
        if invalid_articles:
            warnings.append(
                "Các dẫn chiếu sau xuất hiện trong câu trả lời nhưng không có trong ngữ cảnh truy xuất: "
                + ", ".join(invalid_articles)
            )
        return warnings
