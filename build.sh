#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$REPO_ROOT/build"

pack() {
    local child="$1" archive_name="$2"
    local tar_excludes=(--exclude=eeprom.json --exclude=README.md)
    echo "Packing $(basename "$(dirname "$child")")/$(basename "$child") -> build/$archive_name"
    if [ -f "$child/USE_MPY" ]; then
        local py_args=()
        while IFS= read -r -d '' f; do
            py_args+=("${f/$REPO_ROOT//firmware}")
        done < <(find "$child" -name '*.py' -print0)
        if [ ${#py_args[@]} -gt 0 ]; then
            docker run --rm -v "${REPO_ROOT}:/firmware" \
                ghcr.io/emfcamp/mpy-cross:v5.5.1 \
                "${py_args[@]}"
            find "$child" -name '*.py' -delete
        fi
        tar_excludes+=(--exclude=USE_MPY)
    fi
    (cd "$child" && tar czf "$BUILD_DIR/$archive_name" "${tar_excludes[@]}" .)
    if [ -f "$child/eeprom.json" ]; then
        cp "$child/eeprom.json" "$BUILD_DIR/${archive_name%.tar.gz}.json"
    fi
}

mkdir -p "$BUILD_DIR"

for parent in "$REPO_ROOT"/0x*/; do
    parent_name="$(basename "$parent")"
    for child in "$parent"0x*/; do
        [ -d "$child" ] || continue
        child_name="$(basename "$child")"
        archive_name="firmware_${parent_name,,}_${child_name,,}.tar.gz"
        if [ -z "$(ls -A "$child")" ]; then
            echo "Skipping $parent_name/$child_name (empty)"
            continue
        fi
        pack "$child" "$archive_name"
    done
done

find "$BUILD_DIR" -maxdepth 1 -type f -empty -delete
