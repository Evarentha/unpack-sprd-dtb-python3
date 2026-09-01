# unpack-sprd-dtb-py

Python utility to extract Device Tree Blobs (DTB/DTBO) from Spreadtrum (SPRD) and Android DTBO images.

## Overview

This script extracts individual DTB files from two common firmware image formats used on Spreadtrum/UniSoC platforms:

1. **SPRD Container Format** — Used for base DTB images (`dtb.img`, `dtb.bin`)
2. **Android DTBO Format** — Used for dynamic DTB overlays (`dtbo.img`)

Both formats are commonly found in Android boot partitions for Spreadtrum/UniSoC SoCs.

## Supported Formats

### 1. SPRD Container Format

**Magic:** `SPRD` (0x53 0x50 0x52 0x44)

**Structure:**

```
+------------------+
| "SPRD" (4 bytes) |  Magic identifier
+------------------+
| version (u32)    |  Format version (typically 1)
+------------------+
| count (u32)      |  Number of DTB entries
+------------------+
| Entry 0 (20 B)   |  chipset, platform, rev, offset, size
| Entry 1 (20 B)   |  ...
| ...              |
| Entry N-1 (20 B) |
+------------------+
| 0 (u32)          |  End-of-table marker
+------------------+
| padding          |  Align to page size (default 2048)
+------------------+
| DTB 0 data       |  Raw FDT blob (magic 0xD00DFEED)
| DTB 1 data       |
| ...              |
+------------------+
```

Each entry (little-endian):
- `chipset` (u32) — SoC identifier (e.g., 0x9863)
- `platform` (u32) — Board/platform variant
- `rev` (u32) — Silicon revision
- `offset` (u32) — Byte offset from file start to DTB data
- `size` (u32) — Size of DTB data in bytes

**Output naming:** `{index:04d}_{chipset}.dtb` (e.g., `0000_9863.dtb`)

### 2. Android DTBO Format

**Magic:** `0xD7B7AB1E` (big-endian)

**Structure:**

```
+--------------------------+
| dt_table_header (32 B)   |  Magic, total_size, header_size,
|                          |  dt_entry_size, dt_entry_count, etc.
+--------------------------+
| dt_table_entry 0 (32 B)  |  dt_size, dt_offset, dt_id, dt_rev,
| dt_table_entry 1 (32 B)  |  custom[4]
| ...                      |
+--------------------------+
| DTB 0 data               |  Raw FDT blob (magic 0xD00DFEED)
| DTB 1 data               |
| ...                      |
+--------------------------+
```

All fields are **big-endian**.

**Output naming:** `{index:04d}_{dt_id}.dtb` (e.g., `0000_1234.dtb`)

## Installation

```bash
# No dependencies beyond Python 3 standard library
chmod +x unsprd.py
```

## Usage

```bash
# Extract SPRD container
python unsprd.py dtb.img [output_dir]

# Extract Android DTBO
python unsprd.py dtbo.img [output_dir]

# Options
-f, --force    Overwrite existing files
-v, --verbose  Detailed logging
-d, --all      Extract duplicate entries too
```

### Examples

```bash
# Extract to current directory
python unsprd.py dtb.img

# Extract to specific directory
python unsprd.py dtbo.img ./extracted

# Verbose with force overwrite
python unsprd.py -fv dtb.img output/
```

## How It Works

The script auto-detects the format by checking the first 4 bytes:
- `SPRD` → SPRD container (little-endian)
- `0xD7B7AB1E` → Android DTBO (big-endian)

It then parses the entry table, validates each DTB has the correct FDT magic (`0xD00DFEED`), and writes individual `.dtb` files.

## License

MIT License — see [LICENSE](LICENSE) for details.

