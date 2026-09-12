#!/usr/bin/env python3
#
# SPRD / Android DTBO DTB Extractor
#
# Extracts DTB files from SPRD container images and Android DTBO images.
#
# Authors:
# Dr. TeaBread <teabread233@126.com> @LinearTeam
#
# Copyright (C) 2026 Evarentha
# SPDX-License-Identifier: MIT

"""
SPRD / Android DTBO DTB Extractor

Extracts DTB files from:
  1. SPRD container (magic "SPRD"): version + entry table, entries named
     %04u_%u.dtb (index, chipset)
  2. Android DTBO (magic 0xD7B7AB1E): dt_table_header + dt_table_entry,
     entries named %04u_%u.dtb (index, entry id)

Usage: python unsprd.py [-f] [-v] [-d] <input_img> [output_prefix]

Options:
  -f / --force   overwrite existing files
  -v / --verbose detailed logging
  -d / --all     extract duplicate entries too
"""

import argparse
import struct
import sys
from pathlib import Path

SPRD_MAGIC = b"SPRD"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
DTBO_MAGIC = 0xD7B7AB1E
MAX_DTB_COUNT = 4096
MAX_DTB_SIZE = 64 * 1024 * 1024


def is_fdt(buf: bytes) -> bool:
    return buf[:4] == FDT_MAGIC


def extract_sprd(data: bytes, prefix: Path, force: bool, verbose: bool, allow_dups: bool):
    """SPRD container: 12-byte header + 20-byte entries (LE)."""
    if len(data) < 12:
        print("Error: file too small for SPRD header", file=sys.stderr)
        return 1
    version, count = struct.unpack_from("<II", data, 4)
    if verbose:
        print(f"[DEBUG] SPRD image version: {version}, Entry count: {count}")
    if count == 0 or count > MAX_DTB_COUNT:
        print(f"Error: Unsupported entry count {count}", file=sys.stderr)
        return 1

    entries = []
    for i in range(count):
        chipset, platform, rev, off, size = struct.unpack_from("<5I", data, 12 + i * 20)
        if off + size > len(data):
            print(f"Warning: Entry {i} out of bounds. Skipping.", file=sys.stderr)
            size = 0
        elif size > MAX_DTB_SIZE:
            print(f"Error: Entry {i} size ({size}) exceeds maximum", file=sys.stderr)
            return 1
        entries.append((chipset, platform, rev, off, size))

    extracted = skipped = 0
    for i, (chipset, platform, rev, off, size) in enumerate(entries):
        if size == 0:
            skipped += 1
            continue
        if not allow_dups:
            dup = next((j for j in range(i)
                        if entries[j][3] == off and entries[j][4] == size), -1)
            if dup >= 0:
                if verbose:
                    print(f"[{i:04d}] Duplicate of entry {dup:04d}, skipping.",
                          file=sys.stderr)
                skipped += 1
                continue

        out = prefix / f"{i:04d}_{chipset}.dtb"
        if out.exists() and not force:
            print(f"Warning: File '{out}' already exists. Skipping (use -f).",
                  file=sys.stderr)
            skipped += 1
            continue
        buf = data[off:off + size]
        if not is_fdt(buf):
            print(f"Warning: Entry {i:04d} has invalid FDT magic!", file=sys.stderr)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(buf)
        if verbose:
            print(f"[{i:04d}] Extracted: {out} "
                  f"(ID: 0x{chipset:X} / {chipset}, P:{platform}, R:0x{rev:X})")
        extracted += 1

    print(f"Extraction complete. {extracted} DTB(s) extracted, {skipped} skipped.")
    return 0


def extract_dtbo(data: bytes, prefix: Path, force: bool, verbose: bool, allow_dups: bool):
    """Android DTBO (big-endian): dt_table_header + dt_table_entry (32B)."""
    _, total_size, header_size, fdt_entry_size, _ = struct.unpack_from(">5I", data, 0)
    if verbose:
        print(f"[DEBUG] Android DTBO image: total {total_size}, "
              f"header {header_size}, fdt_entry {fdt_entry_size}")
    if header_size < 32 or fdt_entry_size < 32:
        print("Error: Unexpected DTBO header sizes", file=sys.stderr)
        return 1

    extracted = skipped = 0
    seen = set()
    i = 0
    off = header_size
    while off + 32 <= len(data):
        dt_size, dt_offset, dt_id, dt_rev = struct.unpack_from(">4I", data, off)
        custom = struct.unpack_from(">4I", data, off + 16)
        off += fdt_entry_size
        # Strict validation: entries must sit inside the table region and point
        # at real FDT data. Stop at the first invalid entry (padding/FDT body).
        if (dt_size == 0 or dt_offset < header_size
                or dt_offset + dt_size > min(total_size, len(data))
                or not is_fdt(data[dt_offset:dt_offset + 4])):
            break
        if not allow_dups and (dt_offset, dt_size) in seen:
            if verbose:
                print(f"[{i:04d}] Duplicate entry, skipping.", file=sys.stderr)
            skipped += 1
            i += 1
            continue
        seen.add((dt_offset, dt_size))

        out = prefix / f"{i:04d}_{dt_id}.dtb"
        if out.exists() and not force:
            print(f"Warning: File '{out}' already exists. Skipping (use -f).",
                  file=sys.stderr)
            skipped += 1
            i += 1
            continue
        buf = data[dt_offset:dt_offset + dt_size]
        if not is_fdt(buf):
            print(f"Warning: Entry {i:04d} has invalid FDT magic!", file=sys.stderr)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(buf)
        if verbose:
            print(f"[{i:04d}] Extracted: {out} (id 0x{dt_id:X}, rev 0x{dt_rev:X}, "
                  f"custom: {[hex(c) for c in custom]})")
        extracted += 1
        i += 1

    print(f"Extraction complete. {extracted} DTB(s) extracted, {skipped} skipped.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="SPRD / Android-DTBO DTB Extractor")
    ap.add_argument("-f", "--force", action="store_true", help="force overwrite")
    ap.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    ap.add_argument("-d", "--all", action="store_true", help="extract duplicates too")
    ap.add_argument("input", help="input image (dtb.img / dtbo.img)")
    ap.add_argument("prefix", nargs="?", default=".",
                    help="output directory (or file prefix)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"Error: input file not found: {src}", file=sys.stderr)
        return 1
    data = src.read_bytes()
    prefix = Path(args.prefix)
    prefix.mkdir(parents=True, exist_ok=True)

    if data[:4] == SPRD_MAGIC:
        return extract_sprd(data, prefix, args.force, args.verbose, args.all)
    if struct.unpack_from(">I", data, 0)[0] == DTBO_MAGIC:
        return extract_dtbo(data, prefix, args.force, args.verbose, args.all)
    print(f"Error: Invalid magic: {data[:4].hex()}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
