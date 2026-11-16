"""Unit tests locking in S0.3 verified bibliography and refcheck log."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_BIB = ROOT / "paper" / "references.bib"
NEW_BIB = ROOT / "paper" / "iscience" / "references.bib"
LOG_MD = ROOT / "paper" / "refcheck" / "verification_log.md"

ENTRY_HEADER_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
FIELD_START_RE = re.compile(r"(\w+)\s*=\s*\{")


def parse_bib(path: Path) -> list[tuple[str, str, dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    entries: list[tuple[str, str, dict[str, str]]] = []
    for match in ENTRY_HEADER_RE.finditer(text):
        etype = match.group(1).lower()
        key = match.group(2)
        idx = match.end()
        depth = 1
        while idx < len(text) and depth > 0:
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
            idx += 1
        assert depth == 0, f"Unbalanced braces in entry {key}"
        body = text[match.end():idx - 1]
        fields: dict[str, str] = {}
        pos = 0
        while pos < len(body):
            while pos < len(body) and body[pos].isspace():
                pos += 1
            if pos >= len(body):
                break
            fmatch = FIELD_START_RE.match(body, pos)
            assert fmatch is not None, f"Unexpected syntax in {key} near: {body[pos:pos+40]!r}"
            fname = fmatch.group(1).lower()
            vidx = fmatch.end()
            vdepth = 1
            while vidx < len(body) and vdepth > 0:
                if body[vidx] == "{":
                    vdepth += 1
                elif body[vidx] == "}":
                    vdepth -= 1
                vidx += 1
            assert vdepth == 0, f"Unbalanced field {fname} in {key}"
            assert fname not in fields, f"Duplicate field {fname} in {key}"
            fields[fname] = re.sub(r"\s+", " ", body[fmatch.end():vidx - 1]).strip()
            pos = vidx
            while pos < len(body) and body[pos].isspace():
                pos += 1
            if pos < len(body):
                assert body[pos] == ",", f"Missing comma after field {fname} in {key}"
                pos += 1
        entries.append((etype, key, fields))
    return entries


def test_new_bib_syntax_ascii_and_required_fields():
    raw = NEW_BIB.read_text(encoding="utf-8")
    non_ascii = [ch for ch in raw if ord(ch) > 127]
    assert not non_ascii, f"Non-ASCII chars in references.bib: {set(non_ascii)}"

    entries = parse_bib(NEW_BIB)
    assert len(entries) >= 65

    seen_keys: set[str] = set()
    for etype, key, fields in entries:
        assert key not in seen_keys, f"Duplicate BibTeX key: {key}"
        seen_keys.add(key)
        assert "title" in fields and fields["title"], f"Missing title in {key}"
        assert "author" in fields or "editor" in fields, f"Missing author/editor in {key}"
        assert "year" in fields and re.fullmatch(r"\d{4}", fields["year"]), f"Invalid year in {key}"
        if etype == "article":
            for req in ("journal", "volume", "pages"):
                assert req in fields and fields[req], f"Missing {req} in @article {key}"


def test_every_old_and_new_key_is_logged_in_verification_log():
    log_text = LOG_MD.read_text(encoding="utf-8")
    assert "2026-11-16" in log_text

    old_keys = {key for _, key, _ in parse_bib(OLD_BIB)}
    assert len(old_keys) == 49
    for okey in old_keys:
        assert f"`{okey}`" in log_text, f"Legacy key {okey} missing from verification_log.md"

    new_keys = {key for _, key, _ in parse_bib(NEW_BIB)}
    for nkey in new_keys:
        assert f"`{nkey}`" in log_text, f"New key {nkey} missing from verification_log.md"


def test_required_s03_literature_and_metadata_fixes_present():
    by_key = {key: fields for _, key, fields in parse_bib(NEW_BIB)}

    expected_dois = {
        "kramer2015setpoint": "10.1016/j.apenergy.2015.08.044",
        "kramer2017dynamic": "10.1016/j.buildenv.2017.03.028",
        "kramer2022clima": "10.34641/clima.2022.305",
        "martens2012thesis": "10.6100/IR729797",
        "kupczak2018herie": "10.1080/00393630.2018.1504447",
        "bratasz2013paintedwood": "10.1179/2047058412Y.0000000061",
        "camuffo2022en15757": "10.3390/atmos13091344",
        "schito2018museum": "10.1016/j.apenergy.2018.04.076",
        "schito2020museum": "10.1016/j.buildenv.2020.107018",
        "frasca2024microclimate": "10.1038/s41598-024-69395-3",
        "coelho2020museum": "10.1016/j.enbuild.2020.110250",
        "drgona2022dpc": "10.1016/j.jprocont.2022.06.001",
        "sedlbauer2002mould": "10.1177/0075424202025004093",
    }
    for key, doi in expected_dois.items():
        assert key in by_key, f"Required entry {key} missing"
        assert by_key[key].get("doi") == doi

    for non_doi_req in (
        "michalski1993rh",
        "michalski2002double",
        "michalski2007ideal",
        "bizot2023green",
        "ashrae_handbook_ch24",
        "sedlbauer2001thesis",
    ):
        assert non_doi_req in by_key, f"Required entry {non_doi_req} missing"

    # Guard against regression of fabricated given names found in legacy bib
    assert "Bosco, Emanuela" in by_key["frasca2024microclimate"]["author"]
    assert "Kuka, Edgars" in by_key["frasca2024microclimate"]["author"]
    assert "Boesgaard, Christian" in by_key["boesgaard2022heritage"]["author"]
    assert "Torp-Smith, Noah" in by_key["boesgaard2022heritage"]["author"]
    assert "Tringa, Efstathia" in by_key["greek_museum_2024"]["author"]
    assert by_key["energyplus"]["year"] == "2023"
