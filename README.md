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
- **10-bit** video encoding switch
- **Denoising** filter: hqdn3d (quick), nlmeans (best quality)
- **Stabilizing** of video (vidstab), detection, and transforming processes
- **Pure audio** conversion option
- **Subtitles extraction** into a file and importing of external subtitles (in format .srt/.ass)
- **Preview** of video with frame saving in JPEG, PNG, BMP formats
- **Suspend/continue** video encoding
- **Multilingual** interface: English, French, German, Russian
- Chapters support
- Queuing with drag-and-drop reordering
- Preset profile for DVD, Blu-ray, and 4K videos with auto-detection

## Requirements

- **Python 3.10+** (for running from source code)
- **FFmpeg** (with the desired encoder: `libx264`, `libx265`, `hevc_nvenc`, `av1_nvenc`, etc.)

## Run GUI

```bash
python main.py
```

## CLI usage

```bash
python main.py --cli scan input.mkv          # show media info
python main.py --cli presets                 # list available presets
python main.py --cli encode input.mkv -o output.mkv   # encode a file
```

Full CLI help:

```bash
python main.py --cli encode --help
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
