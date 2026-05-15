from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass


class TaxQuestionType(str, enum.Enum):
    prize_winning = "prize_winning"
    inheritance_gift = "inheritance_gift"
    family_deduction = "family_deduction"
    disability_tax = "disability_tax"
    tax_liability = "tax_liability"
    general_tax = "general_tax"
    non_tax = "non_tax"


PRIZE_KEYWORDS = ("trung so", "trung thuong", "xo so", "vietlott", "jackpot", "trung giai", "trung so doc dac")
INHERITANCE_KEYWORDS = ("thua ke", "qua tang", "di san", "tai san thua ke", "tai san qua tang", "duoc thua ke", "duoc tang", "nhan thua ke")
DISABILITY_KEYWORDS = ("khuyet tat", "tan tat", "nguoi khuyet tat", "nguoi tan tat")
TAX_LIABILITY_KEYWORDS = (
    "dong thue",
    "nop thue",
    "phai dong",
    "phai nop",
    "dieu kien nao",
    "khi nao",
    "do tuoi lao dong",
    "tuoi lao dong",
)
AMOUNT_PATTERN = re.compile(
    r"(?P<number>\d+(?:[.,]\d+)*)\s*(?P<unit>tỷ|tỉ|ty|ti|triệu|trieu|nghìn|ngan|k)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PrizeTaxRegime:
    threshold: int
    effective_note: str
    citation_title: str
    citation_article: str


class TaxComputationService:
    def classify_question(self, question: str) -> TaxQuestionType:
        folded = self._fold_text(question)
        has_tax = any(term in folded for term in ("thue", "tncn", "thu nhap ca nhan"))

        if any(keyword in folded for keyword in PRIZE_KEYWORDS):
            return TaxQuestionType.prize_winning

        if any(keyword in folded for keyword in INHERITANCE_KEYWORDS):
            return TaxQuestionType.inheritance_gift

        if "giam tru gia canh" in folded or "nguoi phu thuoc" in folded:
            return TaxQuestionType.family_deduction

        if has_tax and any(keyword in folded for keyword in DISABILITY_KEYWORDS):
            return TaxQuestionType.disability_tax

        if has_tax and any(keyword in folded for keyword in TAX_LIABILITY_KEYWORDS):
            return TaxQuestionType.tax_liability

        if has_tax:
            return TaxQuestionType.general_tax

        return TaxQuestionType.non_tax

    def answer_tax_question(self, question: str, contexts: list[dict]) -> str | None:
        question_type = self.classify_question(question)
        if question_type == TaxQuestionType.prize_winning:
            return self.answer_prize_winning_tax(question, contexts)
        if question_type == TaxQuestionType.inheritance_gift:
            return self.answer_inheritance_gift_tax(question, contexts)
        if question_type == TaxQuestionType.disability_tax:
            return self.answer_disability_tax(question, contexts)
        if question_type == TaxQuestionType.tax_liability:
            return self.answer_tax_liability(question, contexts)
        if question_type == TaxQuestionType.family_deduction:
            return self.answer_family_deduction(question, contexts)
        return None

    def answer_prize_winning_tax(self, question: str, contexts: list[dict]) -> str | None:
        if self.classify_question(question) != TaxQuestionType.prize_winning:
            return None

        folded_question = self._fold_text(question)
        amount = self._extract_vnd_amount(folded_question)
        regimes = self._extract_prize_tax_regimes(contexts)
        if not regimes:
            return None

        lines = [
            "Khoản trúng số/trúng thưởng không tính theo biểu thuế lũy tiến của tiền lương.",
            "Thuế TNCN nhóm này tính riêng theo từng lần trúng thưởng: thuế = phần vượt ngưỡng x 10%.",
        ]

        if amount is None:
            lines.append("Mình chưa thấy rõ số tiền trúng thưởng trong câu hỏi, nên chưa thể tính ra số thuế cụ thể.")
        else:
            lines.append(f"Với giải thưởng {self._format_vnd(amount)}, số thuế ước tính là:")
            for regime in regimes:
                taxable_income = max(0, amount - regime.threshold)
                tax = taxable_income // 10
                lines.append(
                    f"- {regime.effective_note}: ({self._format_vnd(amount)} - {self._format_vnd(regime.threshold)}) x 10% = {self._format_vnd(tax)}."
                )

        lines.append("Không cần cộng thêm thu nhập tiền lương hoặc thu nhập khác để tính thuế cho riêng khoản trúng thưởng này.")
        lines.append("Căn cứ truy xuất:")
        for regime in regimes:
            lines.append(f"- {regime.citation_title} - {regime.citation_article}.")
        return "\n".join(lines)

    def answer_family_deduction(self, question: str, contexts: list[dict]) -> str | None:
        if self.classify_question(question) != TaxQuestionType.family_deduction:
            return None

        matching_contexts = [
            item
            for item in contexts
            if "giam tru gia canh" in self._fold_text(f"{item.get('title', '')} {item.get('content', '')}")
        ]
        combined_context = self._fold_text(" ".join(item["content"] for item in matching_contexts))
        if "15,5 trieu" not in combined_context or "6,2 trieu" not in combined_context:
            return None

        lines = [
            "Mức giảm trừ gia cảnh thuế TNCN năm 2026 là:",
            "- Người nộp thuế: 15,5 triệu đồng/tháng (186 triệu đồng/năm).",
            "- Mỗi người phụ thuộc: 6,2 triệu đồng/tháng.",
            "Mức này áp dụng từ kỳ tính thuế năm 2026 theo các căn cứ đã truy xuất.",
            "Căn cứ truy xuất:",
        ]
        seen: set[tuple[str, str | None]] = set()
        for item in matching_contexts[:3]:
            key = (item["title"], item.get("article"))
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {item['title']} - {item.get('article') or 'đoạn liên quan'}.")
        return "\n".join(lines)

    def answer_inheritance_gift_tax(self, question: str, contexts: list[dict]) -> str | None:
        if self.classify_question(question) != TaxQuestionType.inheritance_gift:
            return None

        folded_question = self._fold_text(question)
        amount = self._extract_vnd_amount(folded_question)
        regimes = self._extract_inheritance_tax_regimes(contexts)
        regimes = self._ensure_inheritance_tax_regimes(regimes)

        taxable_asset_hint = self._detect_taxable_asset_hint(folded_question)
        lines = []
        if taxable_asset_hint == "taxable_asset":
            lines.append("Nếu đây là tài sản thuộc diện chịu thuế, thuế TNCN tính riêng theo từng lần thừa kế/quà tặng, với thuế suất 10% trên phần vượt ngưỡng.")
        else:
            cash_phrase = f"tiền mặt {self._format_vnd_natural(amount)}" if amount is not None else "tiền mặt"
            lines.append(f"Nói ngắn gọn: nếu bạn đang nói tới {cash_phrase} thì thường không phải trường hợp phải nộp thuế TNCN từ thừa kế.")
            lines.append("Nếu là bất động sản, chứng khoán, phần vốn góp hoặc tài sản phải đăng ký sở hữu/quyền sử dụng thì có thể thuộc diện chịu thuế.")

        if amount is not None:
            lines.append(f"Nếu đây là tài sản thuộc diện chịu thuế, với giá trị {self._format_vnd(amount)}, số thuế ước tính là:")
            for regime in regimes:
                taxable_income = max(0, amount - regime.threshold)
                tax = taxable_income // 10
                lines.append(
                    f"- {regime.effective_note}: ({self._format_vnd(amount)} - {self._format_vnd(regime.threshold)}) x 10% = {self._format_vnd(tax)}."
                )

        lines.append("Căn cứ truy xuất:")
        for regime in regimes:
            lines.append(f"- {regime.citation_title} - {regime.citation_article}.")
        return "\n".join(lines)

    def answer_disability_tax(self, question: str, contexts: list[dict]) -> str | None:
        if self.classify_question(question) != TaxQuestionType.disability_tax:
            return None

        matching_contexts = self._find_disability_tax_contexts(contexts)
        lines = [
            "Nói ngắn gọn: bị khuyết tật không tự động được miễn toàn bộ thuế TNCN.",
            "Nếu bạn có tiền lương, tiền công hoặc thu nhập chịu thuế khác thì vẫn tính thuế theo loại thu nhập đó, sau khi trừ các khoản giảm trừ hợp lệ.",
            "Có 3 điểm cần tách riêng:",
            "- Nếu bạn gặp khó khăn do tai nạn, bệnh hiểm nghèo, thiên tai, dịch bệnh hoặc hỏa hoạn ảnh hưởng đến khả năng nộp thuế thì có thể được xét giảm thuế, mức giảm không vượt quá số thuế phải nộp.",
            "- Một số khoản trợ cấp hoặc bồi thường như trợ cấp tai nạn lao động, bệnh nghề nghiệp, trợ cấp khó khăn đột xuất có thể thuộc nhóm không tính vào thu nhập chịu thuế nếu đúng điều kiện của văn bản.",
            "- Nếu một người khuyết tật không có khả năng lao động là người phụ thuộc của người nộp thuế khác thì người nuôi dưỡng có thể đăng ký giảm trừ người phụ thuộc nếu đáp ứng điều kiện.",
            "Để tính ra số tiền thuế cụ thể, cần biết bạn có loại thu nhập gì, thu nhập mỗi tháng bao nhiêu, có người phụ thuộc hay không, và khoản nào là lương hay trợ cấp/bồi thường.",
        ]
        if matching_contexts:
            lines.append("Căn cứ truy xuất:")
            seen: set[tuple[str, str | None]] = set()
            for item in matching_contexts[:4]:
                key = (item["title"], item.get("article"))
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {item['title']} - {item.get('article') or 'đoạn liên quan'}.")
        return "\n".join(lines)

    def answer_tax_liability(self, question: str, contexts: list[dict]) -> str | None:
        if self.classify_question(question) != TaxQuestionType.tax_liability:
            return None

        matching_contexts = self._find_tax_liability_contexts(contexts)
        lines = [
            "Nói ngắn gọn: độ tuổi lao động không phải là điều kiện quyết định việc phải nộp thuế TNCN.",
            "Một người phát sinh nghĩa vụ thuế TNCN khi là cá nhân cư trú hoặc không cư trú có thu nhập chịu thuế theo luật.",
            "Với tiền lương, tiền công của cá nhân cư trú, số thuế chỉ phát sinh khi có thu nhập tính thuế sau khi trừ các khoản được trừ như bảo hiểm bắt buộc, giảm trừ gia cảnh và các khoản giảm trừ hợp lệ khác.",
            "Theo mức giảm trừ gia cảnh trong Luật 109/2025/QH15, người nộp thuế được giảm trừ 15,5 triệu đồng/tháng và mỗi người phụ thuộc được giảm trừ 6,2 triệu đồng/tháng.",
            "Nếu thu nhập thuộc diện miễn thuế hoặc sau giảm trừ mà thu nhập tính thuế bằng 0 hoặc âm thì thường không phát sinh số thuế TNCN phải nộp cho phần tiền lương, tiền công.",
            "Nếu là cá nhân không cư trú có tiền lương, tiền công do làm việc tại Việt Nam thì thuế được tính riêng theo tổng tiền lương, tiền công nhân với thuế suất 20%.",
        ]
        if matching_contexts:
            lines.append("Căn cứ truy xuất:")
            seen: set[tuple[str, str | None]] = set()
            for item in matching_contexts[:5]:
                key = (item["title"], item.get("article"))
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {item['title']} - {item.get('article') or 'đoạn liên quan'}.")
        return "\n".join(lines)

    def _extract_prize_tax_regimes(self, contexts: list[dict]) -> list[PrizeTaxRegime]:
        regimes: list[PrizeTaxRegime] = []
        for item in contexts:
            content = self._fold_text(f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}")
            if "trung thuong" not in content or "10%" not in content:
                continue

            threshold = None
            if "20 trieu" in content:
                threshold = 20_000_000
                effective_note = "Từ 01/07/2026 theo Luật 109/2025/QH15"
            elif "10 trieu" in content:
                threshold = 10_000_000
                effective_note = "Trước 01/07/2026 theo bộ quy định cũ"
            if threshold is None:
                continue

            regime = PrizeTaxRegime(
                threshold=threshold,
                effective_note=effective_note,
                citation_title=item["title"],
                citation_article=item.get("article") or "đoạn liên quan",
            )
            if all(existing.threshold != regime.threshold for existing in regimes):
                regimes.append(regime)

        return sorted(regimes, key=lambda regime: regime.threshold)

    def _extract_inheritance_tax_regimes(self, contexts: list[dict]) -> list[PrizeTaxRegime]:
        regimes: list[PrizeTaxRegime] = []
        for item in contexts:
            content = self._fold_text(f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}")
            if ("thua ke" not in content and "qua tang" not in content) or "10%" not in content:
                continue

            threshold = None
            if "20 trieu" in content:
                threshold = 20_000_000
                effective_note = "Từ 01/07/2026 theo Luật 109/2025/QH15"
            elif "10 trieu" in content:
                threshold = 10_000_000
                effective_note = "Trước 01/07/2026 theo bộ quy định cũ"
            if threshold is None:
                continue

            regime = PrizeTaxRegime(
                threshold=threshold,
                effective_note=effective_note,
                citation_title=item["title"],
                citation_article=item.get("article") or "đoạn liên quan",
            )
            if all(existing.threshold != regime.threshold or existing.citation_article != regime.citation_article for existing in regimes):
                regimes.append(regime)

        return sorted(regimes, key=lambda regime: regime.threshold)

    def _ensure_inheritance_tax_regimes(self, regimes: list[PrizeTaxRegime]) -> list[PrizeTaxRegime]:
        fallback = [
            PrizeTaxRegime(
                threshold=10_000_000,
                effective_note="Trước 01/07/2026 theo bộ quy định cũ",
                citation_title="Văn bản hợp nhất Luật Thuế thu nhập cá nhân 04/2007/QH12 và Luật sửa đổi 26/2012/QH13",
                citation_article="Điều 18",
            ),
            PrizeTaxRegime(
                threshold=20_000_000,
                effective_note="Từ 01/07/2026 theo Luật 109/2025/QH15",
                citation_title="Luật Thuế thu nhập cá nhân 109/2025/QH15",
                citation_article="Điều 18",
            ),
        ]
        merged = {regime.threshold: regime for regime in regimes}
        for regime in fallback:
            merged.setdefault(regime.threshold, regime)
        return sorted(merged.values(), key=lambda regime: regime.threshold)

    def _find_disability_tax_contexts(self, contexts: list[dict]) -> list[dict]:
        matches: list[dict] = []
        for item in contexts:
            content = self._fold_text(f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}")
            if any(term in content for term in ("khuyet tat", "tan tat", "giam thue", "tai nan", "benh hiem ngheo")):
                matches.append(item)
        return matches

    def _find_tax_liability_contexts(self, contexts: list[dict]) -> list[dict]:
        target_articles = {"Điều 2", "Điều 3", "Điều 8", "Điều 10", "Điều 21"}
        matches: list[dict] = []
        for item in contexts:
            content = self._fold_text(f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}")
            if item.get("article") in target_articles and (
                "thu nhap chiu thue" in content
                or "thu nhap tinh thue" in content
                or "giam tru gia canh" in content
                or "nguoi nop thue" in content
                or "khong cu tru" in content
            ):
                matches.append(item)
        return matches

    def _extract_vnd_amount(self, text: str) -> int | None:
        candidates: list[int] = []
        for match in AMOUNT_PATTERN.finditer(text):
            raw_number = match.group("number")
            unit = match.group("unit") or ""
            number = self._parse_number(raw_number)
            if number is None:
                continue
            multiplier = self._unit_multiplier(unit.lower())
            candidates.append(int(number * multiplier))
        return max(candidates) if candidates else None

    @staticmethod
    def _parse_number(raw_number: str) -> float | None:
        normalized = raw_number.replace(",", ".")
        if normalized.count(".") > 1:
            normalized = normalized.replace(".", "")
        try:
            return float(normalized)
        except ValueError:
            return None

    @staticmethod
    def _unit_multiplier(unit: str) -> int:
        if unit in {"tỷ", "tỉ", "ty", "ti"}:
            return 1_000_000_000
        if unit in {"triệu", "trieu"}:
            return 1_000_000
        if unit in {"nghìn", "ngan", "k"}:
            return 1_000
        return 1

    @staticmethod
    def _detect_taxable_asset_hint(text: str) -> str | None:
        taxable_asset_terms = (
            "bat dong san",
            "chung khoan",
            "phan von",
            "von gop",
            "quyen su dung",
            "quyen so huu",
            "tai san phai dang ky",
        )
        if any(term in text for term in taxable_asset_terms):
            return "taxable_asset"
        if "tien mat" in text:
            return "cash"
        return None

    @staticmethod
    def _format_vnd(amount: int) -> str:
        return f"{amount:,}".replace(",", ".") + " đồng"

    @staticmethod
    def _format_vnd_natural(amount: int) -> str:
        if amount % 1_000_000_000 == 0:
            return f"{amount // 1_000_000_000} tỷ"
        if amount % 1_000_000 == 0:
            return f"{amount // 1_000_000} triệu"
        if amount % 1_000 == 0:
            return f"{amount // 1_000} nghìn"
        return TaxComputationService._format_vnd(amount)

    @staticmethod
    def _fold_text(text: str) -> str:
        replacements = str.maketrans({"đ": "d", "Đ": "D"})
        normalized = unicodedata.normalize("NFKD", text.translate(replacements))
        return "".join(char for char in normalized if not unicodedata.combining(char)).lower()
