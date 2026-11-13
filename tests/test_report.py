import json
from twinguard.report import summarize, render


def attempt(passed, reads=0, writes=0):
    return {
        "control": "<unsafe>",
        "passed": passed,
        "unauthorized_reads": reads,
        "unauthorized_writes": writes,
        "checks": {"read_repaired": True},
        "task": "task-00",
        "run": 1,
        "before": [],
        "after": [],
        "leaks": [],
        "candidate_sql": "<script>alert(1)</script>",
        "candidate_error": None,
    }


def test_summary_keeps_leaks_separate_from_success():
    result = summarize([attempt(True), attempt(False, 2, 3)])
    assert result["<unsafe>"] == {
        "attempts": 2,
        "passed": 1,
        "happy_path": 2,
        "unauthorized_reads": 2,
        "unauthorized_writes": 3,
    }


def test_report_escapes_all_candidate_content_and_has_no_network_assets():
    report = render([attempt(False, 2)])
    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "&lt;unsafe&gt;" in report
    assert "<html lang=" in report
    assert "https://" not in report
    assert "Unauthorized read observations" in report
    assert json.loads(json.dumps(summarize([attempt(True)])))["<unsafe>"]["passed"] == 1
