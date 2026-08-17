"""End-to-end run over the synthetic smoke fixture (never over research data)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fixture_run(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("smoke")
    sample = workdir / "sample"
    outputs = workdir / "outputs"
    make = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_smoke_fixture.py"),
         "--output", str(sample), "--hotels", "3", "--reviews-per-hotel", "24", "--dim", "32"],
        capture_output=True, text=True,
    )
    assert make.returncode == 0, make.stderr
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_handover.py"),
         "--sample-dir", str(sample), "--output-dir", str(outputs)],
        capture_output=True, text=True,
    )
    return run, sample, outputs


def test_handover_run_succeeds(fixture_run):
    run, _, _ = fixture_run
    assert run.returncode == 0, run.stdout + run.stderr
    assert "ALL STEPS PASSED" in run.stdout


def test_expected_artefacts_are_produced(fixture_run):
    _, _, outputs = fixture_run
    assert len(list((outputs / "full_dossiers").glob("*_full.json"))) == 3
    assert len(list((outputs / "compact_dossiers").glob("*_compact.json"))) == 3
    for name in ("frozen_sample_validation.json", "dossier_validation.json", "execution_record.json", "run_summary.json"):
        assert (outputs / "validation" / name).is_file(), name
    assert (outputs / "manifests" / "SUBMISSION_MANIFEST.json").is_file()
    assert (outputs / "diagnostics" / "cluster_diagnostics_summary.json").is_file()


def test_every_review_reaches_a_dossier(fixture_run):
    _, sample, outputs = fixture_run
    declared = json.loads((sample / "sample_definition.json").read_text())["selected_review_count"]
    summary = json.loads((outputs / "validation" / "run_summary.json").read_text())
    assert summary["reviews"] == declared


def test_rerun_is_byte_identical(fixture_run, tmp_path):
    _, sample, outputs = fixture_run
    second = tmp_path / "rerun"
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_handover.py"),
         "--sample-dir", str(sample), "--output-dir", str(second)],
        capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    volatile = {"provenance", "generated_utc"}
    for first_path in sorted((outputs / "full_dossiers").glob("*_full.json")):
        a = json.loads(first_path.read_text())
        b = json.loads((second / "full_dossiers" / first_path.name).read_text())
        for key in volatile:
            a.pop(key, None)
            b.pop(key, None)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), first_path.name


def test_corrupted_sample_makes_the_run_fail_loudly(fixture_run, tmp_path):
    _, sample, _ = fixture_run
    import shutil
    broken = tmp_path / "broken"
    shutil.copytree(sample, broken)
    (broken / "SOURCE_PROVENANCE.json").write_text('{"tampered": true}\n')
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_handover.py"),
         "--sample-dir", str(broken), "--output-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert run.returncode != 0, "a tampered sample must not produce a successful run"
    assert "FAILED" in run.stderr or "FAILED" in run.stdout
