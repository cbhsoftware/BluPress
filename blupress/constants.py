"""Theme colors, fonts, UI helpers, and shared encoder/format maps."""

import os
import platform
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Any

try:
    import plyer.notification as _plyer_notif
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

THEMES = {
    'dark': {
        'bg':          '#0c0d0f',
        'panel':       '#151619',
        'panel2':      '#1c1d22',
        'well':        '#08090b',
        'border':      '#282a32',
        'indigo':      '#6366f1',
        'indigo_dim':  '#3730a3',
        'indigo_glow': '#818cf8',
        'indigo_bg':   '#1e1b4b',
        'amber':       '#f59e0b',
        'amber_dim':   '#92400e',
        'amber_glow':  '#fbbf24',
        'amber_bg':    '#451a03',
        'teal':        '#2dd4bf',
        'teal_dim':    '#1a7a72',
        'red':         '#ef4444',
        'red_dim':     '#7f1d1d',
        'green':       '#22c55e',
        'green_dim':   '#14532d',
        'purple':      '#7c3aed',
        'purple_dim':  '#3b0764',
        'white':       '#e2e4ea',
        'mid':         '#787c85',
        'dim':         '#40434a',
        'log_fg':      '#22c55e',
        'red_dot':     '#ff5f56',
        'yellow_dot':  '#ffbd2e',
        'green_dot':   '#27c93f',
        'card_bg':     '#1a1b20',
    },
    'light': {
        'bg':          '#f0f0f2',
        'panel':       '#ffffff',
        'panel2':      '#e8e8ec',
        'well':        '#fafafa',
        'border':      '#ccccdd',
        'indigo':      '#6366f1',
        'indigo_dim':  '#a5b4fc',
        'indigo_glow': '#4338ca',
        'indigo_bg':   '#eef2ff',
        'amber':       '#d97706',
        'amber_dim':   '#fde68a',
        'amber_glow':  '#b45309',
        'amber_bg':    '#fffbeb',
        'teal':        '#0d9488',
        'teal_dim':    '#ccfbf1',
        'red':         '#dc2626',
        'red_dim':     '#fecaca',
        'green':       '#16a34a',
        'green_dim':   '#bbf7d0',
        'purple':      '#7c3aed',
        'purple_dim':  '#ede9fe',
        'white':       '#111111',
        'mid':         '#555566',
        'dim':         '#999aaa',
        'log_fg':      '#16a34a',
        'red_dot':     '#dc2626',
        'yellow_dot':  '#ca8a04',
        'green_dot':   '#16a34a',
        'card_bg':     '#f5f5f7',
    },
}
C: dict[str, str] = dict(THEMES['dark'])

MONO  = ('Courier New', 9)
UI    = ('Courier New', 9)
UI_B  = ('Courier New', 9, 'bold')
TINY  = ('Courier New', 8)
SMALL = ('Courier New', 7)

# ---------------------------------------------------------------------------
# Shared encoder / format maps (used by app.py, cli.py, encoder.py)
# ---------------------------------------------------------------------------

CODEC_MAP_SW: dict[str, str] = {
    'H.265': 'libx265',
    'H.264': 'libx264',
    'AV1':   'libaom-av1',
}

CODEC_MAP_NVENC: dict[str, str] = {
    'H.265': 'hevc_nvenc',
    'H.264': 'h264_nvenc',
    'AV1':   'av1_nvenc',
}

CODEC_MAP_AMF: dict[str, str] = {
    'H.265': 'hevc_amf',
    'H.264': 'h264_amf',
    'AV1':   'av1_amf',
}

CODEC_MAP_QSV: dict[str, str] = {
    'H.265': 'hevc_qsv',
    'H.264': 'h264_qsv',
    'AV1':   'av1_qsv',
}

RES_MAP: dict[str, str] = {
    '4K (3840x2160)':   '3840:2160',
    '1080p (1920x1080)': '1920:1080',
    '720p (1280x720)':  '1280:720',
    '576p (1024x576)':  '1024:576',
    '480p (854x480)':   '854:480',
}

AR_MAP: dict[str, str] = {
    '16:9':    '16/9',
    '4:3':     '4/3',
    '2.35:1':  '2.35',
    '2.39:1':  '2.39',
    '1.85:1':  '1.85',
}

DEINT_MAP: dict[str, str] = {
    'Yadif (fast)':       'yadif=0',
    'Yadif (slow/better)': 'yadif=1',
    'BWDIF':              'bwdif=0',
    'Decomb':             'yadif=2',
    'Bob':                'yadif=1:1',
}

BITMAP_SUB_FORMATS: set[str] = {'dvd_subtitle', 'hdmv_pgs_subtitle', 'dvbsub', 'xsub'}

# Quick-preset map: disk_type -> (codec, crf, preset, resolution)
QUICK_PRESET_MAP: dict[str, tuple[str, int, str, str]] = {
    'Blu-ray': ('H.265', 20, 'medium',   'Source'),
    '4K UHD':  ('H.265', 18, 'slow',     'Source'),
    'DVD':     ('H.264', 22, 'fast',     '480p (854x480)'),
    'HD-DVD':  ('H.264', 20, 'medium',   'Source'),
    'Web':     ('H.265', 24, 'veryfast', '720p (1280x720)'),
}

# Rough size-estimation factors per codec (software)
CODEC_SIZE_FACTOR: dict[str, float] = {
    'H.265': 0.45,
    'H.264': 0.80,
    'AV1':   0.30,
}

# HW size overhead multipliers
HW_SIZE_FACTOR: dict[str, dict[str, float]] = {
    'nvenc': {'H.265': 1.8, 'H.264': 1.5, 'AV1': 2.3},
    'qsv':   {'H.265': 1.5, 'H.264': 1.3, 'AV1': 2.0},
    'amf':   {'H.265': 1.6, 'H.264': 1.4, 'AV1': 2.1},
}

FRAMERATE_MAP: dict[str, str] = {
    'Source':     '',
    '23.976 fps': '24000/1001',
    '24 fps':     '24',
    '25 fps':     '25',
    '29.97 fps':  '30000/1001',
    '30 fps':     '30',
    '50 fps':     '50',
    '59.94 fps':  '60000/1001',
    '60 fps':     '60',
}

HDR_MODES: list[str] = [
    'None (passthrough)',
    'HDR10 Passthrough',
    'Dolby Vision Passthrough',
    'Tonemap HDR→SDR (CPU)',
    'Tonemap HDR→SDR (OpenCL)',
    'Tonemap HDR→SDR (CUDA)',
]

DENOISE_MODES: list[str] = ['None', 'hqdn3d (light)', 'hqdn3d (medium)', 'hqdn3d (strong)', 'nlmeans (light)', 'nlmeans (medium)', 'nlmeans (strong)']

DENOISE_FILTER_MAP: dict[str, str] = {
    'hqdn3d (light)':   'hqdn3d=2:2:3:3',
    'hqdn3d (medium)':  'hqdn3d=4:5:6:6',
    'hqdn3d (strong)':  'hqdn3d=8:10:12:12',
    'nlmeans (light)':  'nlmeans=strength=0.5:patch_size=5:research_size=9',
    'nlmeans (medium)': 'nlmeans=strength=1.0:patch_size=7:research_size=15',
    'nlmeans (strong)': 'nlmeans=strength=2.0:patch_size=9:research_size=21',
}

STABILIZE_MODES: list[str] = ['None', 'Stabilize (light)', 'Stabilize (medium)', 'Stabilize (strong)']

STABILIZE_FILTER_MAP: dict[str, tuple[str, str]] = {
    'Stabilize (light)':  ('vidstabdetect=shakiness=2:accuracy=8:result=transforms.trf', 'vidstabtransform=input=transforms.trf:zoom=0:smoothing=5'),
    'Stabilize (medium)': ('vidstabdetect=shakiness=5:accuracy=15:result=transforms.trf', 'vidstabtransform=input=transforms.trf:zoom=0:smoothing=10'),
    'Stabilize (strong)': ('vidstabdetect=shakiness=10:accuracy=15:result=transforms.trf', 'vidstabtransform=input=transforms.trf:zoom=0:smoothing=20'),
}

SW_PRESET_SPEED_MULTIPLIER: dict[str, float] = {
    'ultrafast':  1.8,
    'superfast':  1.8,
    'veryfast':   1.8,
    'faster':     1.8,
    'fast':       1.8,
    'medium':     1.0,
    'slow':       0.45,
    'slower':     0.45,
    'veryslow':   0.45,
}

# ---------------------------------------------------------------------------
# i18n — language / internationalisation
# ---------------------------------------------------------------------------

LANG_EN: dict[str, str] = {}
LANG_FR: dict[str, str] = {
    'BLUPRESS':           'BLUPRESS',
    'READY':              'PRET',
    'Source':             'Source',
    'Output':             'Sortie',
    'Quick Preset':       'Préréglage rapide',
    'Saved Presets':      'Préréglages sauvegardés',
    'File Estimate':      'Estimation fichier',
    'Encode Queue':       'File d\'attente',
    'Encode Progress':    'Progression',
    'Encode Log':         'Journal',
    'START ENCODE':       'LANCER',
    'CANCEL':             'ANNULER',
    'PAUSE':              'PAUSE',
    'RESUME':             'REPRENDRE',
    'Original':           'Origine',
    'Estimated':          'Estimé',
    'Space Saved':        'Économie',
    'Est. Time':          'Tps estimé',
    'Drop source here...':'Déposer ici...',
    'Browse File':        'Parcourir',
    'Folder':             'Dossier',
    'Scan':               'Analyser',
    'DIR':                'RÉP',
    'FILE':               'FIC',
    'FORMAT':             'FORMAT',
    'Auto-name tokens':   'Auto-nom {titre}_{codec}_{rés}_{crf}',
    'Add Files':          'Ajouter',
    'Remove':             'Retirer',
    'Up':                 'Haut',
    'Down':               'Bas',
    'Clear Done':         'Vider faits',
    'VIDEO':              'VIDÉO',
    'AUDIO':              'AUDIO',
    'SUBTITLES':          'SOUS-TITRES',
    'HARDWARE':           'MATÉRIEL',
    'ADVANCED':           'AVANCÉ',
    'CODEC':              'CODEC',
    'CRF':                'CRF',
    'CPU PRESET':         'PRÉRÉGL CPU',
    'Two-pass encoding':  'Débit cible 2 passes',
    'Target bitrate':     'Débit cible',
    'Copy':               'Copier',
    'COPY CMD':           'COPIER CMD',
    'OUTPUT':             'SORTIE',
    'LOG':                'JOURNAL',
    'Dark theme':         'Thème sombre',
    'Notify':             'Notification',
    'TRACK':              'PISTE',
    'BURN INTO VIDEO':   'GRAVER DANS LA VIDÉO',
    'RESOLUTION':         'RÉSOLUTION',
    'ASPECT':             'RAPPORT',
    'DEINTERLACE':        'DÉSENTRELACER',
    'FRAMERATE':          'FPS',
    'HDR MODE':           'MODE HDR',
    'ANAMORPHIC':         'ANAMORPHOSE',
    'Preserve chapters':  'Conserver chapitres',
    'CROP':               'ROGNE',
    'FFMPEG PATH':        'CHEMIN FFMPEG',
    'Language':           'Langue',
    'Denoise':            'Débruitage',
    'Stabilize':          'Stabilisation',
    '10-bit encoding':    'Encodage 10-bit',
    'Audio only':         'Audio seul',
    'Extract':            'Extraire',
    'Preview':            'Aperçu',
}

LANG_RU: dict[str, str] = {
    'BLUPRESS':           'BLUPRESS',
    'READY':              'ГОТОВ',
    'Source':             'Источник',
    'Output':             'Выход',
    'Quick Preset':       'Быстрый пресет',
    'Saved Presets':      'Сохранённые пресеты',
    'File Estimate':      'Оценка файла',
    'Encode Queue':       'Очередь',
    'Encode Progress':    'Прогресс',
    'Encode Log':         'Журнал',
    'START ENCODE':       'ЗАПУСК',
    'CANCEL':             'ОТМЕНА',
    'PAUSE':              'ПАУЗА',
    'RESUME':             'ПРОДОЛЖИТЬ',
    'Original':           'Исходный',
    'Estimated':          'Оценка',
    'Space Saved':        'Экономия',
    'Est. Time':          'Осталось',
    'Drop source here...':'Перетащите файл...',
    'Browse File':        'Обзор',
    'Folder':             'Папка',
    'Scan':               'Сканировать',
    'DIR':                'ПАПКА',
    'FILE':               'ФАЙЛ',
    'FORMAT':             'ФОРМАТ',
    'Auto-name tokens':   'Авто-имя {назв}_{кодек}_{рзр}_{крф}',
    'Add Files':          'Добавить',
    'Remove':             'Удалить',
    'Up':                 'Вверх',
    'Down':               'Вниз',
    'Clear Done':         'Очистить',
    'VIDEO':              'ВИДЕО',
    'AUDIO':              'АУДИО',
    'SUBTITLES':          'СУБТИТРЫ',
    'HARDWARE':           'ОБОРУДОВАНИЕ',
    'ADVANCED':           'ДОПОЛНИТЕЛЬНО',
    'CODEC':              'КОДЕК',
    'CRF':                'CRF',
    'CPU PRESET':         'ПРЕСЕТ CPU',
    'Two-pass encoding':  'Двухпроходное',
    'Target bitrate':     'Целевой битрейт',
    'Copy':               'Копия',
    'COPY CMD':           'КОПИР. КОМАНДУ',
    'OUTPUT':             'ВЫХОД',
    'LOG':                'ЖУРНАЛ',
    'Dark theme':         'Тёмная тема',
    'Notify':             'Уведомления',
    'TRACK':              'ДОРОЖКА',
    'BURN INTO VIDEO':    'ВСТРОИТЬ В ВИДЕО',
    'RESOLUTION':         'РАЗРЕШЕНИЕ',
    'ASPECT':             'ФОРМАТ',
    'DEINTERLACE':        'ДЕИНТЕРЛЕЙС',
    'FRAMERATE':          'КАДРЫ/С',
    'HDR MODE':           'РЕЖИМ HDR',
    'ANAMORPHIC':         'АНАМОРФ',
    'Preserve chapters':  'Сохранять главы',
    'CROP':               'КАДРИРОВАТЬ',
    'FFMPEG PATH':        'ПУТЬ FFMPEG',
    'Language':           'Язык',
    'Denoise':            'Шумоподавление',
    'Stabilize':          'Стабилизация',
    '10-bit encoding':    '10-бит кодирование',
    'Audio only':         'Только аудио',
    'Extract':            'Извлечь',
    'Preview':            'Просмотр',
}

LANG_DE: dict[str, str] = {
    'BLUPRESS':           'BLUPRESS',
    'READY':              'BEREIT',
    'Source':             'Quelle',
    'Output':             'Ausgabe',
    'Quick Preset':       'Schnellvoreinstellung',
    'Saved Presets':      'Gespeicherte Voreinstellungen',
    'File Estimate':      'Dateischätzung',
    'Encode Queue':       'Codierwarteschlange',
    'Encode Progress':    'Fortschritt',
    'Encode Log':         'Protokoll',
    'START ENCODE':       'START',
    'CANCEL':             'ABBRECHEN',
    'PAUSE':              'PAUSE',
    'RESUME':             'FORTSETZEN',
    'Original':           'Original',
    'Estimated':          'Geschätzt',
    'Space Saved':        'Ersparnis',
    'Est. Time':          'Vorauss. Zeit',
    'Drop source here...':'Hier ablegen...',
    'Browse File':        'Durchsuchen',
    'Folder':             'Ordner',
    'Scan':               'Analysieren',
    'DIR':                'VRZ',
    'FILE':               'DTI',
    'FORMAT':             'FORMAT',
    'Auto-name tokens':   'Auto-Name {Titel}_{Codec}_{Aufl}_{CRF}',
    'Add Files':          'Hinzufügen',
    'Remove':             'Entfernen',
    'Up':                 'Hoch',
    'Down':               'Runter',
    'Clear Done':         'Erledigte löschen',
    'VIDEO':              'VIDEO',
    'AUDIO':              'AUDIO',
    'SUBTITLES':          'UNTERITEL',
    'HARDWARE':           'HARDWARE',
    'ADVANCED':           'ERWEITERT',
    'CODEC':              'CODEC',
    'CRF':                'CRF',
    'CPU PRESET':         'CPU-VORGABE',
    'Two-pass encoding':  'Zwei-Durchgang',
    'Target bitrate':     'Zielbitrate',
    'Copy':               'Kopieren',
    'COPY CMD':           'CMD KOPIEREN',
    'OUTPUT':             'AUSGABE',
    'LOG':                'PROTOKOLL',
    'Dark theme':         'Dunkles Design',
    'Notify':             'Benachrichtigen',
    'TRACK':              'SPUR',
    'BURN INTO VIDEO':   'EINBRENNEN',
    'RESOLUTION':         'AUFLÖSUNG',
    'ASPECT':             'SEITENVERHÄLTNIS',
    'DEINTERLACE':        'ENTFLECHTEN',
    'FRAMERATE':          'BPS',
    'HDR MODE':           'HDR-MODUS',
    'ANAMORPHIC':         'ANAMORPH',
    'Preserve chapters':  'Kapitel erhalten',
    'CROP':               'BESCHNEIDEN',
    'FFMPEG PATH':        'FFMPEG-PFAD',
    'Language':           'Sprache',
    'Denoise':            'Entrauschen',
    'Stabilize':          'Stabilisieren',
    '10-bit encoding':    '10-Bit-Codierung',
    'Audio only':         'Nur Audio',
    'Extract':            'Extrahieren',
    'Preview':            'Vorschau',
}

LANG_MAP: dict[str, dict[str, str]] = {
    'English': LANG_EN,
    'Français': LANG_FR,
    'Deutsch': LANG_DE,
    'Русский': LANG_RU,
}

LANG_NAMES: list[str] = ['English', 'Français', 'Deutsch', 'Русский']

_CURRENT_LANG: str = 'English'

def _(key: str) -> str:
    d = LANG_MAP.get(_CURRENT_LANG, LANG_EN)
    return d.get(key, key)

def set_lang(name: str) -> None:
    global _CURRENT_LANG
    if name in LANG_MAP:
        _CURRENT_LANG = name

# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _lbl(parent: tk.Widget, text: str, fg: str | None = None,
         font: tuple | None = None, anchor: Any = tk.W, **kw: Any) -> tk.Label:
    return tk.Label(parent, text=text, bg=parent['bg'],
                    fg=fg or C['mid'], font=font or UI, anchor=anchor, **kw)


def _sep(parent: tk.Widget, color: str | None = None, h: int = 1) -> tk.Frame:
    return tk.Frame(parent, bg=color or C['border'], height=h)


def _entry(parent: tk.Widget, textvariable: tk.Variable, **kw: Any) -> tk.Entry:
    return tk.Entry(parent, textvariable=textvariable,
                    bg=C['well'], fg=C['white'], insertbackground=C['amber'],
                    relief=tk.FLAT, font=UI,
                    highlightthickness=1,
                    highlightbackground=C['border'],
                    highlightcolor=C['amber'], **kw)


def _combo(parent: tk.Widget, variable: tk.Variable, values: list[str],
           width: int = 14) -> ttk.Combobox:
    return ttk.Combobox(parent, textvariable=variable, values=values,
                        width=width, state='readonly', style='BP.TCombobox')


def _check(parent: tk.Widget, text: str, variable: tk.Variable,
           command: Any = None, fg: str | None = None) -> tk.Checkbutton:
    return tk.Checkbutton(parent, text=text, variable=variable, command=command,
                          bg=parent['bg'], fg=fg or C['mid'],
                          selectcolor=C['panel'],
                          activebackground=parent['bg'], activeforeground=C['amber'],
                          font=UI, relief=tk.FLAT, cursor='hand2')


def _quote_path_for_filter(path: str) -> str:
    if platform.system() == 'Windows':
        path = path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
    else:
        path = path.replace("'", "\\'")
    return f"'{path}'"


def _notify(title: str, message: str) -> None:
    if HAS_PLYER:
        try:
            _plyer_notif.notify(title=title, message=message,
                                app_name='BluPress', timeout=6)
        except Exception:
            pass


def _fmt_size(path: str) -> str:
    try:
        b = Path(path).stat().st_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"
    except Exception:
        return '\u2014'


def _get_ffprobe_path(ffmpeg_path: str) -> str:
    if not ffmpeg_path:
        return 'ffprobe'
    p = Path(ffmpeg_path)
    if p.name == 'ffmpeg':
        return str(p.parent / 'ffprobe')
    if p.name == 'ffmpeg.exe':
        return str(p.parent / 'ffprobe.exe')
    ext = p.suffix
    stem = p.stem.replace('ffmpeg', 'ffprobe')
    return str(p.parent / f'{stem}{ext}')


def _configure_ttk() -> None:
    s = ttk.Style()
    s.theme_use('clam')
    s.configure('BP.TCombobox',
                fieldbackground=C['well'], background=C['well'],
                foreground=C['white'], bordercolor=C['border'],
                arrowcolor=C['amber'], selectbackground=C['amber_dim'],
                selectforeground=C['white'], padding=4)
    s.map('BP.TCombobox',
          fieldbackground=[('readonly', C['well'])],
          foreground=[('readonly', C['white'])],
          bordercolor=[('focus', C['amber'])])
    s.configure('BP.TNotebook', background=C['panel'],
                bordercolor=C['border'], tabmargins=[0, 0, 0, 0])
    s.configure('BP.TNotebook.Tab',
                background=C['well'], foreground=C['dim'],
                font=UI, padding=[14, 6], bordercolor=C['border'])
    s.map('BP.TNotebook.Tab',
          background=[('selected', C['panel2'])],
          foreground=[('selected', C['amber'])],
          bordercolor=[('selected', C['amber'])])
    s.configure('BP.TProgressbar',
                troughcolor=C['well'], background=C['amber'],
                bordercolor=C['border'])
