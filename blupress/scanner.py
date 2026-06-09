"""Shared FFprobe scanning and stream parsing for GUI and CLI."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ScanResult = dict[str, Any]


def scan_source(src: str, ffprobe_path: str = 'ffprobe') -> ScanResult:
    cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json',
           '-show_streams', '-show_format', '-show_chapters', src]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print('ERROR: ffprobe not found. Install FFmpeg.', file=sys.stderr)
        sys.exit(1)
    if r.returncode != 0:
        print(f'ERROR: ffprobe failed:\n{r.stderr.strip()[:500]}', file=sys.stderr)
        sys.exit(1)
    if not r.stdout.strip():
        print('ERROR: ffprobe returned no output', file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f'ERROR: JSON decode failed: {e}', file=sys.stderr)
        sys.exit(1)


def parse_streams(info: ScanResult) -> dict[str, Any]:
    streams = info.get('streams', [])
    vid = None
    audio_streams: list[tuple[int, str, str]] = []
    sub_streams: list[tuple[int, str, str]] = []

    for s in streams:
        ct = s.get('codec_type', '')
        idx = s.get('index', '?')
        lang = s.get('tags', {}).get('language', 'und')
        title = s.get('tags', {}).get('title', '')
        cname = s.get('codec_name', '?')
        if ct == 'video' and vid is None:
            vid = s
        elif ct == 'audio':
            codec = cname.upper()
            ch = s.get('channels', '?')
            label = f'[{idx}] {codec} {ch}ch - {lang}'
            if title:
                label += f' ({title})'
            audio_streams.append((idx, label, cname))
        elif ct == 'subtitle':
            codec = cname.upper()
            label = f'[{idx}] {codec} - {lang}'
            if title:
                label += f' ({title})'
            sub_streams.append((idx, label, cname))

    fmt = info.get('format', {})
    try:
        total_duration = float(fmt.get('duration', 0))
    except (ValueError, TypeError):
        total_duration = 0.0
    try:
        original_size = int(fmt.get('size', 0)) / (1024**3)
    except (ValueError, TypeError):
        original_size = 0.0

    return {
        'video':          vid,
        'audio_streams':  audio_streams,
        'sub_streams':    sub_streams,
        'chapters':       info.get('chapters', []),
        'format':         fmt,
        'total_duration': total_duration,
        'original_size':  original_size,
        'width':          vid.get('width', 0) if vid else 0,
        'height':         vid.get('height', 0) if vid else 0,
    }


def fmt_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def fmt_bytes(bytes_: int) -> str:
    gb = bytes_ / (1024**3)
    if gb >= 1:
        return f'{gb:.2f} GB'
    mb = bytes_ / (1024**2)
    return f'{mb:.1f} MB'


def auto_detect_disk_type(width: int) -> str | None:
    if width >= 3840:
        return '4K UHD'
    if width >= 1920:
        return 'Blu-ray'
    if width >= 720:
        return 'DVD'
    return None


def scan_duration(src: str, ffprobe_path: str = 'ffprobe') -> float:
    try:
        cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json',
               '-show_format', src]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            info = json.loads(r.stdout)
            fmt = info.get('format', {})
            return float(fmt.get('duration', 0))
    except Exception:
        pass
    return 0.0
