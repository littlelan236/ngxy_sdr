#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


LINE_RE = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\]\s*Publishing\s+ROS2\s+message\s*:\s*(?P<payload>.+)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统计日志中两条 hero_x 类型 ROS2 发布消息之间的最大时间间隔"
    )
    parser.add_argument("log_file", type=Path, help="日志文件路径")
    parser.add_argument(
        "--key",
        default="hero_x",
        help="消息体起始 key，默认 hero_x",
    )
    return parser.parse_args()


def payload_starts_with_key(payload: str, key: str) -> bool:
    payload = payload.lstrip()
    return payload.startswith(f'{{"{key}"') or payload.startswith(f"{{'{key}'")


def parse_timestamp(ts_text: str) -> dt.datetime:
    return dt.datetime.strptime(ts_text, "%Y-%m-%d %H:%M:%S,%f")


def main() -> int:
    args = parse_args()
    if not args.log_file.exists():
        print(f"文件不存在: {args.log_file}")
        return 1

    prev_ts = None
    prev_line_no = None
    count = 0

    max_gap = dt.timedelta(0)
    max_pair = None

    with args.log_file.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            m = LINE_RE.match(line.rstrip("\n"))
            if not m:
                continue

            payload = m.group("payload")
            if not payload_starts_with_key(payload, args.key):
                continue

            curr_ts = parse_timestamp(m.group("ts"))
            count += 1

            if prev_ts is not None:
                gap = curr_ts - prev_ts
                if gap > max_gap:
                    max_gap = gap
                    max_pair = (prev_line_no, prev_ts, line_no, curr_ts)

            prev_ts = curr_ts
            prev_line_no = line_no

    if count < 2:
        print(f"匹配到 {count} 条消息，无法计算间隔。")
        return 2

    assert max_pair is not None
    l1, t1, l2, t2 = max_pair
    max_ms = int(max_gap.total_seconds() * 1000)

    print(f"匹配消息数量: {count}")
    print(f"最大时间间隔: {max_gap.total_seconds():.3f} s ({max_ms} ms)")
    print(f"起始行: {l1}, 时间: {t1.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}")
    print(f"结束行: {l2}, 时间: {t2.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
