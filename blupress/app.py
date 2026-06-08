"""BluPress main application class."""

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from blupress.constants import (
    C, THEMES, MONO, UI, UI_B, TINY, SMALL,
    HAS_PLYER, _lbl, _sep, _entry, _combo, _check,
    _quote_path_for_filter, _notify, _fmt_size, _configure_ttk,
)
from blupress.widgets import (
    AmberButton, DropEntry, DropListbox,
    SegmentedControl, VUMeter, MetricCard, Section, AudioTrackRow,
    ToggleSwitch, StatusChip, PillBadge, IndigoBar,
)
from blupress.models import QueueItem
from blupress.presets import STOCK_PRESETS


class BluPress:
    SETTINGS_FILE = Path.home() / '.blupress_presets.json'

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('BLUPRESS')
        self.root.minsize(1000, 820)
        self.root.configure(bg=C['bg'])
        self._set_window_icon()
        _configure_ttk()

        self.source_path     = tk.StringVar()
        self.output_dir      = tk.StringVar()
        self.output_filename = tk.StringVar()
        self.output_format   = tk.StringVar(value='.mkv')
        self.ffmpeg_path     = tk.StringVar(value='')
        self.disk_type       = tk.StringVar(value='Blu-ray')
        self.video_codec     = tk.StringVar(value='H.265')
        self.quality         = tk.IntVar(value=20)
        self.sw_preset       = tk.StringVar(value='medium')
        self.hw_preset       = tk.StringVar(value='p4')
        self.amf_quality     = tk.StringVar(value='balanced')
        self.qsv_preset      = tk.StringVar(value='medium')
        self.resolution      = tk.StringVar(value='Source')
        self.aspect_ratio    = tk.StringVar(value='Source')
        self.anamorphic      = tk.BooleanVar(value=False)
        self.deinterlace     = tk.StringVar(value='None')
        self.use_nvenc       = tk.BooleanVar(value=False)
        self.use_qsv         = tk.BooleanVar(value=False)
        self.use_amf         = tk.BooleanVar(value=False)
        self.sub_track_var   = tk.StringVar(value='None')
        self.sub_burn        = tk.BooleanVar(value=False)
        self.two_pass        = tk.BooleanVar(value=False)
        self.target_bitrate  = tk.StringVar(value='4000k')
        self.use_crop        = tk.BooleanVar(value=False)
        self.crop_values     = tk.StringVar(value='')
        self.keep_chapters   = tk.BooleanVar(value=True)
        self.fn_tokens       = tk.BooleanVar(value=True)
        self.notify_done     = tk.BooleanVar(value=True)
        self.dark_theme      = tk.BooleanVar(value=True)
        self.preset_name     = tk.StringVar(value='')
        self.selected_title  = tk.StringVar(value='')

        self.source_info     = {}
        self.audio_streams   = []
        self.sub_streams     = []
        self.disc_titles     = []
        self.original_size   = 0.0
        self.total_duration  = 0.0
        self._audio_rows     = []

        self.queue           = []
        self.encode_process  = None
        self.is_encoding     = False
        self._start_time     = 0.0
        self._stderr_buf     = []
        self._progress_data  = {}
        self._current_item   = None
        self._current_pass   = 1
        self._out_path_live  = ''

        self.saved_presets   = {}
        self._app_settings   = {}
        self._hw_available   = {'nvenc': True, 'amf': True, 'qsv': True}

        self.STOCK_PRESETS = STOCK_PRESETS
        self._load_settings()
        self._restore_queue()

        # Apply app-level settings
        self.dark_theme.set(self._app_settings.get('dark_theme', True))
        self.notify_done.set(self._app_settings.get('notify_done', True))
        self.ffmpeg_path.set(self._app_settings.get('ffmpeg_path', ''))
        geom = self._app_settings.get('window_geometry', '1200x980')
        try:
            self.root.geometry(geom)
        except Exception:
            self.root.geometry('1200x980')
        if not self.dark_theme.get():
            C.update(THEMES['light'])
            _configure_ttk()
            self.root.configure(bg=C['bg'])

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._build()
        self._bind_shortcuts()

        # Async hardware encoder detection after UI is up
        self.root.after(500, self._detect_hw_encoders)

    # ==================== UI BUILD ====================

    def _build(self):
        outer = tk.Frame(self.root, bg=C['bg'])
        outer.pack(fill=tk.BOTH, expand=True)
        self._topbar(outer)
        body = tk.Frame(outer, bg=C['bg'])
        body.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(body, bg=C['bg'], width=340)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8,4), pady=(0,6))
        left.pack_propagate(False)
        left_canvas = tk.Canvas(left, bg=C['bg'], highlightthickness=0, width=340)
        left_scrollbar = tk.Scrollbar(left, orient=tk.VERTICAL, bg=C['panel2'],
                                       command=left_canvas.yview)
        left_scrollable = tk.Frame(left_canvas, bg=C['bg'])
        left_scrollable.bind('<Configure>',
                             lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        left_canvas_window = left_canvas.create_window((0, 0), window=left_scrollable,
                                                        anchor=tk.NW, width=325)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._left_scrollable = left_scrollable
        self._left_canvas = left_canvas
        if platform.system() == 'Linux':
            def _on_mousewheel_linux(event):
                if event.num == 4:
                    left_canvas.yview_scroll(-3, 'units')
                elif event.num == 5:
                    left_canvas.yview_scroll(3, 'units')
            for seq in ('<Button-4>', '<Button-5>'):
                left_canvas.bind(seq, _on_mousewheel_linux, add='+')
                left_scrollable.bind(seq, _on_mousewheel_linux, add='+')
        else:
            def _on_mousewheel(event):
                left_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
            left_canvas.bind('<MouseWheel>', _on_mousewheel, add='+')
            left_scrollable.bind('<MouseWheel>', _on_mousewheel, add='+')
        left_canvas.bind('<Configure>', lambda e: left_canvas.itemconfig(
            left_canvas_window, width=e.width-4))
        right = tk.Frame(body, bg=C['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,8), pady=(0,6))
        self._left_panel(left_scrollable)
        self._right_panel(right)
        self._statusbar(outer)

    # --- TOPBAR ---

    def _topbar(self, parent):
        bar = tk.Frame(parent, bg='#111111', height=50)
        bar.pack(fill=tk.X); bar.pack_propagate(False)
        # Thick amber stripe on far left
        tk.Frame(bar, bg=C['amber'], width=6).pack(side=tk.LEFT, fill=tk.Y)
        # Title area
        tk.Label(bar, text='BLUPRESS', font=('Courier New', 16, 'bold'),
                 bg='#111111', fg=C['amber']).pack(side=tk.LEFT, padx=(10, 4))
        tk.Label(bar, text='// BLU-RAY & DVD COMPRESSOR',
                 font=('Courier New', 9), bg='#111111', fg='#555566',
                 anchor=tk.W).pack(side=tk.LEFT, padx=(0, 10))
        # Right: 5 small badge boxes (SOURCE, OUTPUT, LIVE SIZE, SAVING, ENCODER)
        badges = tk.Frame(bar, bg='#111111')
        badges.pack(side=tk.RIGHT, padx=10)

        def _badge_box(parent, label, initial, val_color):
            f = tk.Frame(parent, bg=C['panel'], padx=6, pady=2)
            tk.Label(f, text=label, font=('Courier New', 7, 'bold'),
                     bg=C['panel'], fg='#555566').pack()
            lbl = tk.Label(f, text=initial, font=('Courier New', 10, 'bold'),
                           bg=C['panel'], fg=val_color)
            lbl.pack()
            return lbl

        self._badge_src    = _badge_box(badges, 'SOURCE',  '---', C['amber'])
        self._badge_out    = _badge_box(badges, 'OUTPUT',  '---', C['amber'])
        self._badge_live   = _badge_box(badges, 'LIVE SIZE', '---', C['teal'])
        self._badge_save   = _badge_box(badges, 'SAVING',  '---', C['green'])
        self._badge_enc    = _badge_box(badges, 'ENCODER', 'CPU', C['teal'])
        f = tk.Frame(badges, bg=C['panel'], padx=2, pady=2); f.pack(side=tk.LEFT, padx=2)
        # spacer between badge boxes and left
        _sep(parent, C['border'], h=1).pack(fill=tk.X)

    # --- LEFT PANEL ---

    def _left_panel(self, parent):
        # --- Source ---
        src = Section(parent, 'Source'); src.pack(fill=tk.X, pady=(8,4))
        sb = src.body()
        self._src_entry = DropEntry(sb, self.source_path,
                                    on_drop=self._handle_source_drop,
                                    browse_cmd=self._browse_source)
        self._src_entry.configure(bg=C['well'], fg=C['dim'],
                                  insertbackground=C['amber'],
                                  relief=tk.FLAT, font=UI,
                                  highlightthickness=1,
                                  highlightbackground=C['border'],
                                  highlightcolor=C['amber'])
        self._src_entry.pack(fill=tk.X, pady=(0,6))
        self._src_entry.insert(0, 'Drop source here...')
        self._src_entry._placeholder_shown = True
        self._src_entry.bind('<FocusIn>', self._on_entry_focus)
        self._src_entry.bind('<FocusOut>', self._on_entry_unfocus)

        br = tk.Frame(sb, bg=C['panel']); br.pack(fill=tk.X)
        AmberButton(br, 'Browse File', self._browse_source, style='normal', width=90, height=26).pack(side=tk.LEFT, padx=(0,3))
        AmberButton(br, 'Folder',     self._browse_folder, style='normal', width=74, height=26).pack(side=tk.LEFT, padx=(0,3))
        # Teal Scan button
        scan_btn = AmberButton(br, 'Scan', self._load_source_info, style='normal', width=66, height=26)
        scan_btn.pack(side=tk.LEFT)
        scan_btn._label.config(fg=C['teal'])


        # --- Output ---
        out = Section(parent, 'Output'); out.pack(fill=tk.X, pady=(0,4))
        ob = out.body()
        dr = tk.Frame(ob, bg=C['panel']); dr.pack(fill=tk.X, pady=(0,3))
        _lbl(dr, 'DIR', width=3).pack(side=tk.LEFT)
        _entry(dr, self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4,4))
        AmberButton(dr, '...', self._browse_output_dir, style='normal', width=26, height=24).pack(side=tk.LEFT)
        fn = tk.Frame(ob, bg=C['panel']); fn.pack(fill=tk.X, pady=(0,3))
        _lbl(fn, 'FILE', width=3).pack(side=tk.LEFT)
        _entry(fn, self.output_filename).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4,0))
        # Checkbox for auto-name tokens
        tok = tk.Frame(ob, bg=C['panel']); tok.pack(fill=tk.X, pady=(2,0))
        _check(tok, 'Auto-name tokens  {title}_{codec}_{res}_{crf}',
               self.fn_tokens, command=self._refresh_filename).pack(side=tk.LEFT)
        fm = tk.Frame(ob, bg=C['panel']); fm.pack(fill=tk.X, pady=(3,0))
        _lbl(fm, 'FORMAT', width=4).pack(side=tk.LEFT)
        fmt_cb = _combo(fm, self.output_format, ['.mkv', '.mp4'], width=5)
        fmt_cb.pack(side=tk.LEFT, padx=4)

        # --- Quick Preset ---
        pre = Section(parent, 'Quick Preset'); pre.pack(fill=tk.X, pady=(0,4))
        SegmentedControl(pre.body(),
                         ['Blu-ray','4K UHD','DVD','HD-DVD','Web'],
                         self.disk_type, command=self._apply_preset).pack(fill=tk.X)

        # --- Saved Presets ---
        ps = Section(parent, 'Saved Presets'); ps.pack(fill=tk.X, pady=(0,4))
        pb = ps.body()
        pr1 = tk.Frame(pb, bg=C['panel']); pr1.pack(fill=tk.X, pady=(0,3))
        _lbl(pr1, 'Name:', width=5).pack(side=tk.LEFT)
        _entry(pr1, self.preset_name, width=16).pack(side=tk.LEFT, padx=4)
        AmberButton(pr1, 'SAVE', self._save_preset, style='normal', width=50, height=24).pack(side=tk.LEFT)
        pr2 = tk.Frame(pb, bg=C['panel']); pr2.pack(fill=tk.X)
        self._preset_cb = _combo(pr2, tk.StringVar(), [], width=18)
        self._preset_cb.pack(side=tk.LEFT, padx=(0,3))
        AmberButton(pr2, 'LOAD', self._load_preset_by_name, style='normal', width=50, height=24).pack(side=tk.LEFT, padx=(0,3))
        AmberButton(pr2, 'DEL',  self._del_preset,          style='danger',  width=42, height=24).pack(side=tk.LEFT, padx=(0,3))
        self._refresh_preset_cb()

        # --- Estimate ---
        st = Section(parent, 'File Estimate'); st.pack(fill=tk.X, pady=(0,4))
        sg = st.body()
        grid = tk.Frame(sg, bg=C['panel']); grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
        self._stat_orig = MetricCard(grid, 'Original',     '---', C['amber'])
        self._stat_out  = MetricCard(grid, 'Estimated',    '---', C['teal'])
        self._stat_save = MetricCard(grid, 'Space Saved',  '---', C['green'])
        self._stat_eta  = MetricCard(grid, 'Est. Time',    '---', C['white'])
        self._stat_orig.grid(row=0, column=0, sticky=tk.EW, padx=(0,2), pady=(0,2))
        self._stat_out.grid (row=0, column=1, sticky=tk.EW,              pady=(0,2))
        self._stat_save.grid(row=1, column=0, sticky=tk.EW, padx=(0,2))
        self._stat_eta.grid (row=1, column=1, sticky=tk.EW)

        ac = Section(parent, ''); ac.pack(fill=tk.X, pady=(0,6))
        ab = ac.body()
        self._btn_start  = AmberButton(ab, 'START ENCODE',    self._start_queue,   style='primary', width=295, height=38)
        self._btn_start.pack(fill=tk.X, pady=(0,4))
        self._btn_cancel = AmberButton(ab, 'CANCEL',           self._cancel_encode, style='danger',  width=295, height=30)
        self._btn_cancel.pack(fill=tk.X, pady=(0,4))
        self._btn_cancel.config_state(tk.DISABLED)
        row_btns = tk.Frame(ab, bg=C['panel']); row_btns.pack(fill=tk.X)
        AmberButton(row_btns, 'COPY CMD',     self._copy_command,    style='ghost', width=97, height=26).pack(side=tk.LEFT, padx=(0,2))
        AmberButton(row_btns, 'OUTPUT',       self._open_output_dir, style='ghost', width=97, height=26).pack(side=tk.LEFT, padx=(0,2))
        AmberButton(row_btns, 'LOG',          self._export_log,      style='ghost', width=97, height=26).pack(side=tk.LEFT)
        misc = tk.Frame(ab, bg=C['panel']); misc.pack(fill=tk.X, pady=(6,0))
        _check(misc, 'Dark theme', self.dark_theme, command=self._toggle_theme).pack(side=tk.LEFT)
        _check(misc, 'Notify', self.notify_done).pack(side=tk.LEFT, padx=10)

    # --- RIGHT PANEL ---

    def _refresh_queue_list(self):
        self._queue_list.delete(0, tk.END)
        status_chip_colors = {
            QueueItem.STATUS_WAIT: (C['mid'], C['panel2']),
            QueueItem.STATUS_ENC:  (C['amber'], C['amber_bg']),
            QueueItem.STATUS_DONE: (C['green'], C['green_dim']),
            QueueItem.STATUS_ERR:  (C['red'], C['red_dim']),
            QueueItem.STATUS_SKIP: (C['dim'], C['panel2']),
        }
        for i, q in enumerate(self.queue):
            sc_fg, sc_bg = status_chip_colors.get(q.status, (C['mid'], C['panel2']))
            pct_text = f'{q.progress:.0f}%' if q.status == QueueItem.STATUS_ENC else ''
            # Build a display string: status icon + name
            icons = {QueueItem.STATUS_WAIT:'○', QueueItem.STATUS_ENC:'●',
                     QueueItem.STATUS_DONE:'●', QueueItem.STATUS_ERR:'●',
                     QueueItem.STATUS_SKIP:'○'}
            icon = icons.get(q.status, '○')
            label = f'  {icon}  {q.name}'
            self._queue_list.insert(tk.END, label)
            self._queue_list.itemconfig(i, fg=q.status_color())

    def _right_panel(self, parent):
        q_sec = Section(parent, 'Encode Queue'); q_sec.pack(fill=tk.X, pady=(8,0))
        qb = q_sec.body()
        qf = tk.Frame(qb, bg=C['well'], highlightthickness=1,
                      highlightbackground=C['border'])
        qf.pack(fill=tk.X, pady=(0,3))
        qsb = tk.Scrollbar(qf, bg=C['panel2']); qsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._queue_list = DropListbox(qf, height=5,
                                       on_drop=self._handle_queue_drop,
                                       bg=C['well'], fg=C['mid'],
                                       font=MONO, relief=tk.FLAT,
                                       selectbackground=C['amber_dim'],
                                       selectforeground=C['white'],
                                       yscrollcommand=qsb.set)
        self._queue_list.pack(fill=tk.X, padx=4, pady=4)
        self._queue_list.bind('<Button-3>', self._queue_context_menu)
        qsb.config(command=self._queue_list.yview)
        qr = tk.Frame(qb, bg=C['panel']); qr.pack(fill=tk.X, pady=(0,3))
        AmberButton(qr, 'Add Files', self._queue_add,        style='normal', width=80, height=24).pack(side=tk.LEFT, padx=(0,2))
        AmberButton(qr, 'Remove',    self._queue_remove,     style='danger', width=70, height=24).pack(side=tk.LEFT, padx=(0,2))
        AmberButton(qr, 'Up',        self._queue_up,         style='normal', width=45, height=24).pack(side=tk.LEFT, padx=(0,2))
        AmberButton(qr, 'Down',      self._queue_down,       style='normal', width=50, height=24).pack(side=tk.LEFT, padx=(0,2))
        tk.Frame(qr, bg=C['panel']).pack(side=tk.LEFT, expand=True)
        AmberButton(qr, 'Clear Done', self._queue_clear_done, style='normal', width=85, height=24).pack(side=tk.LEFT)

        _sep(parent, C['border']).pack(fill=tk.X, pady=4)

        nb = ttk.Notebook(parent, style='BP.TNotebook')
        nb.pack(fill=tk.X)
        self._tab_video(nb)
        self._tab_audio(nb)
        self._tab_subtitles(nb)
        self._tab_hardware(nb)
        self._tab_advanced(nb)

        _sep(parent, C['border']).pack(fill=tk.X, pady=4)

        # Progress section — VU meter + stats
        pr_sec = Section(parent, 'Encode Progress'); pr_sec.pack(fill=tk.X, pady=(0,4))
        pb = pr_sec.body()
        self._prog_bar = VUMeter(pb)
        self._prog_bar.pack(fill=tk.X, pady=(0,4))
        self._prog_bar.set(0)
        stats_row = tk.Frame(pb, bg=C['panel']); stats_row.pack(fill=tk.X)
        self._prog_pct  = tk.Label(stats_row, text='0%', font=UI_B,
                                   bg=C['panel'], fg=C['amber'], width=6)
        self._prog_pct.pack(side=tk.LEFT)
        self._prog_det  = tk.Label(stats_row, text='00:00:00 / 00:00:00', font=UI,
                                   bg=C['panel'], fg=C['mid'])
        self._prog_det.pack(side=tk.LEFT, padx=6)
        self._prog_fps  = tk.Label(stats_row, text='', font=UI,
                                   bg=C['panel'], fg=C['teal'])
        self._prog_fps.pack(side=tk.LEFT, padx=6)
        self._prog_pass = tk.Label(stats_row, text='', font=TINY,
                                   bg=C['panel'], fg=C['amber'])
        self._prog_pass.pack(side=tk.RIGHT, padx=4)
        # Live size in teal
        self._live_size_lbl = tk.Label(stats_row, text='', font=TINY,
                                       bg=C['panel'], fg=C['teal'])
        self._live_size_lbl.pack(side=tk.RIGHT, padx=4)

        log_sec = Section(parent, 'Encode Log'); log_sec.pack(fill=tk.BOTH, expand=True)
        lf = tk.Frame(log_sec, bg=C['well'],
                      highlightthickness=1, highlightbackground=C['border'])
        lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0,4))
        lsb = tk.Scrollbar(lf, bg=C['panel2']); lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log = tk.Text(lf, bg=C['well'], fg=C['mid'],
                            font=MONO, relief=tk.FLAT,
                            state=tk.DISABLED, yscrollcommand=lsb.set,
                            selectbackground=C['amber_dim'])
        self._log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        lsb.config(command=self._log.yview)
        for tag, fg in [('info',C['mid']),('ok',C['green']),
                        ('warn',C['amber']),('err',C['red']),
                        ('head',C['purple']),('ts',C['dim'])]:
            self._log.tag_config(tag, foreground=fg)
        self._log.tag_config('head', font=UI_B)
        self._log_line('[BLUPRESS] Ready — drag & drop files or add to queue.\n','info')

    def _statusbar(self, parent):
        bar = tk.Frame(parent, bg='#0a0a0a', height=22)
        bar.pack(fill=tk.X); bar.pack_propagate(False)
        # Dim amber stripe on left
        tk.Frame(bar, bg=C['amber_dim'], width=3).pack(side=tk.LEFT, fill=tk.Y)
        self._status = tk.Label(bar, text='READY', font=('Courier New', 8, 'bold'),
                                bg='#0a0a0a', fg=C['dim'], anchor=tk.W)
        self._status.pack(side=tk.LEFT, padx=(8,6))

    # --- TABS ---

    def _tab_video(self, nb):
        tab = tk.Frame(nb, bg=C['panel2'], padx=16, pady=12)
        nb.add(tab, text='  VIDEO  ')
        r1 = tk.Frame(tab, bg=C['panel2']); r1.pack(fill=tk.X, pady=(0,8))
        _lbl(r1, 'CODEC', fg=C['dim'], width=8).pack(side=tk.LEFT)
        SegmentedControl(r1, ['H.265','H.264','AV1'],
                         self.video_codec, command=self._on_codec_change).pack(side=tk.LEFT)
        r2 = tk.Frame(tab, bg=C['panel2']); r2.pack(fill=tk.X, pady=(0,6))
        _lbl(r2, 'CRF', fg=C['dim'], width=8).pack(side=tk.LEFT)
        self._crf_canvas = tk.Canvas(r2, width=330, height=28,
                                     bg=C['panel2'], highlightthickness=0)
        self._crf_canvas.pack(side=tk.LEFT, padx=(0,8))
        self._crf_canvas.bind('<Button-1>',  self._crf_click)
        self._crf_canvas.bind('<B1-Motion>', self._crf_click)
        self._crf_lbl = tk.Label(r2, text='20', font=('Courier New',14,'bold'),
                                 bg=C['panel2'], fg=C['amber'], width=4)
        self._crf_lbl.pack(side=tk.LEFT)
        self._draw_crf_slider()
        hint = tk.Frame(tab, bg=C['panel2']); hint.pack(fill=tk.X, pady=(0,6))
        for t, fg in [('0 lossless',C['teal']),('  18 great',C['green']),
                      ('  23 default',C['mid']),('  28 small',C['amber']),('  51 worst',C['red'])]:
            tk.Label(hint, text=t, font=TINY, bg=C['panel2'], fg=fg).pack(side=tk.LEFT)
        # Two-pass as a card
        two_card = tk.Frame(tab, bg=C['card_bg'],
                            highlightthickness=1, highlightbackground=C['border'])
        two_card.pack(fill=tk.X, pady=(0,6))
        two_inner = tk.Frame(two_card, bg=C['card_bg'], padx=8, pady=6)
        two_inner.pack(fill=tk.X)
        cb_two = _check(two_inner, 'Two-pass encoding (target bitrate)',
                         self.two_pass, command=self._toggle_twopass)
        cb_two.pack(side=tk.LEFT)
        _lbl(two_inner, 'Better quality at controlled file size • ~2x slower • SW only',
             fg=C['dim'], font=TINY).pack(side=tk.LEFT, padx=10)
        self._bitrate_row = tk.Frame(tab, bg=C['panel2'])
        self._bitrate_row.pack(fill=tk.X, pady=(0,6))
        _lbl(self._bitrate_row, 'Target bitrate', fg=C['dim'], width=14).pack(side=tk.LEFT)
        _entry(self._bitrate_row, self.target_bitrate, width=10).pack(side=tk.LEFT, padx=4)
        _lbl(self._bitrate_row, '(e.g. 4000k, 8M)', fg=C['dim'], font=TINY).pack(side=tk.LEFT)
        r4 = tk.Frame(tab, bg=C['panel2']); r4.pack(fill=tk.X)
        _lbl(r4, 'CPU PRESET', fg=C['dim'], width=8).pack(side=tk.LEFT)
        self._sw_preset_cb = _combo(r4, self.sw_preset,
                                    ['ultrafast','superfast','veryfast','faster','fast',
                                     'medium','slow','slower','veryslow'], width=14)
        self._sw_preset_cb.pack(side=tk.LEFT, padx=(0,8))
        self._sw_preset_cb.bind('<<ComboboxSelected>>', lambda e: self._update_estimate())
        _lbl(r4, '(software only)', fg=C['dim'], font=TINY).pack(side=tk.LEFT)
        self._toggle_twopass()

    def _tab_audio(self, nb):
        tab = tk.Frame(nb, bg=C['panel2'], padx=16, pady=12)
        nb.add(tab, text='  AUDIO  ')
        hdr = tk.Frame(tab, bg=C['panel2']); hdr.pack(fill=tk.X, pady=(0,4))
        for txt, w in [('EN','4'),('STREAM','47'),('CODEC','8'),('BITRATE','7')]:
            tk.Label(hdr, text=txt, font=TINY, bg=C['panel2'],
                     fg=C['dim'], width=int(w), anchor=tk.W).pack(side=tk.LEFT, padx=3)
        _sep(tab, C['border']).pack(fill=tk.X, pady=(0,4))
        self._audio_frame = tk.Frame(tab, bg=C['panel2'])
        self._audio_frame.pack(fill=tk.X)
        self._no_audio_lbl = _lbl(self._audio_frame,
                                   'Scan a source to populate audio tracks.',
                                   fg=C['dim'], font=TINY)
        self._no_audio_lbl.pack(anchor=tk.W, pady=4)

    def _tab_subtitles(self, nb):
        tab = tk.Frame(nb, bg=C['panel2'], padx=16, pady=12)
        nb.add(tab, text='  SUBTITLES  ')
        r1 = tk.Frame(tab, bg=C['panel2']); r1.pack(fill=tk.X, pady=(0,8))
        _lbl(r1, 'TRACK', fg=C['dim'], width=12).pack(side=tk.LEFT)
        self._sub_track_cb = _combo(r1, self.sub_track_var, ['None'], width=44)
        self._sub_track_cb.pack(side=tk.LEFT)
        r2 = tk.Frame(tab, bg=C['panel2']); r2.pack(fill=tk.X, pady=(0,6))
        cb_subburn = _check(r2, 'BURN INTO VIDEO (hardsub - permanent)',
                             self.sub_burn)
        cb_subburn.pack(side=tk.LEFT)
        self.tooltip(cb_subburn, 'Permanently embed subtitles into the video frames.\n'
                                 'Cannot be turned off later. Use soft-mux (MKV) for togglable subs.')
        info = tk.Frame(tab, bg=C['panel2'],
                        highlightthickness=1, highlightbackground=C['border'])
        info.pack(fill=tk.X, pady=(4,0))
        _lbl(info,
             'i  Burn OFF = soft-muxed MKV track (toggleable in player).\n'
             '   DVD_SUBTITLE / PGS bitmap burn uses filter_complex overlay.\n'
             '   Text subs (ASS/SRT) use libass subtitles= filter.',
             fg=C['dim'], font=TINY).pack(padx=8, pady=6, anchor=tk.W)

    def _tab_hardware(self, nb):
        tab = tk.Frame(nb, bg=C['panel2'], padx=16, pady=12)
        nb.add(tab, text='  HARDWARE  ')
        # Hardware selector cards
        hw_frame = tk.Frame(tab, bg=C['panel2'])
        hw_frame.pack(fill=tk.X, pady=(0,10))
        hw_opts = [
            ('NVENC',  'NVIDIA',  self.use_nvenc, C['green']),
            ('VCE/AMF','AMD',     self.use_amf,   C['red']),
            ('QSV',    'Intel',   self.use_qsv,   C['teal']),
            ('SW',     'CPU',     None,           C['dim']),
        ]
        self._hw_cards = {}
        for label, subtitle, var, color in hw_opts:
            card = tk.Frame(hw_frame, bg=C['card_bg'], width=80, height=52,
                            highlightthickness=1, highlightbackground=C['border'])
            card.pack(side=tk.LEFT, padx=3)
            card.pack_propagate(False)
            active = (var is not None and var.get()) or (var is None and not
                      any(v.get() for v in [self.use_nvenc, self.use_amf, self.use_qsv]))
            fg_ = color if active else C['dim']
            lbl_bg = C['card_bg']
            tk.Label(card, text=label, font=UI_B, bg=lbl_bg,
                     fg=fg_).pack(pady=(6, 0))
            tk.Label(card, text=subtitle, font=SMALL, bg=lbl_bg,
                     fg=fg_).pack()
            if var is not None:
                card.bind('<Button-1>', lambda e, v=var, l=label: self._hw_card_click(v, l))
                for child in card.winfo_children():
                    child.bind('<Button-1>', lambda e, v=var, l=label: self._hw_card_click(v, l))
            self._hw_cards[label] = card
        # Preset rows
        nvr = tk.Frame(tab, bg=C['panel2']); nvr.pack(fill=tk.X, pady=(0,4))
        _lbl(nvr, 'NVENC PRESET', fg=C['dim'], width=14).pack(side=tk.LEFT)
        _combo(nvr, self.hw_preset,
               ['p1 (fastest)','p2','p3','p4 (balanced)','p5','p6','p7 (best)',
                'slow','medium','fast','hq','hp','bd','ll','llhq','llhp'],
               width=16).pack(side=tk.LEFT)
        amr = tk.Frame(tab, bg=C['panel2']); amr.pack(fill=tk.X, pady=(0,4))
        _lbl(amr, 'AMF QUALITY', fg=C['dim'], width=14).pack(side=tk.LEFT)
        _combo(amr, self.amf_quality, ['speed','balanced','quality'], width=10).pack(side=tk.LEFT, padx=(0,10))
        _lbl(amr, '(-quality flag)', fg=C['dim'], font=TINY).pack(side=tk.LEFT)
        qsr = tk.Frame(tab, bg=C['panel2']); qsr.pack(fill=tk.X, pady=(0,8))
        _lbl(qsr, 'QSV PRESET', fg=C['dim'], width=14).pack(side=tk.LEFT)
        _combo(qsr, self.qsv_preset,
               ['veryfast','faster','fast','medium','slow','slower','veryslow'],
               width=10).pack(side=tk.LEFT)
        # Info card
        info = tk.Frame(tab, bg=C['card_bg'],
                        highlightthickness=1, highlightbackground=C['border'])
        info.pack(fill=tk.X, pady=(6,0))
        _lbl(info,
             'i  One HW encoder active at a time  •  3-5x faster  •  5-15% larger files\n'
             '   Two-pass is software only.  Disabled HW checked at startup.',
             fg=C['dim'], font=TINY).pack(padx=8, pady=6, anchor=tk.W)

    def _tab_advanced(self, nb):
        tab = tk.Frame(nb, bg=C['panel2'], padx=16, pady=12)
        nb.add(tab, text='  ADVANCED  ')
        r1 = tk.Frame(tab, bg=C['panel2']); r1.pack(fill=tk.X, pady=(0,8))
        _lbl(r1, 'RESOLUTION', fg=C['dim'], width=12).pack(side=tk.LEFT)
        res_cb = _combo(r1, self.resolution,
                        ['Source','4K (3840x2160)','1080p (1920x1080)',
                         '720p (1280x720)','576p (1024x576)','480p (854x480)'],
                        width=18)
        res_cb.pack(side=tk.LEFT, padx=(0,14))
        self.tooltip(res_cb, 'Downscale to a target resolution.\n"Source" keeps original frame size.')
        _lbl(r1, 'ASPECT', fg=C['dim'], width=8).pack(side=tk.LEFT)
        _combo(r1, self.aspect_ratio,
               ['Source','16:9','4:3','2.35:1','2.39:1','1.85:1'],
               width=10).pack(side=tk.LEFT)
        r2 = tk.Frame(tab, bg=C['panel2']); r2.pack(fill=tk.X, pady=(0,8))
        _lbl(r2, 'DEINTERLACE', fg=C['dim'], width=12).pack(side=tk.LEFT)
        deint_cb = _combo(r2, self.deinterlace,
                          ['None','Yadif (fast)','Yadif (slow/better)','BWDIF','Decomb','Bob'],
                          width=18)
        deint_cb.pack(side=tk.LEFT)
        self.tooltip(deint_cb, 'Deinterlace methods for interlaced content (e.g. DVDs, TV captures).\n'
                               'Yadif is the most common. BWDIF is a modern alternative.')
        r3 = tk.Frame(tab, bg=C['panel2']); r3.pack(fill=tk.X, pady=(0,8))
        cb_an = _check(r3, 'ANAMORPHIC  (setdar 16:9 - widescreen DVDs stored as 720x576/480)',
                        self.anamorphic)
        cb_an.pack(side=tk.LEFT)
        self.tooltip(cb_an, 'Squares non-square pixels from anamorphic widescreen (DVD).\n'
                            'Sets display aspect ratio to 16:9.')
        r4 = tk.Frame(tab, bg=C['panel2']); r4.pack(fill=tk.X, pady=(0,4))
        cb_chap = _check(r4, 'Preserve chapter markers in output', self.keep_chapters)
        cb_chap.pack(side=tk.LEFT)
        self.tooltip(cb_chap, 'Keeps chapter markers from the source in the output file.')
        crop_sec = tk.Frame(tab, bg=C['panel2'],
                            highlightthickness=1, highlightbackground=C['border'])
        crop_sec.pack(fill=tk.X, pady=(6,0))
        crop_hdr = tk.Frame(crop_sec, bg=C['panel2']); crop_hdr.pack(fill=tk.X, padx=8, pady=(6,4))
        _lbl(crop_hdr, 'CROP DETECTION', fg=C['amber'], font=UI_B).pack(side=tk.LEFT)
        cr = tk.Frame(crop_sec, bg=C['panel2']); cr.pack(fill=tk.X, padx=8, pady=(0,8))
        cb_crop = _check(cr, 'Apply detected crop', self.use_crop)
        cb_crop.pack(side=tk.LEFT, padx=(0,10))
        self.tooltip(cb_crop, 'Automatically remove black bars by cropping.\n'
                              'Run "Detect Crop" first to detect values.')
        AmberButton(cr, 'DETECT CROP', self._detect_crop,
                    style='teal', width=120, height=26).pack(side=tk.LEFT, padx=(0,8))
        self._crop_lbl = tk.Label(cr, text='---', font=MONO,
                                  bg=C['panel2'], fg=C['teal'])
        self._crop_lbl.pack(side=tk.LEFT)
        ff = tk.Frame(tab, bg=C['panel2'])
        ff.pack(fill=tk.X, pady=(10,0))
        ff_entry_row = tk.Frame(ff, bg=C['panel2'],
                                highlightthickness=1, highlightbackground=C['border'])
        ff_entry_row.pack(fill=tk.X, padx=0, pady=4)
        _lbl(ff_entry_row, 'FFMPEG PATH', fg=C['dim'], width=12).pack(side=tk.LEFT, padx=4)
        ff_entry = _entry(ff_entry_row, self.ffmpeg_path, width=28)
        ff_entry.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.tooltip(ff_entry, 'Custom path to ffmpeg executable.\n'
                               'Leave empty to use the system PATH.\n'
                               'ffprobe is auto-detected from the same directory.')
        lbl_ff = tk.Label(ff_entry_row, text='(leave empty for PATH)',
                          font=TINY, bg=C['panel2'], fg=C['dim'])
        lbl_ff.pack(side=tk.LEFT, padx=4)

    # ==================== DROP HANDLERS ====================

    def _on_entry_focus(self, event):
        self._src_entry.delete(0, tk.END)
        self._src_entry.configure(fg=C['white'])
        self._src_entry._placeholder_shown = False
        self.source_path.set('')

    def _on_entry_unfocus(self, event):
        current = self._src_entry.get().strip()
        if not current or current.startswith('Drop'):
            self._src_entry.delete(0, tk.END)
            self._src_entry.insert(0, 'Drop source here...')
            self._src_entry.configure(fg=C['dim'])
            self._src_entry._placeholder_shown = True
            self.source_path.set('')

    def _handle_source_drop(self, files):
        if files:
            if len(files) > 1:
                for f in files:
                    if os.path.isfile(f) and not any(q.path == f for q in self.queue):
                        item = QueueItem(f)
                        self._snapshot_item_settings(item)
                        self.queue.append(item)
                self._refresh_queue_list()
                self._persist_settings()
                self._log_ts(f'Added {len(files)} files to queue via drag-drop', 'ok')
                self.source_path.set(files[0])
            else:
                self.source_path.set(files[0])
                self._load_source_info()

    def _handle_queue_drop(self, files):
        added = 0
        for f in files:
            if os.path.isfile(f) and not any(q.path == f for q in self.queue):
                item = QueueItem(f)
                self._snapshot_item_settings(item)
                self.queue.append(item)
                added += 1
        if added:
            self._refresh_queue_list()
            self._persist_settings()
            self._log_ts(f'Added {added} file(s) to queue via drag-drop', 'ok')

    # ==================== UTILITY ====================

    def _log_line(self, msg, tag='info'):
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, msg, tag)
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _log_ts(self, msg, tag='info'):
        ts = time.strftime('%H:%M:%S')
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, f'[{ts}] ', 'ts')
        self._log.insert(tk.END, msg + '\n', tag)
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _set_status(self, msg):
        self._status.config(text=msg.upper())

    def _ts(self):
        return time.strftime('%H:%M:%S')

    # ==================== THEME TOGGLE ====================

    def _toggle_theme(self):
        key = 'dark' if self.dark_theme.get() else 'light'
        C.update(THEMES[key])
        _configure_ttk()
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        self._build()
        self.root.after(100, self._update_hw_ui)
        self._save_app_settings()

    # ==================== CRF SLIDER ====================

    def _draw_crf_slider(self):
        c = self._crf_canvas; c.delete('all')
        W, H = 330, 28; val = self.quality.get()
        frac = val / 51.0; x = int(frac * (W-16)) + 8
        c.create_rectangle(8, H//2-2, W-8, H//2+2, fill=C['well'], outline='')
        steps = 60
        for i in range(steps):
            f = i/steps; gx1 = 8 + f*(W-16); gx2 = gx1 + (W-16)/steps + 1
            r2=int(0x40+(0x99-0x40)*f); g2=int(0x46+(0x66-0x46)*f); b2=int(0xf1-(0xf1-0x99)*f)
            col = f'#{r2:02x}{g2:02x}{b2:02x}'
            if gx1 <= x:
                c.create_rectangle(gx1, H//2-2, min(gx2,x), H//2+2, fill=col, outline='')
        c.create_oval(x-8, 4, x+8, H-4, fill=C['amber'], outline=C['amber_glow'], width=1)
        c.create_text(x, H//2, text=str(val), fill=C['white'], font=('Courier New',7,'bold'))

    def _crf_click(self, e):
        W = 330; frac = max(0.0, min(1.0, (e.x-8)/(W-16)))
        val = int(round(frac*51))
        self.quality.set(val); self._crf_lbl.config(text=str(val))
        self._draw_crf_slider(); self._update_estimate()

    # ==================== TWO-PASS TOGGLE ====================

    def _toggle_twopass(self):
        hw = self.use_nvenc.get() or self.use_amf.get() or self.use_qsv.get()
        if self.two_pass.get() and hw:
            self.two_pass.set(False)
            messagebox.showinfo('Two-pass', 'Two-pass is only available with software encoding.')

    # ==================== FILE BROWSING ====================

    def _browse_source(self):
        initial = self._app_settings.get('last_source_dir')
        f = filedialog.askopenfilename(
            title='Select source file',
            initialdir=initial,
            filetypes=[('Media files','*.iso *.mkv *.m2ts *.ts *.vob *.mp4 *.avi'),
                       ('All files','*.*')])
        if f:
            self.source_path.set(f)
            self._app_settings['last_source_dir'] = str(Path(f).parent)
            self._save_app_settings()
            self._load_source_info()

    def _browse_folder(self):
        initial = self._app_settings.get('last_source_dir')
        d = filedialog.askdirectory(title='Select disc folder / VIDEO_TS / BDMV', initialdir=initial)
        if d:
            self.source_path.set(d)
            self._app_settings['last_source_dir'] = str(Path(d).parent)
            self._save_app_settings()
            self._load_source_info()

    def _browse_output_dir(self):
        initial = self._app_settings.get('last_output_dir')
        d = filedialog.askdirectory(title='Choose output directory', initialdir=initial)
        if d:
            self.output_dir.set(d)
            self._app_settings['last_output_dir'] = d
            self._save_app_settings()

    # ==================== QUEUE ====================

    def _queue_add(self):
        files = filedialog.askopenfilenames(
            title='Add files to queue',
            filetypes=[('Media files','*.iso *.mkv *.m2ts *.ts *.vob *.mp4 *.avi'),
                       ('All files','*.*')])
        for f in files:
            if not any(q.path == f for q in self.queue):
                item = QueueItem(f)
                self._snapshot_item_settings(item)
                self.queue.append(item)
        self._refresh_queue_list()
        self._persist_settings()

    def _queue_remove(self):
        sel = self._queue_list.curselection()
        if not sel: return
        idx = sel[0]
        if self.queue[idx].status == QueueItem.STATUS_ENC:
            messagebox.showwarning('Queue','Cannot remove an actively encoding item.'); return
        del self.queue[idx]; self._refresh_queue_list(); self._persist_settings()

    def _queue_up(self):
        sel = self._queue_list.curselection()
        if not sel or sel[0] == 0: return
        i = sel[0]; self.queue[i-1], self.queue[i] = self.queue[i], self.queue[i-1]
        self._refresh_queue_list(); self._queue_list.selection_set(i-1)
        self._persist_settings()

    def _queue_down(self):
        sel = self._queue_list.curselection()
        if not sel or sel[0] >= len(self.queue)-1: return
        i = sel[0]; self.queue[i], self.queue[i+1] = self.queue[i+1], self.queue[i]
        self._refresh_queue_list(); self._queue_list.selection_set(i+1)
        self._persist_settings()

    def _queue_clear_done(self):
        self.queue = [q for q in self.queue if q.status not in
                      (QueueItem.STATUS_DONE, QueueItem.STATUS_ERR, QueueItem.STATUS_SKIP)]
        self._refresh_queue_list(); self._persist_settings()

    # ==================== SOURCE SCANNING ====================

    def _load_source_info(self):
        src = self.source_path.get().strip()
        if not src: return
        self._set_status('Scanning source...')
        threading.Thread(target=self._scan_worker, args=(src,), daemon=True).start()

    def _scan_worker(self, src):
        try:
            cmd = [self._get_ffprobe(),'-v','quiet','-print_format','json',
                   '-show_streams','-show_format','-show_chapters', src]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                stderr = r.stderr.strip()[:500] if r.stderr else 'unknown error'
                self.root.after(0, lambda e=stderr: (
                    self._set_status('ffprobe failed'),
                    self._log_ts(f'ffprobe error:\n{e}', 'err'),
                ))
                return
            if not r.stdout.strip():
                self.root.after(0, lambda: (
                    self._set_status('ffprobe returned empty output'),
                    self._log_ts('ffprobe returned no output - may be corrupted or invalid file', 'err'),
                ))
                return
            try:
                info = json.loads(r.stdout)
            except json.JSONDecodeError as e:
                self.root.after(0, lambda: (
                    self._set_status('ffprobe output not valid JSON'),
                    self._log_ts(f'JSON decode error: {e}\nRaw: {r.stdout[:300]}', 'err'),
                ))
                return
            self.root.after(0, lambda: self._process_scan(info, src))
        except FileNotFoundError:
            self.root.after(0, lambda: messagebox.showerror(
                'FFmpeg not found', 'Install FFmpeg and add it to PATH.'))
        except Exception as e:
            self.root.after(0, lambda e=e: (
                self._set_status(f'Scan error'),
                self._log_ts(f'Scan error: {e}', 'err'),
            ))

    def _process_scan(self, info, src):
        self.source_info   = info
        self.audio_streams = []
        self.sub_streams   = []
        vid = None
        for s in info.get('streams', []):
            ct    = s.get('codec_type','')
            idx   = s.get('index','?')
            lang  = s.get('tags',{}).get('language','und')
            title = s.get('tags',{}).get('title','')
            cname = s.get('codec_name','?')
            if ct == 'video' and vid is None:
                vid = s
            elif ct == 'audio':
                codec = cname.upper()
                ch    = s.get('channels','?')
                label = f'[{idx}] {codec} {ch}ch - {lang}'
                if title: label += f' ({title})'
                self.audio_streams.append((idx, label, cname))
            elif ct == 'subtitle':
                codec = cname.upper()
                label = f'[{idx}] {codec} - {lang}'
                if title: label += f' ({title})'
                self.sub_streams.append((idx, label, cname))
        chapters = info.get('chapters', [])
        fmt = info.get('format', {})
        try:    self.total_duration = float(fmt.get('duration', 0))
        except: self.total_duration = 0.0
        try:    self.original_size = int(fmt.get('size', 0)) / (1024**3)
        except: self.original_size = 0.0
        self._sub_track_cb['values'] = ['None'] + [l for _,l,_ in self.sub_streams]
        self.sub_track_var.set('None')
        for w in self._audio_rows: w.destroy()
        self._audio_rows = []
        self._no_audio_lbl.pack_forget()
        if self.audio_streams:
            for idx, label, _ in self.audio_streams:
                row = AudioTrackRow(self._audio_frame, idx, label)
                row.pack(fill=tk.X, pady=1)
                self._audio_rows.append(row)
            if self._audio_rows:
                self._audio_rows[0].enabled.set(True)
        else:
            self._no_audio_lbl.pack(anchor=tk.W, pady=4)
        self.output_dir.set(str(Path(src).parent))
        self._refresh_filename()
        h=int(self.total_duration//3600); m=int((self.total_duration%3600)//60); s=int(self.total_duration%60)
        self._log_ts('-'*44, 'head')
        self._log_ts(f'File     : {Path(src).name}', 'warn')
        self._log_ts(f'Size     : {self.original_size:.2f} GB', 'ok')
        self._log_ts(f'Duration : {h:02d}:{m:02d}:{s:02d}', 'ok')
        if vid:
            w = vid.get('width', 0)
            h = vid.get('height', 0)
            self._log_ts(f'Video    : {vid.get("codec_name","?").upper()} '
                         f'{w}x{h} '
                         f'@{vid.get("r_frame_rate","?")} fps', 'ok')
            if w > 0 and h > 0:
                auto_disk = '4K UHD' if w >= 3840 else 'Blu-ray' if w >= 1920 else 'DVD'
                if auto_disk != self.disk_type.get():
                    self.disk_type.set(auto_disk)
                    self._apply_preset()
                    self._log_ts(f'Auto-detected source as {auto_disk}', 'ok')
        for _,al,_ in self.audio_streams: self._log_ts(f'Audio    : {al}', 'info')
        for _,sl,_ in self.sub_streams:   self._log_ts(f'Sub      : {sl}', 'info')
        if chapters:
            self._log_ts(f'Chapters : {len(chapters)} found', 'ok')
        self._log_ts('-'*44, 'head')
        self._badge_src.config(text=f'{self.original_size:.2f} GB')
        self._update_estimate()
        self._set_status(f'Loaded: {Path(src).name} ({self.original_size:.2f} GB)')

    # ==================== CROP DETECTION ====================

    def _detect_crop(self):
        src = self.source_path.get().strip()
        if not src:
            messagebox.showwarning('Crop detect', 'Load a source file first.')
            return
        self._crop_lbl.config(text='Detecting...', fg=C['amber'])
        threading.Thread(target=self._cropdetect_worker, args=(src,), daemon=True).start()

    def _cropdetect_worker(self, src):
        try:
            seek = max(10, int(self.total_duration * 0.10))
            cmd = [self._get_ffmpeg(),'-ss', str(seek),'-i', src,
                   '-t','300','-vf','cropdetect=24:16:0',
                   '-f','null','-']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and r.stderr:
                self.root.after(0, lambda: (
                    self._log_ts(f'cropdetect stderr:\n{r.stderr.strip()[:500]}', 'err'),
                ))
            matches = re.findall(r'crop=(\d+:\d+:\d+:\d+)', r.stderr)
            if matches:
                crop = matches[-1]
                self.crop_values.set(crop)
                self.root.after(0, lambda c=crop: self._crop_lbl.config(
                    text=f'crop={c}', fg=C['teal']))
                self.root.after(0, lambda: self.use_crop.set(True))
            else:
                self.root.after(0, lambda: self._crop_lbl.config(
                    text='No crop detected', fg=C['dim']))
        except Exception as e:
            self.root.after(0, lambda: self._crop_lbl.config(
                text=f'Error: {e}', fg=C['red']))

    # ==================== FILENAME TOKENS ====================

    def _refresh_filename(self):
        src = self.source_path.get().strip()
        stem = Path(src).stem if src else 'output'
        if self.fn_tokens.get():
            codec = self.video_codec.get().replace('.','')
            res   = self.resolution.get().split()[0] if self.resolution.get() != 'Source' else 'src'
            crf   = self.quality.get()
            self.output_filename.set(f'{stem}_{codec}_{res}_crf{crf}')
        else:
            self.output_filename.set(f'{stem}_compressed')

    # ==================== SIZE ESTIMATE ====================

    def _update_estimate(self, *_):
        self._refresh_filename()
        if self.original_size == 0:
            for w in [self._stat_orig,self._stat_out,self._stat_save,self._stat_eta]: w.set('---')
            return
        crf    = self.quality.get()
        codec  = self.video_codec.get()
        preset = self.sw_preset.get()
        cf   = {'H.265':0.45,'H.264':0.80,'AV1':0.30}.get(codec, 0.50)
        qf   = (51-crf)/51.0
        if self.use_nvenc.get():
            hwf = {'H.265':1.8,'H.264':1.5,'AV1':2.3}.get(codec, 1.8)
        elif self.use_qsv.get():
            hwf = {'H.265':1.5,'H.264':1.3,'AV1':2.0}.get(codec, 1.5)
        elif self.use_amf.get():
            hwf = {'H.265':1.6,'H.264':1.4,'AV1':2.1}.get(codec, 1.6)
        else:
            hwf = 1.0
        ratio = max(0.02, min(cf*qf*hwf, 1.5))
        est   = self.original_size * ratio
        saving = (1.0-ratio)*100.0
        speed = 2.5
        if self.use_nvenc.get() or self.use_qsv.get() or self.use_amf.get():
            speed *= 3.5
        if preset in ['ultrafast','superfast','veryfast','faster','fast']: speed *= 1.8
        elif preset in ['slow','slower','veryslow']: speed *= 0.45
        if codec == 'AV1': speed *= 0.25
        eta = max(1, self.original_size / speed)
        self._stat_orig.set(f'{self.original_size:.2f} GB')
        self._stat_out.set(f'{est:.2f} GB')
        self._stat_save.set(f'{saving:.1f}%', color=C['green'] if saving>0 else C['red'])
        self._stat_eta.set(f'~{int(eta)} min')
        self._badge_src.config(text=f'{self.original_size:.2f} GB' if self.original_size > 0 else '---')
        self._badge_out.config(text=f'{est:.2f} GB')
        self._badge_save.config(text=f'{saving:.1f}%')

    # ==================== PRESETS ====================

    def _apply_preset(self):
        p = self.disk_type.get()
        MAP = {'Blu-ray':('H.265',20,'medium','Source'),
               '4K UHD': ('H.265',18,'slow',  'Source'),
               'DVD':    ('H.264',22,'fast',  '480p (854x480)'),
               'HD-DVD': ('H.264',20,'medium','Source'),
               'Web':    ('H.265',24,'veryfast','720p (1280x720)')}
        codec,crf,preset,res = MAP.get(p,('H.265',20,'medium','Source'))
        self.video_codec.set(codec); self.quality.set(crf)
        self._crf_lbl.config(text=str(crf)); self._draw_crf_slider()
        self.sw_preset.set(preset); self.resolution.set(res)
        self._update_estimate()
        self._log_ts(f'Preset applied: {p}', 'warn')

    def _settings_snapshot(self):
        return {
            'video_codec':   self.video_codec.get(),
            'quality':       self.quality.get(),
            'sw_preset':     self.sw_preset.get(),
            'hw_preset':     self.hw_preset.get(),
            'amf_quality':   self.amf_quality.get(),
            'qsv_preset':    self.qsv_preset.get(),
            'resolution':    self.resolution.get(),
            'aspect_ratio':  self.aspect_ratio.get(),
            'anamorphic':    self.anamorphic.get(),
            'deinterlace':   self.deinterlace.get(),
            'use_nvenc':     self.use_nvenc.get(),
            'use_qsv':       self.use_qsv.get(),
            'use_amf':       self.use_amf.get(),
            'sub_track':     self.sub_track_var.get(),
            'sub_burn':      self.sub_burn.get(),
            'two_pass':      self.two_pass.get(),
            'target_bitrate':self.target_bitrate.get(),
            'use_crop':      self.use_crop.get(),
            'crop_values':   self.crop_values.get(),
            'keep_chapters': self.keep_chapters.get(),
        }

    def _set_window_icon(self):
        try:
            base = getattr(sys, '_MEIPASS', Path(__file__).parent.parent)
            ico = Path(base) / 'favicon.ico'
            if ico.exists():
                self.root.iconbitmap(str(ico))
                return
            png = Path(base) / 'favicon.png'
            if png.exists():
                img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, img)
        except Exception:
            pass

    def _apply_settings(self, s: dict):
        self.video_codec.set(s.get('video_codec','H.265'))
        self.quality.set(s.get('quality',20))
        self._crf_lbl.config(text=str(s.get('quality',20)))
        self._draw_crf_slider()
        self.sw_preset.set(s.get('sw_preset','medium'))
        self.hw_preset.set(s.get('hw_preset','p4'))
        self.amf_quality.set(s.get('amf_quality','balanced'))
        self.qsv_preset.set(s.get('qsv_preset','medium'))
        self.resolution.set(s.get('resolution','Source'))
        self.aspect_ratio.set(s.get('aspect_ratio','Source'))
        self.anamorphic.set(s.get('anamorphic',False))
        self.deinterlace.set(s.get('deinterlace','None'))
        self.use_nvenc.set(s.get('use_nvenc',False))
        self.use_qsv.set(s.get('use_qsv',False))
        self.use_amf.set(s.get('use_amf',False))
        self.sub_track_var.set(s.get('sub_track','None'))
        self.sub_burn.set(s.get('sub_burn',False))
        self.two_pass.set(s.get('two_pass',False))
        self.target_bitrate.set(s.get('target_bitrate','4000k'))
        self.use_crop.set(s.get('use_crop',False))
        self.crop_values.set(s.get('crop_values',''))
        self.keep_chapters.set(s.get('keep_chapters',True))
        self._toggle_hw()
        self._update_estimate()

    def _save_preset(self):
        name = self.preset_name.get().strip()
        if not name: messagebox.showwarning('Presets','Enter a name first.'); return
        self.saved_presets[name] = self._settings_snapshot()
        self._persist_settings()
        self._refresh_preset_cb()
        self._log_ts(f'Preset saved: {name}', 'ok')

    def _load_preset_by_name(self):
        name = self._preset_cb.get()
        if not name or name.startswith('--'): return
        stock_settings = None
        for pname, settings in self.STOCK_PRESETS:
            if pname == name:
                stock_settings = settings
                break
        if stock_settings:
            self._apply_settings(stock_settings)
            self._log_ts(f'Stock preset loaded: {name}', 'ok')
        elif name in self.saved_presets:
            self._apply_settings(self.saved_presets[name])
            self._log_ts(f'User preset loaded: {name}', 'ok')

    def _del_preset(self):
        name = self._preset_cb.get()
        if not name or name.startswith('--'): return
        is_stock = any(pname == name for pname, settings in self.STOCK_PRESETS if settings is not None)
        if is_stock:
            self._log_ts(f'Cannot delete stock preset: {name}', 'warn')
            return
        if name not in self.saved_presets: return
        del self.saved_presets[name]
        self._persist_settings()
        self._refresh_preset_cb()
        self._log_ts(f'Preset deleted: {name}', 'warn')

    def _refresh_preset_cb(self):
        stock = [name for name, _ in self.STOCK_PRESETS]
        user  = sorted(self.saved_presets.keys())
        names = stock + (['-- User Presets --'] + user if user else [])
        self._preset_cb['values'] = names
        first_real = next((name for name, settings in self.STOCK_PRESETS if settings is not None), None)
        if first_real:
            self._preset_cb.set(first_real)

    def _load_settings(self):
        try:
            if self.SETTINGS_FILE.exists():
                raw = json.loads(self.SETTINGS_FILE.read_text())
                if isinstance(raw, dict):
                    if 'presets' in raw:
                        self.saved_presets = raw.get('presets', {})
                        self._app_settings = raw.get('app', {})
                        self._queue_raw = raw.get('queue', [])
                    else:
                        self.saved_presets = raw
                        self._app_settings = {}
                        self._queue_raw = []
        except Exception:
            self.saved_presets = {}
            self._app_settings = {}
            self._queue_raw = []

    def _persist_settings(self):
        try:
            data = {
                'presets': self.saved_presets,
                'app': self._app_settings,
                'queue': [item.to_dict() for item in self.queue],
            }
            self.SETTINGS_FILE.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def _save_app_settings(self):
        self._app_settings['dark_theme'] = self.dark_theme.get()
        self._app_settings['notify_done'] = self.notify_done.get()
        self._app_settings['ffmpeg_path'] = self.ffmpeg_path.get()
        try:
            self._app_settings['window_geometry'] = self.root.geometry()
        except Exception:
            pass
        self._persist_settings()

    def _on_close(self):
        self._save_app_settings()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _restore_queue(self):
        for qd in getattr(self, '_queue_raw', []):
            try:
                item = QueueItem.from_dict(qd)
                if item.status in (QueueItem.STATUS_ENC, QueueItem.STATUS_DONE,
                                   QueueItem.STATUS_ERR, QueueItem.STATUS_SKIP):
                    continue
                self.queue.append(item)
            except Exception:
                pass
        self._queue_raw = []

    # ==================== HARDWARE DETECTION ====================

    def _detect_hw_encoders(self):
        def _probe():
            available = {'nvenc': False, 'amf': False, 'qsv': False}
            try:
                r = subprocess.run([self._get_ffmpeg(), '-encoders'], capture_output=True, text=True, timeout=10)
                for line in r.stdout.split('\n'):
                    if 'hevc_nvenc' in line or 'h264_nvenc' in line:
                        available['nvenc'] = True
                    if 'hevc_amf' in line or 'h264_amf' in line:
                        available['amf'] = True
                    if 'hevc_qsv' in line or 'h264_qsv' in line:
                        available['qsv'] = True
            except Exception:
                pass
            self._hw_available = available
            self.root.after(0, self._update_hw_ui)

    def _update_hw_ui(self):
        hw = self._hw_available
        for label, avail in [('NVENC', hw['nvenc']), ('VCE/AMF', hw['amf']),
                              ('QSV', hw['qsv'])]:
            card = self._hw_cards.get(label)
            if card:
                state = tk.NORMAL if avail else tk.DISABLED
                for child in card.winfo_children():
                    try:
                        child.config(state=state)
                    except Exception:
                        pass
                card.config(cursor='hand2' if avail else 'arrow')

    def _hw_card_click(self, var, label):
        if label == 'SW':
            self.use_nvenc.set(False); self.use_amf.set(False); self.use_qsv.set(False)
        else:
            var.set(True)
        self._toggle_hw()
        self._refresh_hw_cards()

    def _refresh_hw_cards(self):
        active_map = {
            'NVENC': self.use_nvenc.get(),
            'VCE/AMF': self.use_amf.get(),
            'QSV': self.use_qsv.get(),
            'SW': not (self.use_nvenc.get() or self.use_amf.get() or self.use_qsv.get()),
        }
        color_map = {'NVENC': C['green'], 'VCE/AMF': C['red'],
                     'QSV': C['teal'], 'SW': C['dim']}
        for label, card in self._hw_cards.items():
            is_active = active_map.get(label, False)
            fg = color_map.get(label, C['dim'])
            col = fg if is_active else C['dim']
            for child in card.winfo_children():
                try:
                    child.config(fg=col)
                except Exception:
                    pass

    # ==================== HARDWARE TOGGLE ====================

    def _toggle_hw(self):
        if self.use_nvenc.get():
            self.use_qsv.set(False); self.use_amf.set(False)
            label = 'NVENC'
        elif self.use_amf.get():
            self.use_nvenc.set(False); self.use_qsv.set(False)
            label = 'AMF'
        elif self.use_qsv.get():
            self.use_nvenc.set(False); self.use_amf.set(False)
            label = 'QSV'
        else:
            label = 'SW'
        self._badge_enc.config(text=label)
        self._update_estimate()

    # ==================== FFMPEG COMMAND BUILDER ====================

    def _build_cmd(self, src: str, out_path: str, settings: dict, pass_num: int = 0):
        cmd   = [self._get_ffmpeg(), '-y', '-i', src]
        crf   = str(settings['quality'])
        codec = settings['video_codec']
        hw    = settings['use_nvenc'] or settings['use_qsv'] or settings['use_amf']

        if settings['two_pass'] and not hw:
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
                            '-preset' if codec != 'AV1' else '-cpu-used', settings['sw_preset'] if codec != 'AV1' else '4',
                            '-an', '-f', 'null']
                    cmd.append('/dev/null' if platform.system() != 'Windows' else 'NUL')
                    return cmd
                else:
                    cmd += ['-c:v', vc, '-b:v', bitrate, '-pass', '2',
                            '-preset' if codec != 'AV1' else '-cpu-used', settings['sw_preset'] if codec != 'AV1' else '4']
        elif settings['use_nvenc']:
            vc = {'H.265':'hevc_nvenc','H.264':'h264_nvenc','AV1':'av1_nvenc'}.get(codec,'hevc_nvenc')
            hw_p = settings['hw_preset'].split()[0]
            cmd += ['-c:v', vc, '-preset', hw_p, '-rc', 'vbr', '-cq', crf]
        elif settings['use_amf']:
            vc = {'H.265':'hevc_amf','H.264':'h264_amf','AV1':'av1_amf'}.get(codec,'hevc_amf')
            cmd += ['-c:v', vc, '-quality', settings['amf_quality'],
                    '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf, '-qp_b', crf]
        elif settings['use_qsv']:
            vc = {'H.265':'hevc_qsv','H.264':'h264_qsv','AV1':'av1_qsv'}.get(codec,'hevc_qsv')
            cmd += ['-c:v', vc, '-global_quality', crf, '-preset', settings['qsv_preset']]
        else:
            vc = {'H.265':'libx265','H.264':'libx264','AV1':'libaom-av1'}.get(codec,'libx265')
            if codec == 'AV1':
                cmd += ['-c:v', vc, '-crf', crf, '-cpu-used', '4', '-row-mt', '1']
            else:
                cmd += ['-c:v', vc, '-crf', crf, '-preset', settings['sw_preset']]

        filters = []
        res_map = {'4K (3840x2160)':'3840:2160','1080p (1920x1080)':'1920:1080',
                   '720p (1280x720)':'1280:720','576p (1024x576)':'1024:576','480p (854x480)':'854:480'}
        if settings['resolution'] in res_map:
            filters.append(f"scale={res_map[settings['resolution']]}:flags=lanczos")
        if settings['use_crop'] and settings['crop_values']:
            filters.append(f"crop={settings['crop_values']}")
        ar_map = {'16:9':'16/9','4:3':'4/3','2.35:1':'2.35','2.39:1':'2.39','1.85:1':'1.85'}
        if settings['aspect_ratio'] in ar_map:
            filters.append(f"setdar={ar_map[settings['aspect_ratio']]}")
        elif settings['anamorphic']:
            filters.append('setdar=16/9')
        deint_map = {'Yadif (fast)':'yadif=0','Yadif (slow/better)':'yadif=1',
                     'BWDIF':'bwdif=0','Decomb':'yadif=2','Bob':'yadif=1:1'}
        if settings['deinterlace'] in deint_map:
            filters.append(deint_map[settings['deinterlace']])

        sub_idx = settings.get('sub_idx')
        is_bitmap = settings.get('sub_is_bitmap', False)
        if sub_idx is not None and settings['sub_burn'] and not is_bitmap:
            filters.append(f"subtitles={_quote_path_for_filter(src)}:si={sub_idx}")

        if filters:
            cmd += ['-vf', ','.join(filters)]

        vid_done = False
        if sub_idx is not None and settings['sub_burn'] and is_bitmap:
            if '-vf' in cmd:
                vi = cmd.index('-vf'); chain = cmd[vi+1]
                cmd = cmd[:vi] + cmd[vi+2:]
                fc = f'[0:v]{chain}[vb];[vb][0:{sub_idx}]overlay[vout]'
            else:
                fc = f'[0:v][0:{sub_idx}]overlay[vout]'
            cmd += ['-filter_complex', fc, '-map', '[vout]']
            vid_done = True

        if settings['keep_chapters']:
            cmd += ['-map_chapters', '0']

        audio_tracks = settings.get('audio_tracks', [])
        audio_configured = 'audio_tracks' in settings
        if not vid_done:
            cmd += ['-map', '0:v:0']

        if audio_tracks:
            for track_idx, acodec, abitrate in audio_tracks:
                cmd += ['-map', f'0:{track_idx}']
            for i, (track_idx, acodec, abitrate) in enumerate(audio_tracks):
                acodec_l = acodec.lower()
                if acodec_l in ('copy','passthrough'):
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
        elif not audio_configured:
            # No audio setting captured — default: copy all tracks
            cmd += ['-map', '0:a?', '-c:a', 'copy']

        if sub_idx is not None and not settings['sub_burn']:
            cmd += ['-map', f'0:{sub_idx}', '-c:s', 'copy']
        else:
            cmd += ['-sn']

        cmd += ['-progress', 'pipe:1', '-nostats']
        cmd.append(out_path)
        return cmd

    def _collect_settings(self) -> dict:
        s = self._settings_snapshot()
        if self._audio_rows:
            audio_tracks = []
            for row in self._audio_rows:
                result = row.get()
                if result: audio_tracks.append(result)
            s['audio_tracks'] = audio_tracks
        if self.sub_streams:
            sub_val = self.sub_track_var.get()
            sub_idx = None; sub_is_bitmap = False
            BITMAP = {'dvd_subtitle','hdmv_pgs_subtitle','dvbsub','xsub'}
            if sub_val != 'None':
                for idx, label, cname in self.sub_streams:
                    if label == sub_val:
                        sub_idx = idx; sub_is_bitmap = cname.lower() in BITMAP; break
            s['sub_idx']       = sub_idx
            s['sub_is_bitmap'] = sub_is_bitmap
        return s

    def _make_out_path(self, src: str, settings: dict, item: QueueItem = None) -> str:
        if item and item.output_name:
            out_name = item.output_name
        else:
            out_name = self.output_filename.get().strip() or f'encoded_{int(time.time())}'
        fmt = (item.output_fmt if item and item.output_fmt else self.output_format.get())
        if not out_name.endswith('.mkv') and not out_name.endswith('.mp4'):
            out_name += fmt
        if item and item.output_dir:
            out_dir = item.output_dir
        else:
            out_dir = self.output_dir.get().strip() or str(Path(src).parent)
        return str(Path(out_dir) / out_name)

    # ==================== QUEUE ENCODING ====================

    def _start_queue(self):
        # Purge stale done/skipped items from previous sessions
        self.queue = [q for q in self.queue if q.status not in
                      (QueueItem.STATUS_DONE, QueueItem.STATUS_SKIP, QueueItem.STATUS_ERR)]
        # Add current source if queue is empty
        if not self.queue:
            src = self.source_path.get().strip()
            if not src:
                messagebox.showerror('No Source',
                                     'Add files to the queue or scan a source file first.')
                return
            item = QueueItem(src)
            self._snapshot_item_settings(item)
            self.queue.append(item)
            self._refresh_queue_list()
            self._persist_settings()
        if self.is_encoding:
            return
        self.is_encoding = True
        self._btn_start.config_state(tk.DISABLED)
        self._btn_cancel.config_state(tk.NORMAL)
        total = len(self.queue)
        self._set_status(f'Encoding 1 of {total} — queue running')
        threading.Thread(target=self._queue_worker, daemon=True).start()

    def _snapshot_item_settings(self, item):
        item.settings = self._collect_settings()
        item.output_dir = self.output_dir.get().strip()
        item.output_name = self.output_filename.get().strip()
        item.output_fmt = self.output_format.get()

    def _queue_worker(self):
        for item in self.queue:
            if not self.is_encoding:
                break
            if item.status in (QueueItem.STATUS_DONE, QueueItem.STATUS_SKIP):
                continue
            self._current_item = item
            item.status = QueueItem.STATUS_ENC
            self.root.after(0, self._refresh_queue_list)
            settings = item.settings or self._collect_settings()
            out_path = self._make_out_path(item.path, settings, item)
            item.output_path = out_path
            self._out_path_live = out_path
            # Quick scan to get source duration for progress tracking
            self._scan_duration(item.path)
            idx = self.queue.index(item) + 1
            total = len(self.queue)
            self.root.after(0, lambda n=item.name, i=idx, t=total: self._set_status(f'Encoding {i} of {t} — {n}'))
            self.root.after(0, lambda: self._log_ts('='*44, 'head'))
            self.root.after(0, lambda n=item.name: self._log_ts(f'Starting: {n}', 'warn'))
            self.root.after(0, lambda p=out_path: self._log_ts(f'Output  : {p}', 'ok'))
            success = self._encode_item(item.path, out_path, settings)
            if success:
                item.status = QueueItem.STATUS_DONE
                item.progress = 100.0
                self._verify_output(out_path, item)
            else:
                item.status = QueueItem.STATUS_ERR
                tail = ''.join(self._stderr_buf[-20:]).strip()
                self.root.after(0, lambda n=item.name, t=tail: messagebox.showerror(
                    'Encode Failed',
                    f'{n}\n\nCheck Encode Log for details.\n\n{t[:500]}'))
            self.root.after(0, self._refresh_queue_list)
            self._persist_settings()
        self.is_encoding = False
        self._current_item = None
        self.root.after(0, self._encode_all_done)

    def _scan_duration(self, src: str):
        try:
            cmd = [self._get_ffprobe(), '-v', 'quiet', '-print_format', 'json',
                   '-show_format', src]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                info = json.loads(r.stdout)
                fmt = info.get('format', {})
                self.total_duration = float(fmt.get('duration', 0))
            else:
                self.total_duration = 0.0
        except Exception:
            self.total_duration = 0.0

    def _encode_item(self, src: str, out_path: str, settings: dict) -> bool:
        two_pass = settings['two_pass'] and not (
            settings['use_nvenc'] or settings['use_amf'] or settings['use_qsv'])
        passes = [1, 2] if two_pass else [0]
        for pass_num in passes:
            self._current_pass = pass_num
            label = {0:'', 1:'Pass 1/2', 2:'Pass 2/2'}.get(pass_num, '')
            self.root.after(0, lambda l=label: self._prog_pass.config(text=l))
            cmd = self._build_cmd(src, out_path, settings, pass_num)
            self.root.after(0, lambda c=cmd: self._log_ts(f'CMD: {" ".join(c)}', 'info'))
            self._start_time = time.time()
            self._vu_reset()
            try:
                self.encode_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1)
            except FileNotFoundError:
                self.root.after(0, lambda: messagebox.showerror(
                    'FFmpeg Not Found', 'Install FFmpeg and add to PATH.'))
                return False
            self._stderr_buf = []
            self._progress_data = {}
            stderr_t = threading.Thread(target=self._drain_stderr, daemon=True)
            stderr_t.start()
            stdout_t = threading.Thread(target=self._drain_stdout, daemon=True)
            stdout_t.start()
            self.root.after(80, lambda: self._poll(src))
            self.encode_process.wait()
            stderr_t.join(timeout=3)
            stdout_t.join(timeout=3)
            rc = self.encode_process.returncode
            if rc != 0 and self.is_encoding:
                tail = ''.join(self._stderr_buf[-40:]).strip()
                self.root.after(0, lambda t=tail: self._log_ts(f'stderr:\n{t}','err'))
                self.root.after(0, lambda: self._prog_fps.config(text='x Error'))
                return False
        return True

    def _drain_stderr(self):
        try:
            for line in self.encode_process.stderr:
                self._stderr_buf.append(line)
        except Exception:
            pass

    def _drain_stdout(self):
        """Read ffmpeg -progress lines from stdout in a background thread.
        Builds a key=value dict from each progress block and forwards it."""
        buf = ''
        try:
            for char in iter(lambda: self.encode_process.stdout.read(1), ''):
                buf += char
                if char == '\n' and buf.strip():
                    line = buf.strip()
                    buf = ''
                    if '=' in line:
                        k, _, v = line.partition('=')
                        self._progress_data[k.strip()] = v.strip()
                    if line == 'progress=continue' or line == 'progress=end':
                        data = dict(self._progress_data)
                        self._progress_data.clear()
                        self.root.after(0, lambda d=data: self._apply_progress(d))
        except Exception:
            pass

    def _apply_progress(self, data: dict):
        """Apply a parsed ffmpeg progress dict to the UI."""
        # out_time_us (microseconds) is preferred; fall back to out_time_ms
        time_us = data.get('out_time_us', data.get('out_time_ms', '0'))
        try:
            cur = int(time_us) / 1_000_000
        except (ValueError, TypeError):
            cur = 0
        if cur > 0:
            self._update_progress_from_time(cur)
        fps_val = data.get('fps', '')
        if fps_val:
            try:
                fv = float(fps_val)
                self._prog_fps.config(text=f'{fv:.1f} fps')
            except ValueError:
                pass

    def _poll(self, src):
        if not self.is_encoding or self.encode_process is None:
            return
        self.root.after(0, self._update_live_size)
        if self.encode_process.poll() is None:
            self.root.after(200, lambda: self._poll(src))

    def _update_progress_from_time(self, cur: float):
        elapsed = time.time() - self._start_time
        td = self.total_duration
        if td > 0:
            pct = min((cur / td) * 100, 100)
            eta = (elapsed / cur) * (td - cur) if cur > 0 else 0
        else:
            pct = 0.0
            eta = 0
        if self._current_item:
            self._current_item.progress = pct

        def _ui(p=pct, e=elapsed, et=eta, c=cur, d=td):
            if d > 0:
                self._prog_bar.set(p)
                self._prog_pct.config(text=f'{p:.1f}%')
                self._prog_det.config(
                    text=f'{int(c//3600):02d}:{int((c%3600)//60):02d}:{int(c%60):02d}'
                         f' / {int(d//3600):02d}:{int((d%3600)//60):02d}:{int(d%60):02d}')
            else:
                self._prog_pct.config(text=f'{_fmt_time(c)}')
        self.root.after(0, _ui)
        self.root.after(0, self._refresh_queue_list)

    def _update_live_size(self):
        if self._out_path_live:
            sz = _fmt_size(self._out_path_live)
            self._badge_live.config(text=sz)
            try: self._live_size_lbl.config(text=sz)
            except: pass

    def _vu_reset(self):
        self._prog_bar.set(0)
        self._prog_pct.config(text='0%')
        self._prog_det.config(text='Initialising...')
        self._prog_fps.config(text='')
        self._badge_live.config(text='')
        try: self._live_size_lbl.config(text='')
        except: pass

    def _verify_output(self, out_path: str, item: QueueItem):
        def _verify():
            try:
                cmd = [self._get_ffprobe(),'-v','quiet','-print_format','json',
                       '-show_format', out_path]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if r.returncode == 0:
                    info = json.loads(r.stdout)
                    size_gb = int(info['format'].get('size',0)) / (1024**3)
                    orig    = self.original_size
                    saving  = (1 - size_gb/orig)*100 if orig>0 else 0
                    self.root.after(0, lambda s=size_gb, sv=saving: (
                        self._log_ts(f'+ Verify OK -- output: {s:.2f} GB  ({sv:.1f}% smaller)', 'ok'),
                        self._badge_live.config(text=f'{s:.2f} GB'),
                        self._live_size_lbl.config(text=f'{s:.2f} GB')
                    ))
                else:
                    self.root.after(0, lambda: self._log_ts('! Verify failed -- output may be corrupt', 'err'))
            except Exception as e:
                self.root.after(0, lambda: self._log_ts(f'Verify error: {e}', 'warn'))
        threading.Thread(target=_verify, daemon=True).start()

    def _encode_all_done(self):
        done  = sum(1 for q in self.queue if q.status == QueueItem.STATUS_DONE)
        errs  = sum(1 for q in self.queue if q.status == QueueItem.STATUS_ERR)
        if errs > 0:
            self._prog_bar.set(0)
            self._prog_pct.config(text='ERROR')
            self._prog_det.config(text=f'{errs} item(s) failed')
        else:
            self._prog_bar.set(100)
            self._prog_pct.config(text='100%')
            self._prog_det.config(text='Queue complete!')
        self._prog_pass.config(text='')
        self._btn_start.config_state(tk.NORMAL)
        self._btn_cancel.config_state(tk.DISABLED)
        self._log_ts(f'Queue finished -- {done} done, {errs} errors', 'ok' if errs==0 else 'warn')
        self._set_status(f'Done -- {done} files encoded' if errs==0 else f'{errs} error(s) — check log')
        if self.notify_done.get():
            _notify('BluPress', f'Encoding complete -- {done} file(s) done, {errs} error(s).')

    def _cancel_encode(self):
        self.is_encoding = False
        if self.encode_process:
            try: self.encode_process.terminate()
            except: pass
        if self._out_path_live:
            try:
                p = Path(self._out_path_live)
                if p.exists() and p.stat().st_size < 10_000_000:
                    p.unlink()
                    self._log_ts(f'Removed incomplete output: {p.name}', 'warn')
                elif p.exists():
                    self._log_ts(f'Partial file kept (>10 MB): {p.name}', 'warn')
            except Exception: pass
        if self._current_item:
            self._current_item.status = QueueItem.STATUS_SKIP
            self._current_item = None
        self._refresh_queue_list()
        self._btn_start.config_state(tk.NORMAL)
        self._btn_cancel.config_state(tk.DISABLED)
        self._set_status('Cancelled.')
        self._log_ts('Cancelled by user', 'warn')

    # ==================== RIGHT-CLICK / CANCEL ITEM ====================

    def _queue_context_menu(self, event):
        sel = self._queue_list.curselection()
        if not sel:
            return
        idx = sel[0]
        item = self.queue[idx]
        menu = tk.Menu(self.root, tearoff=0, bg=C['panel2'], fg=C['white'],
                       activebackground=C['amber_dim'], activeforeground=C['bg'])
        is_busy = item.status == QueueItem.STATUS_ENC
        if is_busy:
            menu.add_command(label='Cancel this item', command=lambda: self._cancel_item(idx),
                             foreground=C['red'])
        else:
            menu.add_command(label='Remove', command=lambda: self._remove_item(idx),
                             foreground=C['white'])
        menu.add_separator()
        if idx > 0:
            menu.add_command(label='Move Up', command=lambda: self._move_item(idx, -1),
                             foreground=C['white'])
        if idx < len(self.queue) - 1:
            menu.add_command(label='Move Down', command=lambda: self._move_item(idx, 1),
                             foreground=C['white'])
        menu.add_separator()
        menu.add_command(label='Edit Output Path...', command=lambda: self._edit_item_output(idx),
                         foreground=C['amber'])
        menu.post(event.x_root, event.y_root)

    def _cancel_item(self, idx):
        item = self.queue[idx]
        if item.status != QueueItem.STATUS_ENC:
            return
        if item is self._current_item:
            self._cancel_encode()
        else:
            item.status = QueueItem.STATUS_SKIP
            self._refresh_queue_list()
            self._persist_settings()
            self._log_ts(f'Cancelled: {item.name}', 'warn')

    def _remove_item(self, idx):
        self._queue_list.selection_clear(0, tk.END)
        del self.queue[idx]
        self._refresh_queue_list()
        self._persist_settings()

    def _move_item(self, idx, direction):
        target = idx + direction
        if target < 0 or target >= len(self.queue):
            return
        self.queue[idx], self.queue[target] = self.queue[target], self.queue[idx]
        self._refresh_queue_list()
        self._queue_list.selection_set(target)
        self._persist_settings()

    def _edit_item_output(self, idx):
        item = self.queue[idx]
        d = filedialog.askdirectory(title='Output directory for this item',
                                    initialdir=item.output_dir or str(Path(item.path).parent))
        if d:
            item.output_dir = d
            self._persist_settings()
            self._log_ts(f'Output dir set for {item.name}: {d}', 'ok')

    # ==================== PRESET IMPORT / EXPORT ====================

    def _export_presets(self):
        if not self.saved_presets:
            messagebox.showinfo('Export', 'No user presets to export.')
            return
        f = filedialog.asksaveasfilename(
            title='Export presets',
            defaultextension='.json',
            filetypes=[('JSON preset pack','*.json')],
            initialfile=f'blupress_presets_{time.strftime("%Y%m%d")}.json')
        if not f:
            return
        try:
            Path(f).write_text(json.dumps(self.saved_presets, indent=2))
            self._log_ts(f'Exported {len(self.saved_presets)} presets → {f}', 'ok')
        except Exception as e:
            messagebox.showerror('Export error', str(e))

    def _import_presets(self):
        f = filedialog.askopenfilename(
            title='Import presets',
            filetypes=[('JSON preset pack','*.json'), ('All files','*.*')])
        if not f:
            return
        try:
            data = json.loads(Path(f).read_text())
            if not isinstance(data, dict):
                raise ValueError('File must contain a JSON object')
            count = 0
            for name, settings in data.items():
                if name not in self.saved_presets and isinstance(settings, dict):
                    self.saved_presets[name] = settings
                    count += 1
            self._refresh_preset_cb()
            self._persist_settings()
            self._log_ts(f'Imported {count} presets from {Path(f).name}', 'ok')
            if count == 0:
                messagebox.showinfo('Import', 'No new presets found (duplicates skipped).')
        except Exception as e:
            messagebox.showerror('Import error', f'Failed to import presets:\n{e}')

    # ==================== KEYBOARD SHORTCUTS ====================

    def _bind_shortcuts(self):
        self.root.bind('<Control-Return>', lambda e: self._start_queue())
        self.root.bind('<Control-o>',       lambda e: self._queue_add())
        self.root.bind('<Escape>',          lambda e: self._cancel_encode())
        self.root.bind('<Control-l>',       lambda e: self._export_log())
        # Ctrl+Shift+C to copy command (avoids conflict with native text copy)
        self.root.bind('<Control-Shift-C>', lambda e: self._copy_command())

    # ==================== FFMPEG PATH HELPER ====================

    def _get_ffmpeg(self) -> str:
        return self.ffmpeg_path.get().strip() or 'ffmpeg'

    def _get_ffprobe(self) -> str:
        fp = self.ffmpeg_path.get().strip()
        if fp:
            p = Path(fp)
            return str(p.parent / 'ffprobe') if p.name == 'ffmpeg' else fp.replace('ffmpeg', 'ffprobe')
        return 'ffprobe'

    # ==================== TOOLTIP ====================

    class ToolTip:
        DELAY_MS = 600

        def __init__(self, widget, text):
            self._widget = widget
            self._text = text
            self._tip = None
            self._after_id = None
            widget.bind('<Enter>', self._enter, add='+')
            widget.bind('<Leave>', self._leave, add='+')
            widget.bind('<Motion>', self._motion, add='+')

        def _cancel(self):
            if self._after_id:
                try:
                    self._widget.after_cancel(self._after_id)
                except Exception:
                    pass
                self._after_id = None
            if self._tip:
                try:
                    self._tip.destroy()
                except Exception:
                    pass
                self._tip = None

        def _enter(self, event):
            self._cancel()
            self._mx = event.x_root
            self._my = event.y_root
            self._after_id = self._widget.after(self.DELAY_MS, self._show)

        def _motion(self, event):
            self._mx = event.x_root
            self._my = event.y_root

        def _show(self):
            self._after_id = None
            self._tip = tk.Toplevel(self._widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f'+{self._mx + 15}+{self._my + 15}')
            lbl = tk.Label(self._tip, text=self._text,
                           bg='#2a2a2a', fg='#cccccc', font=TINY,
                           wraplength=300, padx=8, pady=5)
            lbl.pack()

        def _leave(self, event):
            self._cancel()

    @staticmethod
    def tooltip(widget, text):
        if text:
            widget._tooltip = BluPress.ToolTip(widget, text)

    # ==================== MISC ACTIONS ====================

    def _on_codec_change(self):
        self._update_estimate()

    def _copy_command(self):
        src = self.source_path.get().strip()
        if not src: self._set_status('No source loaded.'); return
        settings = self._collect_settings()
        out_path = self._make_out_path(src, settings)
        cmd = self._build_cmd(src, out_path, settings, 0)
        cmd_str = ' '.join(f'"{a}"' if ' ' in a else a for a in cmd)
        self.root.clipboard_clear(); self.root.clipboard_append(cmd_str)
        self._set_status('FFmpeg command copied'); self._log_ts('CMD copied', 'ok')

    def _open_output_dir(self):
        d = self.output_dir.get().strip()
        if not d:
            if self.queue and self._current_item:
                d = str(Path(self._current_item.output_path).parent)
        if d and Path(d).exists():
            if platform.system() == 'Windows':   os.startfile(d)
            elif platform.system() == 'Darwin':  subprocess.Popen(['open', d])
            else:                                 subprocess.Popen(['xdg-open', d])
        else:
            messagebox.showinfo('Open folder', 'No output directory set yet.')

    def _export_log(self):
        content = self._log.get('1.0', tk.END)
        out_dir = self.output_dir.get().strip() or str(Path.home())
        log_path = Path(out_dir) / f'blupress_log_{time.strftime("%Y%m%d_%H%M%S")}.txt'
        try:
            log_path.write_text(content)
            self._log_ts(f'Log saved: {log_path}', 'ok')
        except Exception as e:
            messagebox.showerror('Export log', str(e))
