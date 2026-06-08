#!/usr/bin/env python3
"""
BluPress — Blu-ray & DVD Compressor
A modern tkinter GUI for FFmpeg-based video compression.
"""

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
    root = ROOT()
    app = BluPress(root)
    root.mainloop()
