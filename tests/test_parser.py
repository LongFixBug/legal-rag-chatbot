from app.services.parser import DocumentParserService


def test_parse_html_file():
    parser = DocumentParserService()
    text = parser.parse_uploaded_file(
        "legal.html",
        b"<html><body><h1>Luat</h1><p>Dieu 10. Noi dung.</p></body></html>",
    )
    assert "Dieu 10" in text
