#!/usr/bin/env python3
"""
BluPress — Blu-ray & DVD Compressor
A modern tkinter GUI for FFmpeg-based video compression.
"""

import sys
import tkinter as tk

try:
    import tkinterDnD
    ROOT = tkinterDnD.Tk
except ImportError:
    ROOT = tk.Tk
    print("Welcome to BluPress!")
    print("     Developed by Band")

from blupress.app import BluPress

if __name__ == '__main__':
    if '--cli' in sys.argv:
        sys.argv.remove('--cli')
        from blupress.cli import main as cli_main
        sys.exit(cli_main())
    root = ROOT()
    app = BluPress(root)
    root.mainloop()
