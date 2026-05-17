from pathlib import Path

from scripts.generate_eval_candidates import generate_candidates


def test_generate_eval_candidates_from_legal_text(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "luat-mau.txt").write_text(
        "\n".join(
            [
                "Luật Nghĩa vụ quân sự mẫu",
                "",
                "Điều 30. Độ tuổi gọi nhập ngũ",
                "Công dân đủ 18 tuổi được gọi nhập ngũ; độ tuổi gọi nhập ngũ từ đủ 18 tuổi đến hết 25 tuổi.",
                "",
                "Điều 6. Nội dung chung",
                "Quy định khác.",
            ]
        ),
        encoding="utf-8",
    )

    payload = generate_candidates(data_dir, ["luat-mau.txt"], max_per_file=3, variants=0)

    assert payload["retrieval"]
    assert payload["answer"]
    retrieval = payload["retrieval"][0]
    answer = payload["answer"][0]
    assert retrieval["draft"] is True
    assert retrieval["expected_any"]["title_contains"] == "Luật Nghĩa vụ quân sự mẫu"
    assert retrieval["expected_any"]["article"] == "Điều 30"
    assert retrieval["seed_files"] == ["luat-mau.txt"]
    assert answer["question"] == retrieval["question"]
    assert "Điều 30" in answer["must_include"] or any("Điều 30" in item for item in answer["must_include"])
