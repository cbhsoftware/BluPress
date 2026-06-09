"""Shared FFmpeg command builder used by both GUI and CLI."""

import platform
from typing import Any

from blupress.constants import (
    CODEC_MAP_SW, CODEC_MAP_NVENC, CODEC_MAP_AMF, CODEC_MAP_QSV,
    RES_MAP, AR_MAP, DEINT_MAP, BITMAP_SUB_FORMATS, FRAMERATE_MAP,
    DENOISE_FILTER_MAP, STABILIZE_FILTER_MAP,
    _quote_path_for_filter,
)


def build_cmd(ffmpeg_path: str, src: str, out_path: str,
              settings: dict[str, Any], pass_num: int = 0) -> list[str]:
    cmd = [ffmpeg_path, '-y', '-i', src]

    if settings.get('audio_only'):
        # Audio-only extraction — no video stream
        audio_tracks = settings.get('audio_tracks', [])
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
        cmd += ['-vn', '-progress', 'pipe:1', '-nostats']
        cmd.append(out_path)
        return cmd

    crf = str(settings['quality'])
    codec = settings['video_codec']
    hw = settings.get('use_nvenc', False) or settings.get('use_qsv', False) or settings.get('use_amf', False)

    if settings.get('two_pass') and not hw:
        bitrate = settings['target_bitrate']
        if codec == 'H.265':
            vc = 'libx265'
            if pass_num == 1:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-x265-params', 'pass=1',
                        '-preset', settings['sw_preset'], '-an', '-f', 'null',
                        '-progress', 'pipe:1', '-nostats']
                cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
                return cmd
            else:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-x265-params', 'pass=2',
                        '-preset', settings['sw_preset']]
        else:
            vc = CODEC_MAP_SW.get(codec, 'libx264')
            if pass_num == 1:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-pass', '1',
                        '-preset' if codec != 'AV1' else '-cpu-used',
                        settings['sw_preset'] if codec != 'AV1' else '4',
                        '-an', '-f', 'null',
                        '-progress', 'pipe:1', '-nostats']
                cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
                return cmd
            else:
                cmd += ['-c:v', vc, '-b:v', bitrate, '-pass', '2',
                        '-preset' if codec != 'AV1' else '-cpu-used',
                        settings['sw_preset'] if codec != 'AV1' else '4']
    elif settings.get('use_nvenc'):
        vc = CODEC_MAP_NVENC.get(codec, 'hevc_nvenc')
        hw_p = settings.get('hw_preset', 'p4').split()[0]
        cmd += ['-c:v', vc, '-preset', hw_p, '-rc', 'vbr', '-cq', crf]
    elif settings.get('use_amf'):
        vc = CODEC_MAP_AMF.get(codec, 'hevc_amf')
        cmd += ['-c:v', vc, '-quality', settings.get('amf_quality', 'balanced'),
                '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf, '-qp_b', crf]
    elif settings.get('use_qsv'):
        vc = CODEC_MAP_QSV.get(codec, 'hevc_qsv')
        cmd += ['-c:v', vc, '-global_quality', crf, '-preset', settings.get('qsv_preset', 'medium')]
    else:
        vc = CODEC_MAP_SW.get(codec, 'libx265')
        if codec == 'AV1':
            cmd += ['-c:v', vc, '-crf', crf, '-cpu-used', '4', '-row-mt', '1']
        else:
            cmd += ['-c:v', vc, '-crf', crf, '-preset', settings['sw_preset']]

    # --- 10-bit encoding ---
    if settings.get('ten_bit'):
        codec_name = settings.get('video_codec', '')
        hw = settings.get('use_nvenc', False) or settings.get('use_qsv', False) or settings.get('use_amf', False)
        if codec_name == 'H.264':
            cmd += ['-profile:v', 'high10', '-pix_fmt', 'yuv420p10le']
        elif hw:
            cmd += ['-pix_fmt', 'p010le']
            if codec_name == 'H.265' and not settings.get('use_nvenc'):
                cmd += ['-profile:v', 'main10']
            elif codec_name == 'H.265':
                cmd += ['-profile:v', 'main10']
        else:
            cmd += ['-pix_fmt', 'yuv420p10le']

    # --- HDR / Dolby Vision passthrough ---
    hdr_mode = settings.get('hdr_mode', 'None (passthrough)')
    if hdr_mode == 'HDR10 Passthrough':
        if any('libx265' in a for a in cmd):
            if '-x265-params' in cmd:
                idx = cmd.index('-x265-params')
                cmd[idx+1] += ':hdr10-opt=1:repeat-headers=1'
            else:
                cmd += ['-x265-params', 'hdr10-opt=1:repeat-headers=1']
        elif settings.get('use_nvenc'):
            cmd += ['-color_primaries', 'bt2020', '-color_trc', 'smpte2084', '-colorspace', 'bt2020nc']
    elif hdr_mode == 'Dolby Vision Passthrough':
        cmd += ['-strict', '-1']

    filters = []
    res = settings.get('resolution', 'Source')
    if res in RES_MAP:
        filters.append(f"scale={RES_MAP[res]}:flags=lanczos")
    if settings.get('use_crop') and settings.get('crop_values'):
        filters.append(f"crop={settings['crop_values']}")
    ar = settings.get('aspect_ratio', 'Source')
    if ar in AR_MAP:
        filters.append(f"setdar={AR_MAP[ar]}")
    elif settings.get('anamorphic'):
        filters.append('setdar=16/9')
    deint = settings.get('deinterlace', 'None')
    if deint in DEINT_MAP:
        filters.append(DEINT_MAP[deint])

    framerate = settings.get('framerate', 'Source')
    fps_val = FRAMERATE_MAP.get(framerate, '')
    if fps_val:
        filters.append(f'fps={fps_val}')

    denoise = settings.get('denoise', 'None')
    if denoise in DENOISE_FILTER_MAP:
        filters.append(DENOISE_FILTER_MAP[denoise])

    stabilize = settings.get('stabilize', 'None')
    if stabilize in STABILIZE_FILTER_MAP:
        st = STABILIZE_FILTER_MAP[stabilize]
        filters.append(st[1])

    if hdr_mode == 'Tonemap HDR→SDR (CPU)':
        filters.append('tonemap=tonemap=hable:desat=2:peak=100,format=yuv420p')
    elif hdr_mode == 'Tonemap HDR→SDR (OpenCL)':
        filters.append('hwupload=opencl,tonemap_opencl=tonemap=hable:desat=2,hwdownload,format=yuv420p')
    elif hdr_mode == 'Tonemap HDR→SDR (CUDA)':
        filters.append('hwupload_cuda,tonemap_cuda=tonemap=hable:desat=2,hwdownload,format=yuv420p')

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


def build_stabilize_detect_cmd(ffmpeg_path: str, src: str,
                                settings: dict[str, Any]) -> list[str] | None:
    stabilize = settings.get('stabilize', 'None')
    if stabilize not in STABILIZE_FILTER_MAP:
        return None
    st = STABILIZE_FILTER_MAP[stabilize]
    cmd = [ffmpeg_path, '-y', '-i', src]
    cmd += ['-vf', st[0], '-f', 'null', '-progress', 'pipe:1', '-nostats']
    cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
    return cmd
