"""A branch cut before a design fix renders the old design. Aloha 2026 women's
top 10 came within one command of posting with a rank-chip colour that main
had fixed a month earlier."""
import subprocess

import pytest

import generate


def _git(behind):
    def run(cmd, **kw):
        out = str(behind) if "rev-list" in cmd else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
    return run


def test_counts_commits_on_main_missing_here(monkeypatch):
    monkeypatch.setattr(generate.subprocess, "run", _git(90))
    assert generate.commits_behind_main() == 90


def test_publishing_from_a_stale_branch_stops(monkeypatch):
    monkeypatch.setattr(generate.subprocess, "run", _git(3))
    with pytest.raises(SystemExit):
        generate.check_not_behind_main(publishing=True)


def test_previewing_from_a_stale_branch_only_warns(monkeypatch, capsys):
    monkeypatch.setattr(generate.subprocess, "run", _git(3))
    generate.check_not_behind_main(publishing=False)
    assert "3 commits behind main" in capsys.readouterr().out


def test_an_up_to_date_branch_says_nothing(monkeypatch, capsys):
    monkeypatch.setattr(generate.subprocess, "run", _git(0))
    generate.check_not_behind_main(publishing=True)
    assert capsys.readouterr().out == ""
