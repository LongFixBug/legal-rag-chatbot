from __future__ import annotations

from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


class DocumentParserService:
    def parse_uploaded_file(self, filename: str, content: bytes) -> str:
        extension = Path(filename).suffix.lower()
        if extension in {".txt", ".md"}:
            return self._decode_text(content)
        if extension in {".html", ".htm"}:
            return self._parse_html(content)
        if extension == ".pdf":
            return self._parse_pdf(content)
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")

    @staticmethod
    def _decode_text(content: bytes) -> str:
        text = content.decode("utf-8")
        if not text.strip():
            raise ValueError("Uploaded text file is empty")
        return text

    @staticmethod
    def _parse_html(content: bytes) -> str:
        soup = BeautifulSoup(content.decode("utf-8"), "html.parser")
        text = soup.get_text("\n", strip=True)
        if not text.strip():
            raise ValueError("Uploaded HTML file does not contain readable text")
        return text

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        reader = PdfReader(BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(page.strip() for page in pages if page.strip())
        if not text.strip():
            raise ValueError("Uploaded PDF file does not contain extractable text")
        return text
