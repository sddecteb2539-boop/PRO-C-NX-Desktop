#!/usr/bin/env python3
"""Validate learning records for a PR. Does not certify engineering or approval."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"schema", "id", "disposition", "scope", "summary", "evidence", "tests", "rule_change", "supersedes", "approval"}
DISPOSITIONS = {"candidate", "verified", "no-reusable-lesson", "project-only", "promotion-proposed"}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8")

def validate(path, obj):
    if not isinstance(obj, dict) or set(obj) != FIELDS or type(obj["schema"]) is not int or obj["schema"] != 1:
        raise ValueError(f"{path}: invalid schema")
    if not isinstance(obj["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{5,95}", obj["id"]) or Path(path).stem != obj["id"]:
        raise ValueError(f"{path}: id must match filename")
    if obj["disposition"] not in DISPOSITIONS:
        raise ValueError(f"{path}: invalid disposition")
    for key in ("scope", "summary", "rule_change", "approval"):
        if not isinstance(obj[key], str) or not obj[key].strip():
            raise ValueError(f"{path}: missing {key}")
    for key in ("evidence", "tests", "supersedes"):
        value = obj[key]
        if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value) or (key != "supersedes" and not value):
            raise ValueError(f"{path}: invalid {key}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    base = git("merge-base", args.base, args.head).strip()
    changes = [p for p in git("diff", "--name-only", "--no-renames", "-z", base, args.head).split("\0") if p]
    added = [p for p in git("diff", "--name-only", "--no-renames", "--diff-filter=A", "-z", base, args.head).split("\0") if p]
    records = [p for p in added if p.startswith("knowledge/records/") and p.endswith(".json")]
    # Documentation-only updates may be exempt; canonical instructions and governance are not.
    def exempt(p):
        return (p.lower().endswith((".md", ".rst")) and not
                (p.startswith(("knowledge/", ".github/")) or Path(p).name.lower() in
                 {"agents.md", "claude.md", "gemini.md", "copilot-instructions.md"}))
    relevant = [p for p in changes if not p.startswith("knowledge/records/") and not exempt(p)]
    if relevant and not records:
        raise ValueError("Behavioral/governance PR needs a new knowledge/records/<id>.json")
    # Records are append-only across PRs, preserving earlier decisions.
    prior = [p for p in changes if p.startswith("knowledge/records/") and p not in added]
    if prior:
        raise ValueError("Do not overwrite or delete prior records; add a superseding record")
    for p in records:
        validate(p, json.loads(git("show", f"{args.head}:{p}")))
    if any(p.startswith("knowledge/records/") and not p.endswith(".json") for p in changes):
        raise ValueError("Records directory accepts JSON only")
    print(f"Knowledge gate PASS: {len(changes)} paths, {len(records)} new record(s). Human approval and engineering QC remain required.")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Knowledge gate FAIL: {exc}")
