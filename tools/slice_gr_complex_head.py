#!/usr/bin/env python3
"""IQ文件切片工具"""

# how to use
# 跳过前 5000 个采样，再取 10000 个
# python /home/ubuntu/radar2026/radio26/tools/slice_gr_complex_head.py /home/ubuntu/Desktop/RecsAndLogs/6-RPS/wireless_raw/rx_sig_433920000.0_2026-05-24_21-33-45.iq rec/trimmed.iq 2000000 --offset 100000

from __future__ import annotations

import argparse
from pathlib import Path

BYTES_PER_COMPLEX64 = 8  # GNU Radio gr_complex: float32 I + float32 Q


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Slice the first N complex64 samples from a binary IQ file."
    )
    parser.add_argument("input", type=Path, help="Input IQ binary file path")
    parser.add_argument("output", type=Path, help="Output sliced file path")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Start position in complex samples (default: 0)",
    )
    parser.add_argument(
        "samples",
        type=int,
        help="Number of complex samples to keep",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

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
