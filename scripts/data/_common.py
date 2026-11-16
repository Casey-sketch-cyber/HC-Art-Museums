"""Shared download and SHA-256 verification helpers for public museum datasets.

Raw data files are stored under ``data/raw/<dataset_id>/`` (gitignored) and are
never committed to the repository. Every file is verified against its recorded
byte size and SHA-256 digest after download.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_ROOT = REPO_ROOT / "data" / "raw"
USER_AGENT = "HC-Art-Museums-DatasetFetcher/1.0"


@dataclass(frozen=True)
class FileSpec:
    rel_path: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    doi: str
    license_id: str
    usable: bool
    files: tuple[FileSpec, ...]
    note: str = ""


def compute_sha256(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    total = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(512 * 1024)
            if not chunk:
                break
            total += len(chunk)
            h.update(chunk)
    return total, h.hexdigest()


def verify_file(dest: Path, spec: FileSpec) -> tuple[bool, str]:
    if not dest.exists():
        return False, f"missing: {dest}"
    actual_size, actual_sha = compute_sha256(dest)
    if actual_size != spec.size:
        return False, f"size mismatch for {spec.rel_path}: expected {spec.size}, got {actual_size}"
    if actual_sha.lower() != spec.sha256.lower():
        return False, f"sha256 mismatch for {spec.rel_path}: expected {spec.sha256}, got {actual_sha}"
    return True, "ok"


def _fetch_one(target_root: Path, spec: FileSpec, retries: int = 3) -> str:
    dest = target_root / spec.rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == spec.size:
        ok, _ = verify_file(dest, spec)
        if ok:
            return f"cached  {spec.rel_path} ({spec.size} B)"

    tmp_dest = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(spec.url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=180) as resp, tmp_dest.open("wb") as out:
                while True:
                    block = resp.read(256 * 1024)
                    if not block:
                        break
                    out.write(block)
            tmp_dest.replace(dest)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
    if last_err is not None:
        raise RuntimeError(f"failed to download {spec.url}: {last_err}") from last_err

    ok, msg = verify_file(dest, spec)
    if not ok:
        raise RuntimeError(msg)
    return f"fetched {spec.rel_path} ({spec.size} B)"


def run_cli(dataset: DatasetSpec, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Download and verify {dataset.dataset_id}: {dataset.title} ({dataset.doi})"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_RAW_ROOT / dataset.dataset_id,
        help=f"Destination directory (default: data/raw/{dataset.dataset_id})",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing local files against SHA-256 checksums without downloading.",
    )
    parser.add_argument(
        "--print-manifest",
        action="store_true",
        help="Print the JSON manifest (URLs, sizes, SHA-256 digests) and exit.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel download workers (default: 4).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Download even if dataset is marked unusable due to license restrictions.",
    )
    args = parser.parse_args(argv)

    if args.print_manifest:
        payload = {
            "dataset_id": dataset.dataset_id,
            "title": dataset.title,
            "doi": dataset.doi,
            "license_id": dataset.license_id,
            "usable": dataset.usable,
            "note": dataset.note,
            "total_files": len(dataset.files),
            "total_bytes": sum(f.size for f in dataset.files),
            "files": [asdict(f) for f in dataset.files],
        }
        try:
            print(json.dumps(payload, indent=2))
        except BrokenPipeError:
            pass
        return 0

    if args.verify_only:
        errors: list[str] = []
        for fspec in dataset.files:
            ok, msg = verify_file(args.out_dir / fspec.rel_path, fspec)
            if not ok:
                errors.append(msg)
        if errors:
            for err in errors[:20]:
                print(f"[FAIL] {err}", file=sys.stderr)
            if len(errors) > 20:
                print(f"... and {len(errors) - 20} more errors", file=sys.stderr)
            return 1
        print(f"[OK] {dataset.dataset_id}: all {len(dataset.files)} files verified in {args.out_dir}")
        return 0

    if not dataset.usable and not args.force:
        print(
            f"[SKIP] {dataset.dataset_id} is marked unusable ({dataset.license_id}): {dataset.note}. "
            "Pass --force to download anyway.",
            file=sys.stderr,
        )
        return 2

    print(
        f"[{dataset.dataset_id}] {dataset.title} | license={dataset.license_id} | "
        f"files={len(dataset.files)} -> {args.out_dir}"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(_fetch_one, args.out_dir, fspec) for fspec in dataset.files]
        for idx, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            status = fut.result()
            if idx % 20 == 0 or idx == len(dataset.files) or len(dataset.files) <= 15:
                print(f"  [{idx}/{len(dataset.files)}] {status}")
    print(f"[OK] {dataset.dataset_id}: verified {len(dataset.files)} files.")
    return 0
