from __future__ import annotations

import enum
import unicodedata


class MilitaryQuestionType(str, enum.Enum):
    age = "age"
    service_duration = "service_duration"
    standards = "standards"
    defer_exempt = "defer_exempt"
    student_defer = "student_defer"
    health = "health"
    eyesight = "eyesight"
    exam_call = "exam_call"
    penalty = "penalty"
    general = "general"
    non_military = "non_military"


MILITARY_KEYWORDS = (
    "nghia vu quan su",
    "nhap ngu",
    "di linh",
    "di bo doi",
    "quan su",
    "kham suc khoe",
    "lenh goi",
    "tam hoan",
    "mien goi",
    "mien nhap ngu",
    "trung tuyen",
    "xuat ngu",
)


class MilitaryServiceLawService:
    def classify_question(self, question: str) -> MilitaryQuestionType:
        folded = self._fold_text(question)
        is_military = any(keyword in folded for keyword in MILITARY_KEYWORDS)
        if not is_military:
            return MilitaryQuestionType.non_military

        if any(term in folded for term in ("bao nhieu tuoi", "do tuoi", "tuoi nao", "het bao nhieu tuoi", "27 tuoi", "25 tuoi")):
            return MilitaryQuestionType.age
        if any(term in folded for term in ("bao lau", "may nam", "thoi han", "phuc vu tai ngu")):
            return MilitaryQuestionType.service_duration
        if any(term in folded for term in ("sinh vien", "dai hoc", "cao dang", "dang hoc", "hoc dai hoc", "hoc cao dang")):
            return MilitaryQuestionType.student_defer
        if any(term in folded for term in ("tam hoan", "mien", "lao dong duy nhat", "con liet si", "thuong binh")):
            return MilitaryQuestionType.defer_exempt
        if any(term in folded for term in ("khong di kham", "tron", "phat", "xu phat", "khong chap hanh")):
            return MilitaryQuestionType.penalty
        if any(term in folded for term in ("can thi", "loan thi", "vien thi", "mat", "thi luc")):
            return MilitaryQuestionType.eyesight
        if any(term in folded for term in ("suc khoe", "loai 1", "loai 2", "loai 3", "chua du suc khoe")):
            return MilitaryQuestionType.health
        if any(term in folded for term in ("lenh goi", "kham suc khoe", "ngay 1 thang 11", "niem yet")):
            return MilitaryQuestionType.exam_call
        if any(term in folded for term in ("tieu chuan", "du dieu kien", "dieu kien")):
            return MilitaryQuestionType.standards
        return MilitaryQuestionType.general

    def answer_question(self, question: str, contexts: list[dict]) -> str | None:
        question_type = self.classify_question(question)
        if question_type == MilitaryQuestionType.non_military:
            return None

        if question_type == MilitaryQuestionType.age:
            lines = [
                "Nói ngắn gọn: công dân đủ 18 tuổi có thể được gọi nhập ngũ.",
                "Độ tuổi gọi nhập ngũ thông thường là từ đủ 18 tuổi đến hết 25 tuổi.",
                "Nếu đã được tạm hoãn vì đang đào tạo trình độ cao đẳng hoặc đại học thì độ tuổi gọi nhập ngũ kéo dài đến hết 27 tuổi.",
            ]
        elif question_type == MilitaryQuestionType.service_duration:
            lines = [
                "Thời hạn phục vụ tại ngũ trong thời bình của hạ sĩ quan, binh sĩ thường là 24 tháng.",
                "Trường hợp cần bảo đảm nhiệm vụ sẵn sàng chiến đấu hoặc nhiệm vụ đặc biệt, thời hạn có thể được kéo dài theo quy định của Luật Nghĩa vụ quân sự.",
            ]
        elif question_type == MilitaryQuestionType.student_defer:
            lines = [
                "Đang học đại học hệ chính quy hoặc cao đẳng hệ chính quy có thể là căn cứ tạm hoãn gọi nhập ngũ.",
                "Điểm quan trọng: tạm hoãn chỉ trong thời gian một khóa đào tạo của một trình độ đào tạo.",
                "Khi không còn lý do tạm hoãn, công dân vẫn có thể được gọi nhập ngũ; nếu đã được tạm hoãn vì cao đẳng/đại học thì độ tuổi gọi nhập ngũ đến hết 27 tuổi.",
            ]
        elif question_type == MilitaryQuestionType.defer_exempt:
            lines = [
                "Tạm hoãn và miễn gọi nhập ngũ là hai nhóm khác nhau.",
                "Tạm hoãn thường áp dụng cho các trường hợp như chưa đủ sức khỏe, là lao động duy nhất trực tiếp nuôi thân nhân không còn khả năng lao động hoặc chưa đến tuổi lao động, đang học phổ thông/đại học/cao đẳng hệ chính quy trong một khóa đào tạo, hoặc một số trường hợp gia đình/chính sách khác.",
                "Miễn gọi nhập ngũ áp dụng cho các nhóm như con liệt sĩ, con thương binh hạng một, một anh hoặc một em trai của liệt sĩ, một con của thương binh hạng hai hoặc bệnh binh/người nhiễm chất độc da cam suy giảm khả năng lao động từ 81% trở lên, và một số trường hợp công tác ở vùng đặc biệt khó khăn.",
            ]
        elif question_type == MilitaryQuestionType.eyesight:
            lines = [
                "Về mắt/cận thị, không nên kết luận chỉ dựa vào số độ cận; cần kết luận phân loại sức khỏe của Hội đồng khám sức khỏe.",
                "Theo bảng phân loại trong Thông tư 105/2023/TT-BQP: cận dưới -3D được chấm theo thị lực sau chỉnh kính và tăng 1 điểm; cận từ -3D đến dưới -4D là điểm 4; từ -4D đến dưới -5D là điểm 5; từ -5D trở lên là điểm 6.",
                "Tiêu chuẩn chung để tuyển chọn thực hiện nghĩa vụ quân sự là sức khỏe loại 1, loại 2 hoặc loại 3; vì vậy các mức bị chấm điểm 4, 5, 6 thường là tín hiệu không đạt tiêu chuẩn chung, nhưng kết luận cuối cùng vẫn thuộc Hội đồng khám sức khỏe.",
            ]
        elif question_type == MilitaryQuestionType.health:
            lines = [
                "Tiêu chuẩn sức khỏe thực hiện nghĩa vụ quân sự hiện hành dựa trên Thông tư 105/2023/TT-BQP.",
                "Tiêu chuẩn chung là đạt sức khỏe loại 1, loại 2 hoặc loại 3 theo quy định phân loại sức khỏe.",
                "Nếu chưa đủ sức khỏe phục vụ tại ngũ theo kết luận của Hội đồng khám sức khỏe thì thuộc nhóm có thể được tạm hoãn gọi nhập ngũ.",
            ]
        elif question_type == MilitaryQuestionType.penalty:
            lines = [
                "Nếu có lệnh mà không đi kiểm tra/khám sức khỏe nghĩa vụ quân sự không có lý do chính đáng thì có thể bị xử phạt hành chính.",
                "Mức thường gặp: không có mặt đúng thời gian hoặc địa điểm ghi trong lệnh gọi kiểm tra/khám sức khỏe có thể bị phạt từ 10 đến 12 triệu đồng; cố ý không nhận lệnh có thể bị phạt từ 12 đến 15 triệu đồng.",
                "Hành vi gian dối làm sai lệch kết quả phân loại sức khỏe có thể bị phạt từ 15 đến 20 triệu đồng; không chấp hành lệnh gọi kiểm tra, khám sức khỏe có thể bị phạt từ 25 đến 35 triệu đồng.",
            ]
        elif question_type == MilitaryQuestionType.exam_call:
            lines = [
                "Lệnh gọi khám sức khỏe phải được giao trước thời điểm khám 15 ngày.",
                "Thời gian khám sức khỏe gọi công dân nhập ngũ hằng năm là từ ngày 01/11 đến hết ngày 31/12.",
                "Kết quả phân loại sức khỏe phải được niêm yết công khai trong thời hạn 20 ngày tại trụ sở UBND cấp xã, cơ quan hoặc tổ chức liên quan.",
            ]
        elif question_type == MilitaryQuestionType.standards:
            lines = [
                "Công dân được gọi nhập ngũ khi đáp ứng các tiêu chuẩn chính: lý lịch rõ ràng, chấp hành nghiêm chính sách pháp luật, đủ sức khỏe phục vụ tại ngũ và có trình độ văn hóa phù hợp.",
                "Riêng sức khỏe được kết luận theo Hội đồng khám sức khỏe và tiêu chuẩn của Thông tư 105/2023/TT-BQP.",
            ]
        else:
            lines = [
                "Tôi sẽ trả lời trong phạm vi luật nghĩa vụ quân sự: cần đối chiếu nhóm quy định về độ tuổi, tiêu chuẩn, khám sức khỏe, tạm hoãn/miễn gọi nhập ngũ, lệnh gọi và xử phạt.",
            ]

        matching_contexts = self._matching_contexts(contexts, question_type)
        if matching_contexts:
            lines.append("Căn cứ truy xuất:")
            seen: set[tuple[str, str | None]] = set()
            for item in matching_contexts[:5]:
                key = (item["title"], item.get("article"))
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- {item['title']} - {item.get('article') or 'đoạn liên quan'}.")
        lines.append("Lưu ý: đây là hỗ trợ tra cứu pháp luật; trường hợp cụ thể nên đối chiếu quyết định/kết luận của cơ quan quân sự địa phương.")
        return "\n".join(lines)

    def suggested_articles(self, question_type: MilitaryQuestionType) -> set[str]:
        if question_type == MilitaryQuestionType.age:
            return {"Điều 30"}
        if question_type == MilitaryQuestionType.service_duration:
            return {"Điều 21"}
        if question_type == MilitaryQuestionType.standards:
            return {"Điều 31", "Điều 4"}
        if question_type == MilitaryQuestionType.student_defer:
            return {"Điều 30", "Điều 41"}
        if question_type == MilitaryQuestionType.defer_exempt:
            return {"Điều 41", "Điều 42"}
        if question_type == MilitaryQuestionType.health:
            return {"Điều 40", "Điều 41", "Điều 4"}
        if question_type == MilitaryQuestionType.eyesight:
            return {"Điều 4", "Phụ lục I"}
        if question_type == MilitaryQuestionType.exam_call:
            return {"Điều 40"}
        if question_type == MilitaryQuestionType.penalty:
            return {"Điều 6"}
        return set()

    def is_relevant_context(self, item: dict, question_type: MilitaryQuestionType | None = None) -> bool:
        folded = self._fold_text(f"{item.get('title', '')} {item.get('article') or ''} {item.get('content', '')}")
        if not any(term in folded for term in ("nghia vu quan su", "nhap ngu", "kham suc khoe", "thong tu 105", "nghi dinh 120")):
            return False
        if question_type is None or question_type == MilitaryQuestionType.general:
            return True
        signals = {
            MilitaryQuestionType.age: ("du 18 tuoi", "het 25 tuoi", "het 27 tuoi"),
            MilitaryQuestionType.service_duration: ("24 thang", "phuc vu tai ngu"),
            MilitaryQuestionType.standards: ("tieu chuan", "ly lich ro rang", "suc khoe loai"),
            MilitaryQuestionType.student_defer: ("dang hoc", "cao dang", "dai hoc", "tam hoan"),
            MilitaryQuestionType.defer_exempt: ("tam hoan", "mien goi", "liet si", "thuong binh"),
            MilitaryQuestionType.health: ("suc khoe", "hoi dong kham", "loai 1", "loai 2", "loai 3"),
            MilitaryQuestionType.eyesight: ("can thi", "thi luc", "loan thi", "phu luc i"),
            MilitaryQuestionType.exam_call: ("lenh goi kham", "15 ngay", "01 thang 11", "20 ngay"),
            MilitaryQuestionType.penalty: ("phat tien", "khong co mat", "khong chap hanh", "gian doi"),
        }
        return any(signal in folded for signal in signals.get(question_type, ()))

    def _matching_contexts(self, contexts: list[dict], question_type: MilitaryQuestionType) -> list[dict]:
        matches = [item for item in contexts if self.is_relevant_context(item, question_type)]
        return matches or [item for item in contexts if self.is_relevant_context(item)]

    @staticmethod
    def _fold_text(text: str) -> str:
        replacements = str.maketrans({"đ": "d", "Đ": "D"})
        normalized = unicodedata.normalize("NFKD", text.translate(replacements))
        return "".join(char for char in normalized if not unicodedata.combining(char)).lower()
