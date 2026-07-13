#!/usr/bin/env bash
# Extract a version from a schema/checklist file and push a git tag for it.
#
# Usage: tag_version.sh <file> <format> <tag-prefix> <label>
#   <format> is "yaml" or "json"; the version is read from the top-level
#   "version" key in either case.
set -eu

FILE="$1"
FORMAT="$2"
TAG_PREFIX="$3"
LABEL="$4"

case "$FORMAT" in
    yaml)
        VERSION=$(grep -m1 '^version:' "$FILE" | sed 's/version:[[:space:]]*["'\'']\?\([^"'\'' ]*\)["'\'']\?.*/\1/')
        ;;
    json)
        VERSION=$(grep -m1 '"version"' "$FILE" | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
        ;;
    *)
        echo "::error::Unknown format '${FORMAT}', expected 'yaml' or 'json'."
        exit 1
        ;;
esac

if [ -z "$VERSION" ]; then
    echo "::error file=${FILE}::Could not extract version."
    exit 1
fi

TAG="${TAG_PREFIX}${VERSION}"
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    echo "Tag ${TAG} already exists, skipping."
else
    git tag -a "${TAG}" -m "${LABEL} version ${VERSION}"
    git push origin "${TAG}"
    echo "Created tag ${TAG}"
fi
