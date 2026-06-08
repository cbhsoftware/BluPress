"""Theme colors, fonts, and UI helper functions."""

import os
import platform
import tkinter as tk
from tkinter import ttk
from pathlib import Path

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
C = dict(THEMES['dark'])

MONO  = ('Courier New', 9)
UI    = ('Courier New', 9)
UI_B  = ('Courier New', 9, 'bold')
TINY  = ('Courier New', 8)
SMALL = ('Courier New', 7)


def _lbl(parent, text, fg=None, font=None, anchor=tk.W, **kw):
    return tk.Label(parent, text=text, bg=parent['bg'],
                    fg=fg or C['mid'], font=font or UI, anchor=anchor, **kw)


def _sep(parent, color=None, h=1):
    return tk.Frame(parent, bg=color or C['border'], height=h)


def _entry(parent, textvariable, **kw):
    return tk.Entry(parent, textvariable=textvariable,
                    bg=C['well'], fg=C['white'], insertbackground=C['amber'],
                    relief=tk.FLAT, font=UI,
                    highlightthickness=1,
                    highlightbackground=C['border'],
                    highlightcolor=C['amber'], **kw)


def _combo(parent, variable, values, width=14):
    return ttk.Combobox(parent, textvariable=variable, values=values,
                        width=width, state='readonly', style='BP.TCombobox')


def _check(parent, text, variable, command=None, fg=None):
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


def _notify(title: str, message: str):
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


def _configure_ttk():
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
