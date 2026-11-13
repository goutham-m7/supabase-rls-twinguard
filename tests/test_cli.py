import json
import subprocess


def test_one_command_demo_writes_real_evidence(tmp_path):
    result = subprocess.run(
        ["twinguard", "demo", "--runs", "1", "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    assert "safe       12/12" in result.stdout
    assert "unsafe      0/12" in result.stdout
    assert "no-tools    2/12" in result.stdout
    records = json.loads((tmp_path / "results.json").read_text())
    assert len(records["attempts"]) == 36
    assert records["summary"]["unsafe"]["unauthorized_reads"] == 96
    assert (tmp_path / "report.html").is_file()


def test_invalid_run_count_rejected_before_database_start():
    result = subprocess.run(["twinguard", "demo", "--runs", "0"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "positive" in result.stderr
