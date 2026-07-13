#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") [VID PID]    e.g. $(basename "$0") 0x4291 0x1830" >&2
    exit 2
}

case $# in
    0) ;;
    2) ;;
    *) usage ;;
esac

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
            for py_arg in "${py_args[@]}"; do
                docker run --rm -v "${REPO_ROOT}:/firmware" \
                    ghcr.io/emfcamp/mpy-cross:v5.5.1 \
                    "-march=xtensawin" \
                    "-s" "$(basename "$py_arg")" \
                    "-O3" \
                    "$py_arg"
            done
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

children=()
for parent in "$REPO_ROOT"/0x*/; do
    parent_name="$(basename "$parent")"
    [ $# -eq 0 ] || [ "${parent_name,,}" = "${1,,}" ] || continue
    for child in "$parent"0x*/; do
        [ -d "$child" ] || continue
        child_name="$(basename "$child")"
        [ $# -eq 0 ] || [ "${child_name,,}" = "${2,,}" ] || continue
        children+=("$child")
    done
done

if [ ${#children[@]} -eq 0 ]; then
    echo "No firmware directory for ${1:-0x*}/${2:-0x*}" >&2
    exit 1
fi

for child in "${children[@]}"; do
    parent_name="$(basename "$(dirname "$child")")"
    child_name="$(basename "$child")"
    archive_name="firmware_${parent_name,,}_${child_name,,}.tar.gz"
    if [ -z "$(ls -A "$child")" ]; then
        echo "Skipping $parent_name/$child_name (empty)"
        continue
    fi
    pack "$child" "$archive_name"
done

find "$BUILD_DIR" -maxdepth 1 -type f -empty -delete
