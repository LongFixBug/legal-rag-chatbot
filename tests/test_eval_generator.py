from pathlib import Path

from scripts.generate_eval_candidates import generate_candidates


def test_generate_eval_candidates_from_legal_text(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "luat-mau.txt").write_text(
        "\n".join(
            [
                "Luật Mẫu",
                "",
                "Điều 5. Giảm thuế",
                "Người nộp thuế gặp khó khăn do tai nạn, bệnh hiểm nghèo thì được giảm thuế.",
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
    assert retrieval["expected_any"]["title_contains"] == "Luật Mẫu"
    assert retrieval["expected_any"]["article"] == "Điều 5"
    assert retrieval["seed_files"] == ["luat-mau.txt"]
    assert answer["question"] == retrieval["question"]
    assert "Điều 5" in answer["must_include"] or any("Điều 5" in item for item in answer["must_include"])
