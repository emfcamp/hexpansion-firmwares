#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") VID PID    e.g. $(basename "$0") 0x4291 0x1830" >&2
    exit 2
}

[ $# -eq 2 ] || usage

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$REPO_ROOT/build"

vid="${1,,}"
pid="${2,,}"
base="firmware_${vid}_${pid}"

json="$BUILD_DIR/$base.json"
tarball="$BUILD_DIR/$base.tar.gz"

[ -f "$json" ] || { echo "No eeprom json for $vid/$pid (expected $json)" >&2; exit 1; }
[ -f "$tarball" ] || { echo "No tarball for $vid/$pid (expected $tarball)" >&2; exit 1; }

eeprom_size="$(jq -r '.eeprom_total_size' "$json")"
fs_offset="$(jq -r '.fs_offset' "$json")"

if [ "$eeprom_size" -lt 8192 ]; then
    BLOCKSIZE=64
else
    BLOCKSIZE=512
fi

# Filesystem occupies everything after the header, in whole 64-byte units.
fs_size=$(( (eeprom_size - fs_offset) / 64 * 64 ))

# Each file costs its content rounded up to a block, plus a block of metadata.
# Two further blocks are the filesystem superblock pair.
read -r file_count used < <(
    tar tzvf "$tarball" |
    awk -v bs="$BLOCKSIZE" '
        $1 ~ /^-/ {
            n++
            used += int(($3 + bs - 1) / bs) * bs + bs
        }
        END { print n + 0, used + 2 * bs }
    '
)

pct="$(awk -v u="$used" -v t="$fs_size" 'BEGIN { printf "%.1f", (t > 0 ? u * 100 / t : 0) }')"

echo "$vid/$pid: $file_count files, block size $BLOCKSIZE"
echo "Used $used bytes of $fs_size ($pct%)"

if [ "$used" -gt "$fs_size" ]; then
    echo "ERROR: filesystem overflows EEPROM by $(( used - fs_size )) bytes" >&2
    exit 1
fi
