from __future__ import annotations

from io import BytesIO
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader


DATA_DIR = Path("data")

DOCS: list[dict[str, str]] = [
    {
        "filename": "luat-thue-thu-nhap-ca-nhan-109-2025-qh15.txt",
        "title": "Luật Thuế thu nhập cá nhân 109/2025/QH15",
        "url": "https://congbaocdn.chinhphu.vn/180507251028987904/2026/1/24/109signed-17692403594311667615452.pdf",
        "format": "pdf",
    },
    {
        "filename": "nghi-quyet-110-2025-ubtvqh15-giam-tru-gia-canh.txt",
        "title": "Nghị quyết 110/2025/UBTVQH15 điều chỉnh mức giảm trừ gia cảnh",
        "url": "https://xaydungchinhsach.chinhphu.vn/nghi-quyet-110-2025-ubtvqh15-dieu-chinh-muc-giam-tru-gia-canh-cua-thue-thu-nhap-ca-nhan-119251110101313787.htm",
        "format": "html",
    },
    {
        "filename": "vbhn-thue-thu-nhap-ca-nhan-2007-2012.txt",
        "title": "Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2012/12/17546/12276-1-2012777-778-08vbhn-vpqhpdf",
        "format": "pdf",
    },
    {
        "filename": "nghi-dinh-65-2013-nd-cp-thue-thu-nhap-ca-nhan.txt",
        "title": "Nghị định 65/2013/NĐ-CP hướng dẫn Luật Thuế thu nhập cá nhân",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2013/6/4403/3203-1-2013401-402-652013nd-cppdf",
        "format": "pdf",
    },
    {
        "filename": "thong-tu-111-2013-tt-btc-thue-thu-nhap-ca-nhan.txt",
        "title": "Thông tư 111/2013/TT-BTC hướng dẫn thuế thu nhập cá nhân",
        "url": "https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2013/8/7822/4293-1-2013563-564-1112013tt-btcpdf",
        "format": "pdf",
    },
]


def parse_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page.strip() for page in pages if page.strip())


def parse_html(content: bytes) -> str:
    soup = BeautifulSoup(content.decode("utf-8"), "html.parser")
    main = soup.select_one('[data-role="content"]') or soup.find("article") or soup.find("main") or soup
    for selector in [".VCSortableInPreviewMode", ".box-relax", ".detail__sm-bottom", "script", "style"]:
        for element in main.select(selector):
            element.decompose()
    return main.get_text("\n", strip=True)


def normalize_text(title: str, url: str, raw_text: str) -> str:
    body = "\n".join(line.strip() for line in raw_text.splitlines() if line.strip())
    return f"{title}\n\nNguồn: {url}\n\n{body}\n"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0, follow_redirects=True, verify=False) as client:
        for doc in DOCS:
            response = client.get(doc["url"])
            response.raise_for_status()
            if doc["format"] == "pdf":
                raw_text = parse_pdf(response.content)
            else:
                raw_text = parse_html(response.content)
            if not raw_text.strip():
                raise RuntimeError(f"Could not extract text from {doc['url']}")
            output = DATA_DIR / doc["filename"]
            output.write_text(
                normalize_text(doc["title"], doc["url"], raw_text),
                encoding="utf-8",
            )
            print(f"Wrote {output}")


if __name__ == "__main__":
    main()
