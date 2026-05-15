from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "evals" / "generated_candidates.json"

ARTICLE_PATTERN = re.compile(r"(?=Điều\s+\d+[A-Za-z0-9-]*[\.:])", re.IGNORECASE)
ARTICLE_LABEL_PATTERN = re.compile(r"^(Điều\s+\d+[A-Za-z0-9-]*)", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*\s*(?:triệu|tỷ|nghìn|%|phần trăm|đồng|năm|tháng|ngày|mức|kg|ha|km)", re.IGNORECASE)

IMPORTANT_TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("calculation", ("thuế", "mức", "tỷ lệ", "thu nhập tính thuế", "giảm trừ", "miễn thuế", "giảm thuế", "thuế suất", "tính thuế", "căn cứ tính")),
    ("condition", ("điều kiện", "đáp ứng", "trường hợp", "không được", "bị cấm", "cấm", "hạn chế", "không áp dụng")),
    ("procedure", ("hồ sơ", "thủ tục", "khai", "đăng ký", "quyết toán", "kê khai", "nộp hồ sơ", "hoàn thuế")),
    ("rights", ("quyền", "nghĩa vụ", "trách nhiệm", "được phép", "quyền hạn")),
    ("definition", ("giải thích từ ngữ", "bao gồm", "là tổ chức", "là cá nhân", "được hiểu")),
    ("obligation", ("phải nộp", "có trách nhiệm", "nghĩa vụ", "người nộp thuế", "đối tượng", "phạm vi")),
)

PARAPHRASE_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("calculation", "{article} của {title} quy định mức hoặc cách tính như thế nào?"),
    ("calculation", "Cho tôi biết {article} của {title} quy định về thuế suất và cách tính?"),
    ("calculation", "{article} trong {title} nói gì về mức và cách tính?"),
    ("condition", "{article} của {title} quy định những điều kiện gì?"),
    ("condition", "Những trường hợp nào được áp dụng {article} của {title}?"),
    ("condition", "{article} trong {title} áp dụng cho đối tượng nào?"),
    ("rights", "{article} của {title} quy định quyền gì?"),
    ("rights", "Theo {article} của {title}, tổ chức cá nhân có những quyền gì?"),
    ("rights", "{article} trong {title} quy định trách nhiệm ra sao?"),
    ("obligation", "{article} của {title} quy định nghĩa vụ gì?"),
    ("obligation", "Ai là đối tượng phải nộp thuế theo {article} của {title}?"),
    ("definition", "{article} của {title} định nghĩa những gì?"),
    ("definition", "{article} trong {title} giải thích các thuật ngữ nào?"),
    ("procedure", "{article} của {title} quy định thủ tục như thế nào?"),
    ("procedure", "Hồ sơ thủ tục theo {article} của {title} gồm những gì?"),
)


def fold_text(text: str) -> str:
    replacements = str.maketrans({"đ": "d", "Đ": "D"})
    normalized = unicodedata.normalize("NFKD", text.translate(replacements))
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def slugify(text: str, max_words: int = 6) -> str:
    words = WORD_PATTERN.findall(fold_text(text))
    useful_words = [word for word in words if len(word) > 1 or word.isdigit()][:max_words]
    return "_".join(useful_words) or "eval_case"


def guess_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("http") and len(stripped) > 3:
            return stripped
    return fallback


def split_articles(content: str) -> list[str]:
    parts = [part.strip() for part in ARTICLE_PATTERN.split(content) if part.strip()]
    return parts or [content.strip()]


def extract_article_label(article_text: str) -> str | None:
    match = ARTICLE_LABEL_PATTERN.search(article_text.strip())
    return match.group(1).strip() if match else None


def classify_topic(article_text: str) -> tuple[str, int]:
    folded = fold_text(article_text)
    best_topic = "general"
    best_score = 0
    for topic, keywords in IMPORTANT_TOPICS:
        score = sum(1 for keyword in keywords if fold_text(keyword) in folded)
        if score > best_score:
            best_topic = topic
            best_score = score
    return best_topic, best_score


def has_numbers(article_text: str) -> bool:
    return bool(NUMBER_PATTERN.search(article_text))


def infer_group(title: str, article_text: str) -> str:
    folded = fold_text(f"{title} {article_text}")
    if "thue" in folded or "thu nhap ca nhan" in folded:
        return "tax.generated"
    if "lao dong" in folded:
        return "labor.generated"
    if "doanh nghiep" in folded:
        return "business.generated"
    if "dau tu" in folded:
        return "investment.generated"
    return "legal.generated"


def build_question(candidate: ArticleCandidate) -> str:
    title = candidate.title
    article = candidate.article
    folded = fold_text(candidate.content)
    if candidate.topic == "calculation":
        if "giam tru gia canh" in folded:
            return f"{article} của {title} quy định mức giảm trừ gia cảnh như thế nào?"
        if "giam thue" in folded:
            return f"{article} của {title} quy định giảm thuế trong trường hợp nào?"
        return f"{article} của {title} quy định cách tính hoặc mức áp dụng như thế nào?"
    if candidate.topic == "condition":
        if "cam" in folded or "khong duoc" in folded:
            return f"{article} của {title} quy định những trường hợp nào bị cấm hoặc không được thực hiện?"
        return f"{article} của {title} quy định điều kiện áp dụng như thế nào?"
    if candidate.topic == "procedure":
        return f"{article} của {title} quy định hồ sơ hoặc thủ tục như thế nào?"
    if candidate.topic == "rights":
        return f"{article} của {title} quy định quyền, nghĩa vụ hoặc trách nhiệm gì?"
    if candidate.topic == "obligation":
        return f"{article} của {title} quy định đối tượng và nghĩa vụ gì?"
    if candidate.topic == "definition":
        return f"{article} của {title} giải thích hoặc định nghĩa nội dung gì?"
    return f"{article} của {title} quy định gì?"


def build_variant_question(candidate: ArticleCandidate, template: str) -> str:
    return template.format(article=candidate.article, title=candidate.title)


_WS_COLLAPSE = re.compile(r"\s+")


def _normalize_whitespace(text: str) -> str:
    collapsed = _WS_COLLAPSE.sub(" ", text).strip()
    return collapsed


def representative_phrase(article_text: str) -> str:
    cleaned = _normalize_whitespace(article_text)
    lowered = cleaned.lower()
    priority_keywords = (
        "giảm trừ gia cảnh", "giảm thuế", "không được", "cấm", "bị cấm",
        "quyền", "nghĩa vụ", "bao gồm", "người nộp thuế", "thu nhập chịu thuế",
        "thuế suất", "miễn thuế", "trúng thưởng", "thừa kế", "quà tặng",
        "thu nhập tính thuế", "khấu trừ", "hoàn thuế",
    )
    for keyword in priority_keywords:
        index = lowered.find(keyword)
        if index >= 0:
            sentence_start = max(cleaned.rfind(".", 0, index), cleaned.rfind(";", 0, index), 0)
            if cleaned[sentence_start:sentence_start + 1] in (".", ";", " "):
                sentence_start += 1
            sentence_end_candidates = [pos for pos in (cleaned.find(".", index + 20), cleaned.find(";", index + 20)) if pos != -1]
            sentence_end = min(sentence_end_candidates) + 1 if sentence_end_candidates else min(index + 120, len(cleaned))
            phrase = cleaned[sentence_start:sentence_end].strip().lstrip(".,; ")
            return phrase[:100].strip()
    return cleaned[:60].strip()


def _extract_first_key_sentence(article_text: str) -> str:
    cleaned = _normalize_whitespace(article_text)
    sentences = re.split(r"(?<=[\.;])\s+", cleaned)
    for sentence in sentences:
        if len(sentence) > 20:
            return sentence.strip()[:80]
    return cleaned[:60].strip()


@dataclass(frozen=True)
class ArticleCandidate:
    title: str
    source_file: str
    article: str
    content: str
    topic: str
    score: int
    has_calculations: bool = False


def collect_candidates(file_path: Path, max_per_file: int) -> list[ArticleCandidate]:
    content = file_path.read_text(encoding="utf-8")
    title = guess_title(content, file_path.stem.replace("-", " ").title())
    candidates: list[ArticleCandidate] = []
    for article_text in split_articles(content):
        article = extract_article_label(article_text)
        if not article:
            continue
        topic, topic_score = classify_topic(article_text)
        score = topic_score + min(len(article_text) // 1200, 3)
        candidates.append(
            ArticleCandidate(
                title=title,
                source_file=file_path.name,
                article=article,
                content=article_text,
                topic=topic,
                score=score,
                has_calculations=has_numbers(article_text) and topic == "calculation",
            )
        )
    candidates.sort(key=lambda value: (value.score, value.article), reverse=True)
    return candidates[:max_per_file]


def _select_variant_templates(topic: str) -> list[str]:
    matching = [t for t in PARAPHRASE_TEMPLATES if t[0] == topic]
    return [t[1] for t in matching[:3]]


def build_eval_cases(candidates: list[ArticleCandidate], variants_per_candidate: int = 2) -> dict[str, list[dict]]:
    retrieval_cases: list[dict] = []
    answer_cases: list[dict] = []
    calculation_cases: list[dict] = []
    seen_ids: set[str] = set()

    for candidate in candidates:
        group = infer_group(candidate.title, candidate.content)
        base_id = f"{group}.{slugify(candidate.title, 4)}.{slugify(candidate.article, 3)}.{candidate.topic}"

        case_id = base_id
        suffix = 2
        while case_id in seen_ids:
            case_id = f"{base_id}_{suffix}"
            suffix += 1

        question = build_question(candidate)
        phrase = representative_phrase(candidate.content)
        if len(phrase) < 15:
            phrase = _extract_first_key_sentence(candidate.content)
        short_phrase = _normalize_whitespace(phrase[:60])

        retrieval_cases.append(
            {
                "id": f"{case_id}.retrieval",
                "group": group,
                "question": question,
                "seed_files": [candidate.source_file],
                "top_k": 5,
                "expected_any": {
                    "title_contains": candidate.title,
                    "article": candidate.article,
                    "excerpt_contains": phrase,
                },
                "draft": True,
            }
        )

        answer_cases.append(
            {
                "id": f"{case_id}.answer",
                "group": group,
                "question": question,
                "seed_files": [candidate.source_file],
                "must_include": [candidate.article],
                "must_not_include": ["Chưa có căn cứ", "Dựa trên các văn bản đã nạp"],
                "draft": True,
            }
        )

        seen_ids.add(case_id)

        if candidate.has_calculations:
            calc_id = f"{case_id}.calc"
            while calc_id in seen_ids:
                calc_id = f"{calc_id}_2"
            calculation_cases.append(
                {
                    "id": calc_id,
                    "group": group,
                    "question": question,
                    "seed_files": [candidate.source_file],
                    "must_include": [candidate.article],
                    "must_not_include": ["Chưa có căn cứ", "Chưa đủ dữ liệu"],
                    "draft": True,
                }
            )
            seen_ids.add(calc_id)

        variant_templates = _select_variant_templates(candidate.topic)
        for vi, template in enumerate(variant_templates[:variants_per_candidate]):
            variant_question = build_variant_question(candidate, template)
            variant_id = f"{case_id}.v{vi + 1}"
            while variant_id in seen_ids:
                variant_id = f"{variant_id}_alt"
            retrieval_cases.append(
                {
                    "id": f"{variant_id}.retrieval",
                    "group": group,
                    "question": variant_question,
                    "seed_files": [candidate.source_file],
                    "top_k": 5,
                    "expected_any": {
                        "title_contains": candidate.title,
                        "article": candidate.article,
                        "excerpt_contains": phrase,
                    },
                    "draft": True,
                }
            )
            answer_cases.append(
                {
                    "id": f"{variant_id}.answer",
                    "group": group,
                    "question": variant_question,
                    "seed_files": [candidate.source_file],
                    "must_include": [candidate.article],
                    "must_not_include": ["Chưa có căn cứ", "Dựa trên các văn bản đã nạp"],
                    "draft": True,
                }
            )
            seen_ids.add(variant_id)

    return {
        "retrieval": retrieval_cases,
        "answer": answer_cases,
        "calculation": calculation_cases,
    }


def generate_candidates(data_dir: Path, filenames: list[str], max_per_file: int, variants: int) -> dict[str, list[dict]]:
    if filenames:
        file_paths = [data_dir / filename for filename in filenames]
    else:
        file_paths = sorted(
            path for path in data_dir.glob("*.txt")
            if path.name.lower() != "readme.txt" and not path.name.lower().startswith("readme")
        )

    candidates: list[ArticleCandidate] = []
    for file_path in file_paths:
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
        candidates.extend(collect_candidates(file_path, max_per_file=max_per_file))

    return build_eval_cases(candidates, variants_per_candidate=variants)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate draft legal RAG eval cases from local legal text files (v2).")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory containing legal .txt files.")
    parser.add_argument("--file", action="append", default=[], help="Specific data filename to scan. Can be repeated.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output JSON path for draft candidates.")
    parser.add_argument("--max-per-file", type=int, default=20, help="Maximum candidate articles to generate per file.")
    parser.add_argument("--variants", type=int, default=2, help="Number of paraphrase variants per candidate.")
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout instead of writing the output file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = generate_candidates(args.data_dir, args.file, args.max_per_file, args.variants)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.stdout:
        print(rendered)
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered + "\n", encoding="utf-8")
    retrieval_count = len(payload.get("retrieval", []))
    answer_count = len(payload.get("answer", []))
    calculation_count = len(payload.get("calculation", []))
    print(f"Generated {retrieval_count} retrieval, {answer_count} answer, {calculation_count} calculation cases -> {args.out}")


if __name__ == "__main__":
    main()
