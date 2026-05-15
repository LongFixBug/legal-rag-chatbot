from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EVAL_CASES_PATH = PROJECT_ROOT / "evals" / "legal_quality_cases.json"
GENERATED_CASES_PATH = PROJECT_ROOT / "evals" / "generated_cases.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _merge_cases(base: dict, extra: dict) -> dict:
    merged: dict[str, list] = {}
    for key in ("retrieval", "answer", "calculation"):
        merged[key] = base.get(key, []) + extra.get(key, [])
    return merged


def load_eval_cases() -> dict:
    base = _load_json(EVAL_CASES_PATH)
    if GENERATED_CASES_PATH.exists():
        extra = _load_json(GENERATED_CASES_PATH)
        return _merge_cases(base, extra)
    return base


def active_eval_groups() -> set[str] | None:
    raw = os.getenv("EVAL_GROUPS", "").strip()
    if not raw:
        return None
    return {group.strip() for group in raw.split(",") if group.strip()}


def select_eval_cases(cases: list[dict]) -> list[dict]:
    groups = active_eval_groups()
    if not groups:
        return cases
    return [case for case in cases if case.get("group") in groups]


EVAL_CASES = load_eval_cases()
RETRIEVAL_CASES = select_eval_cases(EVAL_CASES["retrieval"])
ANSWER_CASES = select_eval_cases(EVAL_CASES["answer"])
CALCULATION_CASES = select_eval_cases(EVAL_CASES["calculation"])


def case_ids(cases: list[dict]) -> list[str]:
    return [f"{case.get('group', 'ungrouped')}::{case['id']}" for case in cases]


def seed_case_documents(client, case: dict) -> None:
    existing = client.get("/api/documents")
    assert existing.status_code == 200
    for document in existing.json():
        deleted = client.delete(f"/api/documents/{document['id']}")
        assert deleted.status_code == 200

    for filename in case["seed_files"]:
        path = DATA_DIR / filename
        content = path.read_text(encoding="utf-8")
        response = client.post(
            "/api/documents/ingest",
            json={
                "title": path.stem.replace("-", " ").title(),
                "source": f"eval/{case['id']}/{filename}",
                "content": content,
            },
        )
        assert response.status_code == 200


def _ws_collapse(s: str) -> str:
    return " ".join(s.split())


def assert_text_constraints(text: str, case: dict) -> None:
    is_draft = case.get("draft", False)
    for expected in case.get("must_include", []):
        if is_draft:
            assert _ws_collapse(expected) in _ws_collapse(text), (
                f"Expected `{expected}` in answer for `{case['id']}`.\nAnswer:\n{text[:400]}"
            )
        else:
            assert expected in text, f"Expected `{expected}` in answer for `{case['id']}`.\nAnswer:\n{text[:400]}"
    for forbidden in case.get("must_not_include", []):
        assert forbidden not in text, f"Did not expect `{forbidden}` in answer for `{case['id']}`.\nAnswer:\n{text[:400]}"


def result_matches_expected(result: dict, expected: dict, is_draft: bool = False) -> bool:
    if expected.get("title_contains") and expected["title_contains"] not in result["title"]:
        return False
    if expected.get("article") and expected["article"] != result.get("article"):
        return False
    if expected.get("excerpt_contains"):
        expected_excerpt = _ws_collapse(expected["excerpt_contains"])
        result_excerpt = _ws_collapse(result["excerpt"])
        if is_draft:
            expected_tokens = set(expected_excerpt.lower().split())
            result_tokens = set(result_excerpt.lower().split())
            if len(expected_tokens & result_tokens) < max(len(expected_tokens) // 3, 2):
                return False
        elif expected_excerpt not in result_excerpt:
            return False
    return True


@pytest.mark.parametrize("case", RETRIEVAL_CASES, ids=case_ids(RETRIEVAL_CASES))
def test_retrieval_quality_eval(client, case):
    seed_case_documents(client, case)

    response = client.get("/api/legal/search", params={"q": case["question"], "top_k": case.get("top_k", 5)})
    assert response.status_code == 200
    results = response.json()["results"]

    assert results, f"Expected retrieval results for `{case['id']}`"
    assert any(result_matches_expected(result, case["expected_any"], case.get("draft", False)) for result in results), (
        f"No retrieval result matched expected evidence for `{case['id']}`.\n"
        f"Expected: {case['expected_any']}\n"
        f"Results: {results}"
    )


@pytest.mark.parametrize("case", ANSWER_CASES, ids=case_ids(ANSWER_CASES))
def test_answer_quality_eval(client, case):
    seed_case_documents(client, case)

    response = client.post("/api/chat/query", json={"question": case["question"]})
    assert response.status_code == 200
    assert_text_constraints(response.json()["answer"], case)


@pytest.mark.parametrize("case", CALCULATION_CASES, ids=case_ids(CALCULATION_CASES))
def test_calculation_quality_eval(client, case):
    seed_case_documents(client, case)

    response = client.post("/api/chat/query", json={"question": case["question"]})
    assert response.status_code == 200
    assert_text_constraints(response.json()["answer"], case)
