# BluPress

GUI app to encode Blu-ray and DVD video files using FFmpeg.

## Features

- Analyze video files and see stream info (video, audio, subtitles, chapters)
- Video encode: **H.264**, **H.265/HEVC**, or **AV1**
- Hardware acceleration: **NVENC** (NVIDIA), **QSV** (Intel), **AMF** (AMD)
- Audio per-track encode/passthrough with specific codecs/bitrates
- Subtitles burn-in or passthrough
- Scaling/cropping/deinterlace
- CRF slider with estimated file size
- 2-pass encode with target bitrate
- Chapter handling
- Queue processing
- Command line mode for headless use
- Presets for DVD/Blu-ray/4K video with automatic detection

## Requirements

- **Python 3.10+** (for running from source code)
- **FFmpeg** (with the desired encoder: `libx264`, `libx265`, `hevc_nvenc`, `av1_nvenc`, etc.)

## Run GUI

```bash
python main.py
```

## CLI usage

```bash
python main.py --cli -i input.mkv -o output.mkv
```

Full CLI arguments:

```
python main.py --cli --help
```

## Building

### Linux AppImage

```bash
pip install pyinstaller
./build_appimage.sh
```

### Windows

```powershell
pip install -r requirements.txt
pyinstaller BluPress.spec
```

## Licensing

GPLv3
