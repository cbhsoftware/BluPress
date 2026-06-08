"""BluPress CLI — encode, scan, and list presets from the terminal."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from blupress.constants import _quote_path_for_filter
from blupress.models import QueueItem
from blupress.presets import STOCK_PRESETS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ffmpeg():
    return shutil.which('ffmpeg') or 'ffmpeg'


def _get_ffprobe():
    return shutil.which('ffprobe') or 'ffprobe'


def _fmt_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def _fmt_size(bytes_: int) -> str:
    gb = bytes_ / (1024**3)
    if gb >= 1:
        return f'{gb:.2f} GB'
    mb = bytes_ / (1024**2)
    return f'{mb:.1f} MB'


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan_source(src: str) -> dict:
    cmd = [_get_ffprobe(), '-v', 'quiet', '-print_format', 'json',
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


def print_scan(info: dict):
    vid = None
    audio_streams = []
    sub_streams = []
    for s in info.get('streams', []):
        ct = s.get('codec_type', '')
        idx = s.get('index', '?')
        lang = s.get('tags', {}).get('language', 'und')
        codec = s.get('codec_name', '?')
        if ct == 'video' and vid is None:
            vid = s
        elif ct == 'audio':
            title = s.get('tags', {}).get('title', '')
            label = f'{idx}: {lang} {codec}'
            if title:
                label += f' ({title})'
            audio_streams.append((idx, label, codec))
        elif ct == 'subtitle':
            title = s.get('tags', {}).get('title', '')
            label = f'{idx}: {lang} {codec}'
            if title:
                label += f' ({title})'
            sub_streams.append((idx, label, codec))
    fmt = info.get('format', {})
    duration = float(fmt.get('duration', 0))
    size = int(fmt.get('size', 0))
    h = int(duration // 3600)
    m = int((duration % 3600) // 60)
    s = int(duration % 60)

    print(f'File:       {Path(src).name}')
    print(f'Size:       {_fmt_size(size)}')
    print(f'Duration:   {h:02d}:{m:02d}:{s:02d}')
    if vid:
        w = vid.get('width', '?')
        h2 = vid.get('height', '?')
        fps = vid.get('r_frame_rate', '?')
        print(f'Video:      {vid.get("codec_name", "?").upper()}  {w}x{h2}  @{fps} fps')
    for _, al, _ in audio_streams:
        print(f'Audio:      {al}')
    for _, sl, _ in sub_streams:
        print(f'Subtitle:   {sl}')
    chapters = info.get('chapters', [])
    if chapters:
        print(f'Chapters:   {len(chapters)} found')
    print()


# ---------------------------------------------------------------------------
# Command builder (extracted from app.py with minimal changes)
# ---------------------------------------------------------------------------

def _build_cmd(src: str, out_path: str, settings: dict, pass_num: int = 0) -> list:
    cmd = [_get_ffmpeg(), '-y', '-i', src]
    crf = str(settings['quality'])
    codec = settings['video_codec']
    hw = settings.get('use_nvenc', False) or settings.get('use_qsv', False) or settings.get('use_amf', False)

    if settings.get('two_pass') and not hw:
        bitrate = settings['target_bitrate']
        if codec == 'H.265':
            vc = 'libx265'
            if pass_num == 1:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-x265-params', 'pass=1',
                        '-preset', settings['sw_preset'], '-an', '-f', 'null']
                cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
                return cmd
            else:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-x265-params', 'pass=2',
                        '-preset', settings['sw_preset']]
        else:
            vc = 'libx264' if codec == 'H.264' else 'libaom-av1'
            if pass_num == 1:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-pass', '1',
                        '-preset' if codec != 'AV1' else '-cpu-used',
                        settings['sw_preset'] if codec != 'AV1' else '4',
                        '-an', '-f', 'null']
                cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
                return cmd
            else:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-pass', '2',
                        '-preset' if codec != 'AV1' else '-cpu-used',
                        settings['sw_preset'] if codec != 'AV1' else '4']
    elif settings.get('use_nvenc'):
        vc = {'H.265': 'hevc_nvenc', 'H.264': 'h264_nvenc', 'AV1': 'av1_nvenc'}.get(codec, 'hevc_nvenc')
        hw_p = settings.get('hw_preset', 'p4').split()[0]
        cmd += ['-c:v', vc, '-preset', hw_p, '-rc', 'vbr', '-cq', crf]
    elif settings.get('use_amf'):
        vc = {'H.265': 'hevc_amf', 'H.264': 'h264_amf', 'AV1': 'av1_amf'}.get(codec, 'hevc_amf')
        cmd += ['-c:v', vc, '-quality', settings.get('amf_quality', 'balanced'),
                '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf, '-qp_b', crf]
    elif settings.get('use_qsv'):
        vc = {'H.265': 'hevc_qsv', 'H.264': 'h264_qsv', 'AV1': 'av1_qsv'}.get(codec, 'hevc_qsv')
        cmd += ['-c:v', vc, '-global_quality', crf, '-preset', settings.get('qsv_preset', 'medium')]
    else:
        vc = {'H.265': 'libx265', 'H.264': 'libx264', 'AV1': 'libaom-av1'}.get(codec, 'libx265')
        if codec == 'AV1':
            cmd += ['-c:v', vc, '-crf', crf, '-cpu-used', '4', '-row-mt', '1']
        else:
            cmd += ['-c:v', vc, '-crf', crf, '-preset', settings['sw_preset']]

    filters = []
    res_map = {'4K (3840x2160)': '3840:2160', '1080p (1920x1080)': '1920:1080',
               '720p (1280x720)': '1280:720', '576p (1024x576)': '1024:576', '480p (854x480)': '854:480'}
    res = settings.get('resolution', 'Source')
    if res in res_map:
        filters.append(f"scale={res_map[res]}:flags=lanczos")
    if settings.get('use_crop') and settings.get('crop_values'):
        filters.append(f"crop={settings['crop_values']}")
    ar_map = {'16:9': '16/9', '4:3': '4/3', '2.35:1': '2.35', '2.39:1': '2.39', '1.85:1': '1.85'}
    ar = settings.get('aspect_ratio', 'Source')
    if ar in ar_map:
        filters.append(f"setdar={ar_map[ar]}")
    elif settings.get('anamorphic'):
        filters.append('setdar=16/9')
    deint_map = {'Yadif (fast)': 'yadif=0', 'Yadif (slow/better)': 'yadif=1',
                 'BWDIF': 'bwdif=0', 'Decomb': 'yadif=2', 'Bob': 'yadif=1:1'}
    deint = settings.get('deinterlace', 'None')
    if deint in deint_map:
        filters.append(deint_map[deint])

    sub_idx = settings.get('sub_idx')
    is_bitmap = settings.get('sub_is_bitmap', False)
    if sub_idx is not None and settings.get('sub_burn') and not is_bitmap:
        filters.append(f"subtitles={_quote_path_for_filter(src)}:si={sub_idx}")

    if filters:
        cmd += ['-vf', ','.join(filters)]

    vid_done = False
    if sub_idx is not None and settings.get('sub_burn') and is_bitmap:
        if '-vf' in cmd:
            vi = cmd.index('-vf')
            chain = cmd[vi + 1]
            cmd = cmd[:vi] + cmd[vi + 2:]
            fc = f'[0:v]{chain}[vb];[vb][0:{sub_idx}]overlay[vout]'
        else:
            fc = f'[0:v][0:{sub_idx}]overlay[vout]'
        cmd += ['-filter_complex', fc, '-map', '[vout]']
        vid_done = True

    if settings.get('keep_chapters', True):
        cmd += ['-map_chapters', '0']

    audio_tracks = settings.get('audio_tracks', [])
    if not vid_done:
        cmd += ['-map', '0:v:0']

    if audio_tracks:
        for track_idx, acodec, abitrate in audio_tracks:
            cmd += ['-map', f'0:{track_idx}']
        for i, (track_idx, acodec, abitrate) in enumerate(audio_tracks):
            acodec_l = acodec.lower()
            if acodec_l in ('copy', 'passthrough'):
                cmd += [f'-c:a:{i}', 'copy']
            elif acodec_l == 'aac':
                cmd += [f'-c:a:{i}', 'aac', f'-b:a:{i}', abitrate]
            elif acodec_l == 'flac':
                cmd += [f'-c:a:{i}', 'flac']
            elif acodec_l == 'opus':
                cmd += [f'-c:a:{i}', 'libopus', f'-b:a:{i}', abitrate]
            elif acodec_l == 'mp3':
                cmd += [f'-c:a:{i}', 'libmp3lame', f'-b:a:{i}', abitrate]
            else:
                cmd += [f'-c:a:{i}', 'copy']
    else:
        cmd += ['-map', '0:a?', '-c:a', 'copy']

    if sub_idx is not None and not settings.get('sub_burn'):
        cmd += ['-map', f'0:{sub_idx}', '-c:s', 'copy']
    else:
        cmd += ['-sn']

    cmd += ['-progress', 'pipe:1', '-nostats']
    cmd.append(out_path)
    return cmd


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------

def run_encode(src: str, out_path: str, settings: dict):
    """Run the ffmpeg encode with terminal progress output."""
    two_pass = settings.get('two_pass') and not (
        settings.get('use_nvenc') or settings.get('use_amf') or settings.get('use_qsv'))
    passes = [1, 2] if two_pass else [0]

    # Get total duration for progress calculation
    info = scan_source(src)
    fmt = info.get('format', {})
    total_duration = float(fmt.get('duration', 0))
    total_size = int(fmt.get('size', 0))

    print(f'Encoding: {Path(src).name}')
    print(f'Output:   {out_path}')
    print(f'Codec:    {settings["video_codec"]}  CRF: {settings["quality"]}')
    if total_duration:
        print(f'Duration: {_fmt_time(total_duration)}  ({_fmt_size(total_size)})')
    if two_pass:
        print(f'Passes:   2-pass ({settings["target_bitrate"]})')
    print()

    for pass_num in passes:
        label = {0: '', 1: 'Pass 1/2', 2: 'Pass 2/2'}.get(pass_num, '')
        if label:
            print(f'--- {label} ---')

        cmd = _build_cmd(src, out_path, settings, pass_num)
        print(f'CMD: {" ".join(cmd[:8])} ...')
        print()

        start_time = time.time()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)

        last_bucket = -1
        buf = ''
        progress_data = {}

        for char in iter(lambda: proc.stdout.read(1), ''):
            buf += char
            if char == '\n' and buf.strip():
                line = buf.strip()
                buf = ''
                if '=' in line:
                    k, _, v = line.partition('=')
                    progress_data[k.strip()] = v.strip()
                if line in ('progress=continue', 'progress=end'):
                    data = dict(progress_data)
                    progress_data.clear()
                    pct = 0
                    if total_duration > 0:
                        time_s = data.get('out_time_us', '0')
                        try:
                            cur_us = int(time_s)
                            pct = min((cur_us / 1_000_000) / total_duration * 100, 100)
                        except ValueError:
                            pass
                    fps = data.get('fps', '?')
                    speed = data.get('speed', '?')

                    bucket = int(pct / 5)
                    if bucket != last_bucket:
                        last_bucket = bucket
                        elapsed = time.time() - start_time
                        eta = (elapsed / max(pct, 1)) * (100 - pct) if pct > 1 else 0
                        bar_len = 40
                        filled = int(bar_len * pct / 100)
                        bar = '█' * filled + '░' * (bar_len - filled)
                        print(f'\r  [{bar}] {pct:5.1f}%  {fps} fps  {speed}  ETA {_fmt_time(eta)}  ', end='', flush=True)

        print()
        proc.wait()
        if proc.returncode != 0:
            stderr = ''.join(proc.stderr or [])
            print(f'\nERROR: ffmpeg exited with code {proc.returncode}', file=sys.stderr)
            if stderr:
                print(stderr[-500:], file=sys.stderr)
            sys.exit(1)

    elapsed = time.time() - start_time
    out_size = Path(out_path).stat().st_size if Path(out_path).exists() else 0
    print(f'\nDone!  {_fmt_time(elapsed)} elapsed')
    if total_size and out_size:
        saving = (1 - out_size / total_size) * 100
        print(f'  Original: {_fmt_size(total_size)}')
        print(f'  Output:   {_fmt_size(out_size)}  ({saving:.1f}% smaller)')
    print()


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

def list_presets():
    print('Available presets:\n')
    for name, settings in STOCK_PRESETS:
        if settings is None:
            print(f'  -- {name} --')
        else:
            hw = ''
            if settings.get('use_nvenc'):
                hw = ' [NVENC]'
            elif settings.get('use_qsv'):
                hw = ' [QSV]'
            elif settings.get('use_amf'):
                hw = ' [AMF]'
            tp = ' [2-pass]' if settings.get('two_pass') else ''
            print(f'  {name:<40s}  {settings["video_codec"]:5s}  CRF {settings["quality"]:2d}  '
                  f'{settings["sw_preset"]:10s}{hw}{tp}')
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _resolve_preset(name: str) -> dict | None:
    """Find a stock preset by name (case-insensitive, partial match)."""
    name_lower = name.lower()
    for pname, settings in STOCK_PRESETS:
        if settings and name_lower in pname.lower():
            return settings
    return None


def build_encode_settings(args) -> dict:
    settings = {
        'video_codec':    args.codec,
        'quality':        args.crf,
        'sw_preset':      args.preset,
        'hw_preset':      args.hw_preset,
        'amf_quality':    args.amf_quality,
        'qsv_preset':     args.qsv_preset,
        'resolution':     args.resolution,
        'aspect_ratio':   'Source',
        'anamorphic':     False,
        'deinterlace':    args.deinterlace or 'None',
        'use_nvenc':      args.hw == 'nvenc',
        'use_qsv':        args.hw == 'qsv',
        'use_amf':        args.hw == 'amf',
        'sub_track':      'None',
        'sub_burn':       args.burn_subs,
        'two_pass':       args.two_pass,
        'target_bitrate': args.bitrate,
        'use_crop':       False,
        'crop_values':    '',
        'keep_chapters':  not args.no_chapters,
        'sub_idx':        None,
        'sub_is_bitmap':  False,
        'audio_tracks':   [],
    }

    # Apply preset if given
    if args.preset_name:
        preset = _resolve_preset(args.preset_name)
        if preset:
            settings.update(preset)
        else:
            print(f'Warning: preset "{args.preset_name}" not found, using CLI args', file=sys.stderr)

    # CLI args override preset values
    if args.codec != 'H.265':
        settings['video_codec'] = args.codec
    if args.crf != 20:
        settings['quality'] = args.crf
    if args.preset != 'medium':
        settings['sw_preset'] = args.preset
    if args.hw:
        settings['use_nvenc'] = args.hw == 'nvenc'
        settings['use_qsv'] = args.hw == 'qsv'
        settings['use_amf'] = args.hw == 'amf'
    if args.bitrate != '4000k':
        settings['target_bitrate'] = args.bitrate
    if args.two_pass:
        settings['two_pass'] = True

    return settings


def main():
    parser = argparse.ArgumentParser(
        prog='blupress',
        description='BluPress — Blu-ray & DVD Compressor (CLI)',
    )
    sub = parser.add_subparsers(dest='command')

    # --- scan ---
    scan_p = sub.add_parser('scan', help='Show media info for a source file')
    scan_p.add_argument('source', help='Source file path')

    # --- presets ---
    sub.add_parser('presets', help='List available presets')

    # --- encode ---
    enc_p = sub.add_parser('encode', help='Encode a file')
    enc_p.add_argument('source', help='Source file path')
    enc_p.add_argument('-o', '--output', help='Output file path (auto if omitted)')
    enc_p.add_argument('--codec', choices=['H.265', 'H.264', 'AV1'], default='H.265',
                       help='Video codec (default: H.265)')
    enc_p.add_argument('--crf', type=int, default=20, choices=range(0, 52),
                       metavar='0-51', help='Quality (CRF, default: 20)')
    enc_p.add_argument('--preset', default='medium',
                       choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast',
                                'medium', 'slow', 'slower', 'veryslow'],
                       help='Software encoder preset (default: medium)')
    enc_p.add_argument('--hw', choices=['nvenc', 'qsv', 'amf'], default=None,
                       help='Hardware encoder')
    enc_p.add_argument('--hw-preset', default='p4', help='HW encoder preset (default: p4)')
    enc_p.add_argument('--amf-quality', default='balanced',
                       choices=['speed', 'balanced', 'quality'],
                       help='AMF quality preset (default: balanced)')
    enc_p.add_argument('--qsv-preset', default='medium',
                       choices=['veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
                       help='QSV encoder preset (default: medium)')
    enc_p.add_argument('--resolution', default='Source',
                       help='Target resolution (e.g. "1080p (1920x1080)", "Source")')
    enc_p.add_argument('--deinterlace', default='',
                       help='Deinterlacing filter (Yadif (fast), BWDIF, etc.)')
    enc_p.add_argument('--two-pass', action='store_true', help='Enable two-pass encoding')
    enc_p.add_argument('--bitrate', default='4000k', help='Target bitrate for two-pass (default: 4000k)')
    enc_p.add_argument('--burn-subs', action='store_true', help='Burn subtitles into video')
    enc_p.add_argument('--no-chapters', action='store_true', help='Discard chapter metadata')
    enc_p.add_argument('--preset-name', help='Start from a stock preset name (partial match)')
    enc_p.add_argument('--audio', default='copy',
                       help='Audio codec or "copy" (default: copy)')
    enc_p.add_argument('--audio-bitrate', default='192k', help='Audio bitrate (default: 192k)')
    enc_p.add_argument('--audio-tracks', type=int, nargs='*', default=None,
                       help='Audio track indices to include (default: all)')

    args = parser.parse_args()

    if args.command == 'scan':
        info = scan_source(args.source)
        print_scan(info)

    elif args.command == 'presets':
        list_presets()

    elif args.command == 'encode':
        settings = build_encode_settings(args)

        # Scan source for audio/sub info
        info = scan_source(args.source)
        audio_streams = []
        sub_streams = []
        for s in info.get('streams', []):
            ct = s.get('codec_type', '')
            idx = s.get('index', '?')
            lang = s.get('tags', {}).get('language', 'und')
            codec = s.get('codec_name', '?')
            if ct == 'audio':
                title = s.get('tags', {}).get('title', '')
                label = f'{idx}: {lang} {codec}'
                if title:
                    label += f' ({title})'
                audio_streams.append((idx, label, codec))
            elif ct == 'subtitle':
                title = s.get('tags', {}).get('title', '')
                label = f'{idx}: {lang} {codec}'
                if title:
                    label += f' ({title})'
                sub_streams.append((idx, label, codec))

        # Build audio tracks
        audio_tracks = []
        if args.audio_tracks is not None:
            # Specific tracks
            for idx, _, cname in audio_streams:
                if idx in args.audio_tracks:
                    audio_tracks.append((idx, args.audio, args.audio_bitrate))
        else:
            # All
            for idx, _, cname in audio_streams:
                audio_tracks.append((idx, args.audio, args.audio_bitrate))
        settings['audio_tracks'] = audio_tracks

        # Derive output path
        if args.output:
            out_path = args.output
        else:
            src_path = Path(args.source)
            out_path = str(src_path.parent / f'{src_path.stem}_encoded{src_path.suffix}')

        run_encode(args.source, out_path, settings)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
