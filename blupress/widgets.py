"""Custom tkinter widgets for BluPress."""

import os
import re
import tkinter as tk
from tkinter import ttk

from blupress.constants import C, MONO, UI, UI_B, TINY, SMALL, _lbl, _sep, _entry, _combo, _check


class AmberButton(tk.Frame):
    def __init__(self, parent, text, command=None,
                 style='normal', width=140, height=30, **kw):
        super().__init__(parent, width=width, height=height,
                         bg=C['panel'], **kw)
        self.pack_propagate(False)
        self.command = command
        self.style = style
        self._hover = False
        self._state = tk.NORMAL

        self._label = tk.Label(self, text=text, font=UI_B, anchor=tk.CENTER,
                               bg=C['panel2'], fg=C['mid'],
                               highlightthickness=0)
        self._label.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonRelease-1>', self._on_release)
        self._label.bind('<Enter>', self._on_enter)
        self._label.bind('<Leave>', self._on_leave)
        self._label.bind('<ButtonRelease-1>', self._on_release)

        self._update_style()

    def _colors(self):
        if self._state == tk.DISABLED:
            return {'bg': C['panel2'], 'fg': C['dim'], 'border': C['border']}
        if self.style == 'primary':
            if self._hover:
                return {'bg': C['amber_glow'], 'fg': C['white'], 'border': C['amber_glow']}
            return {'bg': C['amber'], 'fg': C['white'], 'border': C['amber']}
        if self.style == 'danger':
            if self._hover:
                return {'bg': C['red_dim'], 'fg': C['white'], 'border': C['red']}
            return {'bg': C['red'], 'fg': C['white'], 'border': C['red']}
        if self.style == 'ghost':
            if self._hover:
                return {'bg': C['panel2'], 'fg': C['amber'], 'border': C['amber']}
            return {'bg': C['panel2'], 'fg': C['mid'], 'border': C['border']}
        if self._hover:
            return {'bg': C['amber_dim'], 'fg': C['white'], 'border': C['amber_glow']}
        return {'bg': C['panel2'], 'fg': C['mid'], 'border': C['border']}

    def _update_style(self):
        try:
            col = self._colors()
            self.configure(bg=col['border'])
            self._label.configure(bg=col['bg'], fg=col['fg'])
        except tk.TclError as e:
            print(f'AmberButton style error: {e}')

    def _on_enter(self, event):
        self._hover = True
        if self._state != tk.DISABLED:
            self.config(cursor='hand2')
            self._label.config(cursor='hand2')
        self._update_style()

    def _on_leave(self, event):
        self._hover = False
        self._update_style()

    def _on_release(self, event):
        if self._state != tk.DISABLED and self.command:
            self.command()

    def config_state(self, state):
        self._state = state
        self._update_style()

    def set_text(self, text):
        self._label.config(text=text)


class DropTarget:
    """Mixin to add drag-and-drop support to tkinter widgets."""

    def __init__(self):
        self._drop_target_register()

    def _drop_target_register(self):
        try:
            import tkinterDnD
            self.drop_target_register(tkinterDnD.DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)
        except (ImportError, AttributeError):
            self.bind('<Double-Button-1>', self._on_double_click)
            self.bind('<Button-3>', self._on_right_click)

    def _on_drop(self, event):
        files = self._parse_drop_data(event.data)
        if files:
            self._handle_files(files)

    def _parse_drop_data(self, data):
        files = []
        if data.startswith('{') and data.endswith('}'):
            files = re.findall(r'\{([^}]+)\}', data)
        elif data:
            import shlex
            try:
                files = shlex.split(data)
            except Exception:
                files = data.strip().split()
        cleaned = []
        for f in files:
            f = f.strip('{}').strip()
            if f and os.path.exists(f):
                cleaned.append(f)
        return cleaned

    def _on_double_click(self, event):
        pass

    def _on_right_click(self, event):
        pass

    def _handle_files(self, files):
        pass


class DropEntry(tk.Entry, DropTarget):
    """Entry widget with drag-and-drop support."""

    def __init__(self, parent, textvariable, on_drop=None, browse_cmd=None, **kw):
        tk.Entry.__init__(self, parent, textvariable=textvariable, **kw)
        self._on_drop_callback = on_drop
        self._browse_cmd = browse_cmd
        self._placeholder_shown = False
        DropTarget.__init__(self)

    def _handle_files(self, files):
        if files:
            self.delete(0, tk.END)
            self.insert(0, files[0])
            self.configure(fg=C['white'])
            self._placeholder_shown = False
            if self._on_drop_callback:
                self._on_drop_callback(files)

    def _on_double_click(self, event):
        if self._browse_cmd:
            self._browse_cmd()

    def _on_right_click(self, event):
        menu = tk.Menu(self, tearoff=0, bg=C['panel2'], fg=C['white'],
                       activebackground=C['amber_dim'], activeforeground=C['white'])
        menu.add_command(label='Browse File...', command=self._browse_cmd if self._browse_cmd else self._on_double_click_nop)
        menu.add_command(label='Browse Folder...', command=self._browse_folder_cmd if hasattr(self, '_browse_folder_cmd') else self._on_double_click_nop)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_double_click_nop(self):
        pass


class DropListbox(tk.Listbox, DropTarget):
    """Listbox with drag-and-drop support."""

    def __init__(self, parent, on_drop=None, **kw):
        tk.Listbox.__init__(self, parent, **kw)
        self._on_drop_callback = on_drop
        DropTarget.__init__(self)

    def _handle_files(self, files):
        if self._on_drop_callback:
            self._on_drop_callback(files)


class SegmentedControl(tk.Frame):
    def __init__(self, parent, options, variable, command=None, **kw):
        super().__init__(parent, bg=parent['bg'], **kw)
        self.variable = variable
        self.command = command
        self.buttons = {}
        self._trace_id = None

        for opt in options:
            b = tk.Label(self, text=opt, font=UI,
                         bg=C['well'], fg=C['dim'],
                         padx=11, pady=4, cursor='hand2',
                         relief=tk.FLAT, highlightthickness=1,
                         highlightbackground=C['border'])
            b.pack(side=tk.LEFT, padx=1)
            b.bind('<Button-1>', lambda e, o=opt: self._select(o))
            self.buttons[opt] = b

        self._refresh()
        self._trace_id = variable.trace_add('write', lambda *_: self._safe_refresh())

        self.bind('<Destroy>', self._on_destroy)

    def _on_destroy(self, event):
        if event.widget == self and self._trace_id is not None:
            try:
                self.variable.trace_remove('write', self._trace_id)
            except Exception:
                pass

    def _select(self, opt):
        self.variable.set(opt)
        if self.command:
            self.command()

    def _safe_refresh(self):
        try:
            if not self.winfo_exists():
                return
            self._refresh()
        except Exception:
            pass

    def _refresh(self):
        val = self.variable.get()
        for opt, b in self.buttons.items():
            try:
                if b.winfo_exists():
                    if opt == val:
                        b.config(bg=C['amber'], fg=C['white'], highlightbackground=C['amber'])
                    else:
                        b.config(bg=C['well'], fg=C['dim'], highlightbackground=C['border'])
            except tk.TclError:
                continue


class ToggleSwitch(tk.Frame):
    """Sleek pill-style toggle switch."""
    def __init__(self, parent, variable, command=None, **kw):
        super().__init__(parent, bg=parent['bg'], width=36, height=20, **kw)
        self._var = variable
        self._cmd = command
        self.pack_propagate(False)
        self._canvas = tk.Canvas(self, width=36, height=20, bg=parent['bg'],
                                 highlightthickness=0)
        self._canvas.pack()
        self._canvas.bind('<Button-1>', self._toggle)
        self._draw()
        self._trace = variable.trace_add('write', lambda *_: self._draw())

    def _toggle(self, event):
        self._var.set(not self._var.get())
        if self._cmd:
            self._cmd()

    def _draw(self):
        on = self._var.get()
        bg = C['amber'] if on else C['border']
        knob_x = 18 if on else 4
        self._canvas.delete('all')
        self._canvas.create_oval(0, 0, 20, 20, fill=bg, outline='')
        self._canvas.create_oval(16, 0, 36, 20, fill=bg, outline='')
        self._canvas.create_rectangle(10, 0, 26, 20, fill=bg, outline='')
        self._canvas.create_oval(knob_x - 6, 2, knob_x + 6, 18,
                                 fill=C['white'], outline='')

    def destroy(self):
        try:
            self._var.trace_remove('write', self._trace)
        except Exception:
            pass
        super().destroy()


class MetricCard(tk.Frame):
    """A metric card with a muted label and large colored value."""
    def __init__(self, parent, label, initial='---', color=None, **kw):
        super().__init__(parent, bg=C['card_bg'], padx=10, pady=8, **kw)
        tk.Label(self, text=label.upper(), font=SMALL,
                 bg=C['card_bg'], fg=C['dim']).pack(anchor=tk.W)
        self._v = tk.Label(self, text=initial,
                           font=('Courier New', 15, 'bold'),
                           bg=C['card_bg'], fg=color or C['amber'])
        self._v.pack(anchor=tk.W, pady=(1, 0))

    def set(self, t, color=None):
        self._v.config(text=t)
        if color:
            self._v.config(fg=color)


class StatusChip(tk.Frame):
    """A small rounded-looking status label."""
    def __init__(self, parent, text, fg=None, bg=None, **kw):
        super().__init__(parent, bg=bg or C['amber_bg'], padx=8, pady=1, **kw)
        self._lbl = tk.Label(self, text=text.upper(), font=SMALL,
                             bg=bg or C['amber_bg'],
                             fg=fg or C['amber'])
        self._lbl.pack()

    def set_text(self, text):
        self._lbl.config(text=text.upper())

    def set_colors(self, fg, bg):
        self._lbl.config(fg=fg)
        self.config(bg=bg)
        self._lbl.config(bg=bg)


class PillBadge(tk.Frame):
    """Small pill badge for titlebar."""
    def __init__(self, parent, text, fg, bg, **kw):
        super().__init__(parent, bg=bg, padx=10, pady=2, **kw)
        tk.Label(self, text=text, font=SMALL,
                 bg=bg, fg=fg).pack()


class Section(tk.Frame):
    def __init__(self, parent, title, **kw):
        super().__init__(parent, bg=C['panel'], **kw)
        hdr = tk.Frame(self, bg=C['panel'])
        hdr.pack(fill=tk.X, pady=(0, 8))
        tk.Frame(hdr, bg=C['amber'], width=3).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        tk.Label(hdr, text=title.upper(), font=UI_B,
                 bg=C['panel'], fg=C['amber']).pack(side=tk.LEFT)
        _sep(hdr, C['amber_dim']).pack(side=tk.LEFT, fill=tk.X, expand=True,
                                        padx=(10, 0), pady=6)

    def body(self):
        f = tk.Frame(self, bg=C['panel'])
        f.pack(fill=tk.X, padx=4)
        return f


class AudioTrackRow(tk.Frame):
    CODECS = ['copy', 'aac', 'ac3', 'eac3', 'flac', 'mp3', 'opus']
    RATES = ['96k', '128k', '160k', '192k', '224k', '256k', '320k', '384k', '448k', '512k']

    def __init__(self, parent, idx, label, **kw):
        super().__init__(parent, bg=C['panel2'], **kw)
        self.stream_idx = idx
        self.enabled = tk.BooleanVar(value=False)
        self.codec = tk.StringVar(value='copy')
        self.bitrate = tk.StringVar(value='192k')

        _check(self, '', self.enabled).pack(side=tk.LEFT, padx=(4, 2))
        tk.Label(self, text=label, font=TINY, bg=C['panel2'],
                 fg=C['mid'], width=46, anchor=tk.W).pack(side=tk.LEFT)
        _combo(self, self.codec, self.CODECS, width=6).pack(side=tk.LEFT, padx=3)
        _combo(self, self.bitrate, self.RATES, width=5).pack(side=tk.LEFT, padx=3)

    def get(self):
        if not self.enabled.get():
            return None
        return (self.stream_idx, self.codec.get(), self.bitrate.get())


class VUMeter(tk.Canvas):
    SEGMENTS = 40

    def __init__(self, parent, **kw):
        super().__init__(parent, height=20, bg=C['panel'],
                         highlightthickness=0, **kw)
        self._pct = 0.0
        self._target = 0.0
        self._aid = None
        self.bind('<Configure>', lambda e: self._draw())

    def set(self, pct):
        self._target = max(0.0, min(100.0, pct))
        self._animate()

    def _animate(self):
        if self._aid:
            self.after_cancel(self._aid)
        diff = self._target - self._pct
        if abs(diff) < 0.3:
            self._pct = self._target
            self._draw()
            return
        self._pct += diff * 0.18
        self._draw()
        self._aid = self.after(16, self._animate)

    def _draw(self):
        self.delete('all')
        w = self.winfo_width() or 700
        h = self.winfo_height() or 20
        n, gap = self.SEGMENTS, 2
        sw = max(1, (w - (n - 1) * gap) / n)
        filled = int((self._pct / 100.0) * n)
        for i in range(n):
            x1 = i * (sw + gap)
            x2 = x1 + sw
            f = i / n
            if i < filled:
                col = C['teal'] if f < 0.6 else (C['amber'] if f < 0.85 else C['red'])
            else:
                col = C['well']
            self.create_rectangle(x1, 2, x2, h - 2, fill=col, outline='')
        if self._pct > 0:
            self.create_text(w - 5, h // 2, text=f"{self._pct:.1f}%",
                             fill=C['white'], font=TINY, anchor=tk.E)


class IndigoBar(tk.Frame):
    """Slim 4px indigo progress bar."""
    def __init__(self, parent, **kw):
        super().__init__(parent, height=4, bg=C['panel2'], **kw)
        self._fill = tk.Frame(self, bg=C['amber'], width=0, height=4)
        self._fill.pack(side=tk.LEFT, fill=tk.Y)
        self.pack_propagate(False)

    def set(self, pct):
        w = self.winfo_width() or 200
        self._fill.config(width=int(w * pct / 100))
