from app.services.citation import CitationService


def test_extract_references():
    service = CitationService()
    refs = service.extract_references("Theo khoản 1 Điều 30 và điểm a khoản 2 Điều 4 của Luật Nghĩa vụ quân sự")
    assert "Điều 30" in refs
    assert "khoản 1" in [item.lower() for item in refs]
