"""Shared constants + theme palette for Cheat Engine 2X (modern dark UI)."""

import os
import sys

# Platform detection
C = {
    "bg":          "#16181c",   # window background
    "bg_panel":    "#1c1f24",   # panels / dialogs
    "bg_surface":  "#24272e",   # cards / list backgrounds
    "bg_shelf":    "#2c2f37",   #Toolbar / tabs
    "bg_input":    "#2a2d35",   # text fields
    "text":        "#e6e8ec",   # primary text
    "text_muted":  "#8a909c",   # secondary text
    "text_caption":"#6b707c",   # captions / column headers
    "accent":      "#58a6ff",   # primary blue accent
    "accent_dim":  "#214c8c",
    "accent_glow": "#3b82f6",
    "green":       "#30d158",   # found / success
    "green_dim":   "#1e6b3a",
    "red":         "#ff5c5c",   # error / mismatch
    "red_dim":     "#8a2a2a",
    "amber":       "#ffb454",   # warning
    "amber_dim":   "#8a6d1a",
    "border":      "#33363e",   # borders
    "border_focus": "#58a6ff",  # focused border
    "select":      "#1f48b8",   # selected row bg
    "select_fg":   "#e6e8ec",   # selected row text
    "select_muted": "#2c313a",  # alternate row
    "scrollbar":   "#33363e",   # scrollbar track
    "scrollbar_thumb": "#4b505a",  # scrollbar thumb
    "FONT": "Segoe UI",
    "MONO": "Cascadia Mono",
    "SIZE": {"base": 10, "sm": 9, "lg": 11, "xl": 14, "xxl": 18},
}

# ---- UI geometry ----
FONT = "Segoe UI"                      # modern system font
MONO = "Cascadia Mono"                 # monospaced (code / hex)

ACCENT_PALETTE = [
    "#58a6ff", "#30d158", "#ffb454", "#ff5c5c", "#7c5cfc",
    "#30a6ff", "#ff7a5c", "#9c5cff", "#5cff8a", "#ff5c7a",
]

# ---- Core defaults ----
DEFAULT_PROCESS = "notepad.exe"
SCAN_LIMIT = 100_000          # max addresses returned per scan
WRITE_SIZE = 8                # default write width in bytes

# ---- Engine / store awareness ----
# Prebuilt structure templates per engine (for guided scan wizards + automation).
# Keys are engine names; values are lists of builder tags.
ENGINE_TEMPLATES = {
    "Unity (Mono)": ["mono", "il2cpp", "ascii", "transform", "m_localPosition"],
    "Unity (IL2CPP)": ["il2cpp", "watson", "string_hash", "scriptable_object"],
    "Unreal Engine": ["ue4", "ue5", "gameinstance", "world", "gameviewport"],
    "Epic (Fortnite)": ["fortnite", "fdefault", "streamer"],
    "Wwise": ["wwise", "sound", "bank"],
    "FMOD": ["fmod", "bank", "studio"],
    "Custom/Unknown": ["auto", "any"],
}

# ---- Supported game stores ----
GAME_STORES = ["Steam", "Epic Games", "Microsoft Store", "GOG", "Origin", "Battle.net"]

# ---- Community table repository (local cache path) ----
TABLE_REPO_DIR = os.path.expanduser("~/.ce2x/tables")
REPO_SCHEMA_VERSION = 1

