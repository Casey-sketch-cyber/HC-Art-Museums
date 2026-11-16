"""Unit tests for S2.1 public dataset fetchers, SHA-256 manifests, and DATASETS.md ledger."""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.data._common import DatasetSpec, FileSpec, compute_sha256, run_cli, verify_file  # noqa: E402

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_COUNTS = {
    "D1": 209,
    "D2": 45,
    "D3": 1,
    "D4": 34,
    "D5": 1,
}


def _load_spec(ds_id: str) -> DatasetSpec:
    mod = importlib.import_module(f"scripts.data.fetch_{ds_id}")
    assert hasattr(mod, "DATASET"), f"fetch_{ds_id}.py must expose DATASET"
    spec = mod.DATASET
    assert isinstance(spec, DatasetSpec)
    return spec


@pytest.mark.parametrize("ds_id,expected_count", sorted(EXPECTED_COUNTS.items()))
def test_fetcher_manifest_integrity(ds_id: str, expected_count: int):
    spec = _load_spec(ds_id)
    assert spec.dataset_id == ds_id
    assert spec.title.strip()
    assert spec.doi.startswith("10.")
    assert len(spec.files) == expected_count

    seen_paths: set[str] = set()
    for fspec in spec.files:
        assert isinstance(fspec, FileSpec)
        assert fspec.rel_path and "\\" not in fspec.rel_path
        rel = Path(fspec.rel_path)
        assert not rel.is_absolute(), f"absolute path not allowed: {fspec.rel_path}"
        assert ".." not in rel.parts, f"parent traversal not allowed: {fspec.rel_path}"
        assert fspec.rel_path not in seen_paths, f"duplicate rel_path in {ds_id}: {fspec.rel_path}"
        seen_paths.add(fspec.rel_path)

        assert fspec.url.startswith("https://")
        assert fspec.size > 0
        assert HEX64_RE.match(fspec.sha256), f"invalid sha256 for {fspec.rel_path}: {fspec.sha256}"


def test_license_and_usability_flags_match_audit():
    for ds_id in ("D1", "D2", "D3", "D4"):
        spec = _load_spec(ds_id)
        assert spec.usable is True
        assert spec.license_id == "CC-BY-4.0"

    d5 = _load_spec("D5")
    assert d5.usable is False
    assert "other-open" in d5.license_id


def test_d1_records_are_namespaced_and_d4_splits_museum_from_lab():
    d1 = _load_spec("D1")
    record_dirs = {Path(f.rel_path).parts[0] for f in d1.files}
    assert record_dirs == {"14233429", "14233508", "14233546", "14503914"}

    d4 = _load_spec("D4")
    museum_txts = [f for f in d4.files if f.rel_path.startswith("Museum_Nov2019/") and f.rel_path.endswith(".txt")]
    lab_txts = [f for f in d4.files if f.rel_path.startswith("LSCR_Oct2019/") and f.rel_path.endswith(".txt")]
    assert len(museum_txts) == 12
    assert len(lab_txts) == 12


def test_cli_print_manifest_outputs_valid_json(capsys: pytest.CaptureFixture[str]):
    d2 = _load_spec("D2")
    rc = run_cli(d2, ["--print-manifest"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_id"] == "D2"
    assert payload["total_files"] == 45
    assert payload["total_bytes"] == sum(f.size for f in d2.files)


def test_cli_skips_unusable_dataset_unless_forced(tmp_path: Path):
    d5 = _load_spec("D5")
    rc = run_cli(d5, ["--out-dir", str(tmp_path / "D5")])
    assert rc == 2
    assert not (tmp_path / "D5").exists()


def test_verify_only_detects_missing_size_and_hash_mismatches(tmp_path: Path):
    payload = b"temperature,rh\n20.5,51.2\n"
    digest = hashlib.sha256(payload).hexdigest()
    sample = DatasetSpec(
        dataset_id="DX",
        title="Synthetic verification dataset",
        doi="10.0000/synthetic",
        license_id="CC-BY-4.0",
        usable=True,
        files=(FileSpec("sub/trace.csv", "https://example.org/trace.csv", len(payload), digest),),
    )

    # 1. Missing file -> exit 1
    assert run_cli(sample, ["--verify-only", "--out-dir", str(tmp_path)]) == 1

    # 2. Exact content -> exit 0
    target = tmp_path / "sub" / "trace.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    size, sha = compute_sha256(target)
    assert (size, sha) == (len(payload), digest)
    assert verify_file(target, sample.files[0])[0] is True
    assert run_cli(sample, ["--verify-only", "--out-dir", str(tmp_path)]) == 0

    # 3. Same byte length, corrupted byte -> exit 1
    corrupted = bytearray(payload)
    corrupted[-1] ^= 0x01
    target.write_bytes(bytes(corrupted))
    ok, msg = verify_file(target, sample.files[0])
    assert not ok and "sha256 mismatch" in msg
    assert run_cli(sample, ["--verify-only", "--out-dir", str(tmp_path)]) == 1

    # 4. Different byte length -> exit 1
    target.write_bytes(payload + b"\n")
    ok, msg = verify_file(target, sample.files[0])
    assert not ok and "size mismatch" in msg
    assert run_cli(sample, ["--verify-only", "--out-dir", str(tmp_path)]) == 1


def test_datasets_doc_has_completed_audit_entries():
    doc_path = ROOT / "docs" / "DATASETS.md"
    text = doc_path.read_text(encoding="utf-8")
    assert "待核对" not in text
    assert "DOI 待核对" not in text

    for ds_id in ("D1", "D2", "D3", "D4", "D5"):
        assert f"### {ds_id} ·" in text

    for required_term in ("许可证", "时间范围", "采样间隔", "缺测比例", "传感器精度", "室外同步数据", "不用"):
        assert required_term in text
