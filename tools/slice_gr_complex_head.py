#!/usr/bin/env python3
"""IQ文件切片工具"""

# how to use
# 查看文件样本数
# python tools/slice_gr_complex_head.py input.iq --info
# 跳过前 5000 个采样，再取 10000 个
# python tools/slice_gr_complex_head.py input.iq output.iq 10000 --offset 5000

from __future__ import annotations

import argparse
from pathlib import Path

BYTES_PER_COMPLEX64 = 8  # GNU Radio gr_complex: float32 I + float32 Q


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Slice the first N complex64 samples from a binary IQ file."
    )
    parser.add_argument("input", type=Path, help="Input IQ binary file path")
    parser.add_argument("output", type=Path, nargs="?", default=None, help="Output sliced file path")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start position in complex samples (default: 0)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print sample count and exit (no slicing)",
    )
    parser.add_argument(
        "samples",
        type=int,
        nargs="?",
        default=None,
        help="Number of complex samples to keep",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(f"File not found: {args.input}")

    file_size = args.input.stat().st_size
    total_samples = file_size // BYTES_PER_COMPLEX64
    remainder = file_size % BYTES_PER_COMPLEX64

    if args.info:
        print(f"File: {args.input}")
        print(f"Size: {file_size} bytes")
        print(f"Samples: {total_samples} (complex64)")
        if remainder:
            print(f"Warning: {remainder} extra bytes (not a multiple of {BYTES_PER_COMPLEX64})")
        return 0

    if args.output is None or args.samples is None:
        raise SystemExit("output and samples are required unless --info is used")
    if args.samples <= 0:
        raise SystemExit("samples must be > 0")
    if args.offset < 0:
        raise SystemExit("offset must be >= 0")

    start_bytes = args.offset * BYTES_PER_COMPLEX64
    head_bytes = args.samples * BYTES_PER_COMPLEX64

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.input.open("rb") as f_in, args.output.open("wb") as f_out:
        f_in.seek(start_bytes)
        f_out.write(f_in.read(head_bytes))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
