"""Resolve a released principles instance, with an explicit PR preview opt-in."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = "stamped-principles/stamped-principles-schema"
API = f"https://api.github.com/repos/{REPO}"
SHA = re.compile(r"[0-9a-f]{40}")


def get_json(path):
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(f"{API}/{path}", headers=headers), timeout=30) as response:
        return json.load(response)


def resolve(version, preview=None, get=get_json):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid principles version")
    try:
        obj = get(f"git/ref/tags/v{version}")["object"]
    except HTTPError as exc:
        if exc.code != 404 or preview is None:
            raise
        if (
            set(preview) != {"version", "pr", "sha"}
            or preview["version"] != version
            or type(preview["pr"]) is not int
            or preview["pr"] <= 0
            or not isinstance(preview["sha"], str)
            or not SHA.fullmatch(preview["sha"])
        ):
            raise ValueError("Invalid or mismatched principles preview pin")
        sha = preview["sha"]
        for page in range(1, 31):
            commits = get(f"pulls/{preview['pr']}/commits?per_page=100&page={page}")
            if any(commit["sha"] == sha for commit in commits):
                break
            if len(commits) < 100:
                raise ValueError("Preview SHA is not a commit in the specified PR")
        else:
            raise ValueError("Could not verify preview PR commit membership")
        source = f"Preview: PR #{preview['pr']} at {sha}; v{version} is not released"
    else:
        for _ in range(10):
            if obj["type"] != "tag":
                break
            obj = get(f"git/tags/{obj['sha']}")["object"]
        if obj["type"] != "commit":
            raise ValueError("Principles release tag does not resolve to a commit")
        sha = obj["sha"]
        source = f"Released principles v{version} at {sha}"
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise ValueError("Invalid resolved commit SHA")
    file = get(f"contents/stamped-principles.json?ref={sha}")
    if file["type"] != "file" or file["encoding"] != "base64":
        raise ValueError("Invalid principles file response")
    principles = json.loads(base64.b64decode(file["content"]))
    if principles.get("version") != version:
        raise ValueError("Resolved principles instance has the wrong version")
    return principles, source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, default=Path("stamped-checklist.json"))
    parser.add_argument("--preview", type=Path, help="Explicitly permit this PR pin if the release tag is absent")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    version = json.loads(args.checklist.read_text())["principles_version"]
    preview = json.loads(args.preview.read_text()) if args.preview else None
    principles, source = resolve(version, preview)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(principles, indent=2) + "\n")
    print(source)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as stream:
            stream.write(f"### Principles validation source\n\n{source}.\n")


if __name__ == "__main__":
    main()
