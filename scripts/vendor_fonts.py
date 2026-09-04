#!/usr/bin/env python3
"""Vendor web fonts locally so the app has no runtime dependency on Google's CDN.

Downloads woff2 files from Google Fonts into ``static/fonts/`` and generates
``static/css/fonts.css`` with ``@font-face`` rules that point at the local files.

Re-run this script to refresh the vendored fonts (e.g. to pick up a new weight
or a newer font version). It is deterministic and safe to run repeatedly.

Usage:
    python scripts/vendor_fonts.py
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request

# A desktop Chrome UA makes Google Fonts serve woff2 (its smallest format).
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(REPO_ROOT, "static", "fonts")
CSS_OUT = os.path.join(REPO_ROOT, "static", "css", "fonts.css")

# Only ship the subsets an English-language classroom app needs. This keeps the
# vendored payload small (drops cyrillic/greek/vietnamese/etc.).
KEEP_SUBSETS = {"latin", "latin-ext"}

# Text families: (local file prefix, Google Fonts css2 query).
#
# Inter and Atkinson Hyperlegible Next are *variable* fonts: the css2 `..` range
# syntax returns a single woff2 per subset covering the whole weight range, which
# is the officially recommended way to consume them (one file, not one per
# weight). IBM Plex Mono is *not* variable, so it must list discrete weights;
# each weight is a distinct static instance file.
TEXT_FONTS = [
    ("inter", "Inter:wght@300..700"),
    ("atkinson-hyperlegible-next", "Atkinson+Hyperlegible+Next:wght@400..700"),
    ("ibm-plex-mono", "IBM+Plex+Mono:wght@300;400;500;600;700"),
]

# Material Symbols is a single variable woff2 with no unicode-range subsetting.
MATERIAL_SYMBOLS_QUERY = (
    "Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_css(query: str) -> str:
    return fetch(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode("utf-8")


# One @font-face block, captured with the preceding /* subset */ comment.
_BLOCK_RE = re.compile(
    r"/\*\s*(?P<subset>[\w-]+)\s*\*/\s*(?P<block>@font-face\s*\{[^}]*\})",
    re.DOTALL,
)
_SRC_URL_RE = re.compile(r"url\((https://[^)]+\.woff2)\)")
_WEIGHT_RE = re.compile(r"font-weight:\s*([^;]+);")
_STYLE_RE = re.compile(r"font-style:\s*([^;]+);")


def vendor_text_font(prefix: str, query: str) -> list[str]:
    """Download a text family's woff2 files; return rewritten @font-face blocks."""
    css = fetch_css(query)
    out_blocks: list[str] = []
    for match in _BLOCK_RE.finditer(css):
        subset = match.group("subset").strip()
        if subset not in KEEP_SUBSETS:
            continue
        block = match.group("block")
        url_match = _SRC_URL_RE.search(block)
        if not url_match:
            continue
        url = url_match.group(1)
        weight = _WEIGHT_RE.search(block).group(1).strip()
        style = _STYLE_RE.search(block).group(1).strip()
        # "300 700" (variable range) -> "300-700"; "400" (static) stays "400".
        weight_tag = weight.replace(" ", "-")
        filename = f"{prefix}-{subset}-{weight_tag}-{style}.woff2"
        dest = os.path.join(FONTS_DIR, filename)
        print(f"  downloading {filename} <- {url}")
        with open(dest, "wb") as fh:
            fh.write(fetch(url))
        rewritten = _SRC_URL_RE.sub(
            f"url(../fonts/{filename})", block
        )
        out_blocks.append(rewritten.strip())
    return out_blocks


def vendor_material_symbols() -> list[str]:
    css = fetch_css(MATERIAL_SYMBOLS_QUERY)
    url = _SRC_URL_RE.search(css).group(1)
    filename = "material-symbols-outlined.woff2"
    dest = os.path.join(FONTS_DIR, filename)
    print(f"  downloading {filename} <- {url}")
    with open(dest, "wb") as fh:
        fh.write(fetch(url))
    # Keep Google's face + base .material-symbols-outlined class, but point the
    # src at the local file.
    face_and_class = css[css.index("@font-face"):]
    face_and_class = _SRC_URL_RE.sub(f"url(../fonts/{filename})", face_and_class)
    # Chromium and other modern engines use the unprefixed property to enable
    # Material Symbols' ligature names (for example, "school") as glyphs.
    face_and_class = face_and_class.replace(
        "  -webkit-font-feature-settings: 'liga';",
        "  font-feature-settings: 'liga';\n  -webkit-font-feature-settings: 'liga';",
    )
    return [face_and_class.strip()]


def main() -> int:
    os.makedirs(FONTS_DIR, exist_ok=True)
    sections: list[str] = []

    for prefix, query in TEXT_FONTS:
        print(f"Vendoring {prefix} ...")
        blocks = vendor_text_font(prefix, query)
        if not blocks:
            print(f"  WARNING: no blocks captured for {prefix}", file=sys.stderr)
        sections.append(f"/* {prefix} */\n" + "\n".join(blocks))

    print("Vendoring material-symbols-outlined ...")
    sections.append("/* material-symbols-outlined */\n" + "\n".join(vendor_material_symbols()))

    header = (
        "/*\n"
        " * Self-hosted web fonts. Generated by scripts/vendor_fonts.py.\n"
        " * Do not edit by hand; re-run the script to regenerate.\n"
        " * woff2 files live in static/fonts/.\n"
        " */\n\n"
    )
    with open(CSS_OUT, "w") as fh:
        fh.write(header + "\n\n".join(sections) + "\n")
    print(f"Wrote {CSS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
