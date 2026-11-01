import json
from pathlib import Path

from chatjimmy_harness.harness import check_case, load_suite


def test_check_case_contains_and_bounds():
    passed, failed = check_case(
        "Paris is lovely",
        {
            "expect_contains": ["paris"],
            "expect_not_contains": ["London"],
            "min_chars": 5,
            "max_chars": 50,
        },
    )
    assert failed == []
    assert any("contains" in p for p in passed)


def test_check_case_non_empty_default():
    passed, failed = check_case("hi", {})
    assert passed == ["non_empty"]
    assert failed == []
    passed, failed = check_case("   ", {})
    assert failed == ["non_empty"]


def test_load_suite_json(tmp_path: Path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "name": "t",
                "cases": [{"id": "a", "prompt": "hi", "expect_contains": ["x"]}],
            }
        ),
        encoding="utf-8",
    )
    suite = load_suite(path)
    assert suite["name"] == "t"
    assert suite["cases"][0]["id"] == "a"


def test_load_suite_jsonl(tmp_path: Path):
    path = tmp_path / "s.jsonl"
    path.write_text(
        '# comment\n{"prompt": "hi"}\n\n{"id": "b", "prompt": "yo"}\n',
        encoding="utf-8",
    )
    suite = load_suite(path)
    assert suite["name"] == "s"
    assert suite["cases"][0]["id"] == "case-2"
    assert suite["cases"][1]["id"] == "b"
