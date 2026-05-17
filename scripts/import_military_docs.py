from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "nghia-vu-quan-su"


@dataclass(frozen=True)
class MilitarySource:
    filename: str
    url: str
    min_size_bytes: int
    extract_text: bool = False


SOURCES = (
    MilitarySource(
        filename="80-vbhn-vpqh-luat-nghia-vu-quan-su.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/8/45896/58326-1-20251119-112080-vbhn-vpqh.pdf",
        min_size_bytes=500_000,
        extract_text=True,
    ),
    MilitarySource(
        filename="98-2025-qh15-sua-doi-quan-su-quoc-phong.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/6/45533/57621-1-2025957-95898-2025-qh15.pdf",
        min_size_bytes=300_000,
        extract_text=True,
    ),
    MilitarySource(
        filename="36-vbhn-bqp-tuyen-chon-goi-nhap-ngu.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/8/45994/58570-1-20251251-125236-vbhn-bqp.pdf",
        min_size_bytes=1_000_000,
    ),
    MilitarySource(
        filename="88-vbhn-bqp-kham-suc-khoe-part1.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/11/46656/59892-1-20251641-164288-vbhn-bqp.pdf",
        min_size_bytes=500_000,
        extract_text=True,
    ),
    MilitarySource(
        filename="88-vbhn-bqp-kham-suc-khoe-part2.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/11/46656/59895-1-20251643-164488-vbhn-bqp.pdf",
        min_size_bytes=300_000,
        extract_text=True,
    ),
    MilitarySource(
        filename="75-vbhn-bqp-dang-ky-kham-suc-khoe.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/10/46339/59245-1-20251459-146075-vbhn-bqp.pdf",
        min_size_bytes=1_000_000,
    ),
    MilitarySource(
        filename="76-vbhn-bqp-cong-dan-nu-thoi-chien-du-bi.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/10/46340/59247-1-20251459-146076-vbhn-bqp.pdf",
        min_size_bytes=1_000_000,
    ),
    MilitarySource(
        filename="40-vbhn-bqp-che-do-chinh-sach-binh-si.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2025/8/46088/58733-1-20251307-130840-vbhn-bqp.pdf",
        min_size_bytes=1_000_000,
    ),
    MilitarySource(
        filename="04-vbhn-bqp-xu-phat-quoc-phong-co-yeu.pdf",
        url="https://congbaocdn.chinhphu.vn/CongBaoCP/VanBan/2022/8/37697/41554-1-2022695-69604-vbhn-bqp.pdf",
        min_size_bytes=1_000_000,
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(source: MilitarySource, raw_dir: Path, force: bool) -> Path:
    destination = raw_dir / source.filename
    if destination.exists() and not force:
        return destination
    with urllib.request.urlopen(source.url, timeout=120) as response:
        payload = response.read()
    if len(payload) < source.min_size_bytes:
        raise RuntimeError(f"{source.filename} looked too small: {len(payload)} bytes")
    destination.write_bytes(payload)
    return destination


def extract_text(pdf_path: Path) -> Path | None:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return None
    output_path = pdf_path.with_name(f"text-{pdf_path.stem}.txt")
    subprocess.run([pdftotext, "-layout", str(pdf_path), str(output_path)], check=True)
    text = output_path.read_text(encoding="utf-8", errors="ignore")
    if len(text.strip()) < 2_000:
        output_path.rename(pdf_path.with_name(f"extracted-{pdf_path.stem}.txt"))
        return None
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download official Vietnamese military-service-law source PDFs.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="Directory where raw PDFs are stored.")
    parser.add_argument("--force", action="store_true", help="Download again even if files already exist.")
    parser.add_argument("--extract-text", action="store_true", help="Also run pdftotext for sources with a usable text layer.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        path = download(source, args.raw_dir, force=args.force)
        print(f"{path.name}: {path.stat().st_size} bytes sha256={sha256(path)[:16]}")
        if args.extract_text and source.extract_text:
            text_path = extract_text(path)
            if text_path:
                print(f"  extracted text: {text_path.name}")
            else:
                print("  text extraction skipped or marked low quality")


if __name__ == "__main__":
    main()
