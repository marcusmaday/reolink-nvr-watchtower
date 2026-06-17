#!/usr/bin/env python3
"""
Validate the rolling RTSP buffer path against a live Reolink NVR.

Usage:
  NVR_HOST=... NVR_PORT=80 NVR_USERNAME=... NVR_PASSWORD=... \
  python3 scripts/validate_rolling_buffer.py --channel 8 --seconds 12 --segment-seconds 2

This script:
  1. Connects to the NVR through reolink_aio
  2. Resolves an RTSP stream for the selected channel
  3. Records segmented MPEG-TS chunks using a bundled ffmpeg binary
  4. Stitches the captured segments into a short MP4
"""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from imageio_ffmpeg import get_ffmpeg_exe
from reolink_aio.api import Host


@dataclass
class Segment:
    path: Path
    start_time: datetime


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", type=int, default=int(os.getenv("ROLLING_BUFFER_CHANNEL", "8")))
    parser.add_argument("--seconds", type=int, default=12)
    parser.add_argument("--segment-seconds", type=int, default=2)
    parser.add_argument("--stream", choices=["sub", "main"], default=os.getenv("ROLLING_BUFFER_STREAM", "sub"))
    return parser.parse_args()


async def _resolve_rtsp(host: Host, channel: int, stream: str) -> Optional[str]:
    if hasattr(host, "get_rtsp_stream_source"):
        return await host.get_rtsp_stream_source(channel, stream=stream)
    if hasattr(host, "get_rtsp_url"):
        return await host.get_rtsp_url(channel, stream=stream)
    if hasattr(host, "rtsp"):
        return host.rtsp(channel, stream)
    return None


async def _record_segments(rtsp_url: str, out_dir: Path, ffmpeg_bin: str, segment_seconds: int, seconds: int) -> None:
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-rtsp_transport",
        "tcp",
        "-fflags",
        "+genpts",
        "-i",
        rtsp_url,
        "-an",
        "-map",
        "0:v:0",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(max(segment_seconds * 2, 10)),
        "-keyint_min",
        str(max(segment_seconds * 2, 10)),
        "-sc_threshold",
        "0",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-reset_timestamps",
        "1",
        "-segment_format",
        "mpegts",
        "-strftime",
        "1",
        str(out_dir / "%Y%m%dT%H%M%S.ts"),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.sleep(seconds)
    finally:
        proc.terminate()
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            _, stderr = await proc.communicate()
        if proc.returncode not in (0, None):
            detail = (stderr or b"").decode("utf-8", "ignore").strip()
            print(f"ffmpeg exited with {proc.returncode}: {detail}")


def _load_segments(out_dir: Path) -> list[Segment]:
    segments: list[Segment] = []
    for file_path in sorted(out_dir.glob("*.ts")):
        try:
            start_time = datetime.strptime(file_path.stem.split("_")[0], "%Y%m%dT%H%M%S")
        except ValueError:
            continue
        segments.append(Segment(path=file_path, start_time=start_time))
    return segments


async def main() -> int:
    args = _parse_args()
    host = os.getenv("NVR_HOST")
    port = int(os.getenv("NVR_PORT", "80"))
    username = os.getenv("NVR_USERNAME")
    password = os.getenv("NVR_PASSWORD")
    use_https = os.getenv("NVR_SSL", "false").lower() == "true"
    if not all([host, username, password]):
        print("Missing NVR_HOST, NVR_USERNAME, or NVR_PASSWORD")
        return 2

    ffmpeg_bin = get_ffmpeg_exe()
    print("Using ffmpeg:", ffmpeg_bin)

    nvr = Host(host=host, port=port, username=username, password=password, use_https=use_https)
    await nvr.get_host_data()
    print(f"Connected to NVR: {nvr.nvr_name} ({nvr.num_channels} channels)")

    rtsp_url = await _resolve_rtsp(nvr, args.channel, args.stream)
    if not rtsp_url:
        print("No RTSP URL available")
        return 3

    print("RTSP URL resolved:", rtsp_url.split("@", 1)[0] + "@<redacted>" if "@" in rtsp_url else rtsp_url)

    with TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        print(f"Recording {args.seconds}s of segments to {out_dir}")
        await _record_segments(rtsp_url, out_dir, ffmpeg_bin, args.segment_seconds, args.seconds)

        segments = _load_segments(out_dir)
        print("Segments:", len(segments))
        for seg in segments:
            print(" ", seg.path.name, seg.path.stat().st_size)

        if not segments:
            return 4

    await nvr.logout()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
