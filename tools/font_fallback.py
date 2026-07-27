#!/usr/bin/env python3
"""Wire self-hosted Archivo in as a fallback for Adobe Fonts 'acumin-pro'.

Adobe Fonts kits are licensed per-domain, so acumin-pro loads on localhost and on
domains registered to Rachel's kit, but nowhere else -- and when it fails the
browser drops all the way to the default serif, which looks nothing like the site.

Rather than replacing acumin-pro (which would throw away real fidelity where the
licence does apply), this appends a fallback chain:

    "acumin-pro", "Archivo", sans-serif

  - licensed domain / localhost -> real Acumin Pro, unchanged
  - anywhere else (GitHub Pages) -> Archivo, a close open-licensed neo-grotesque
  - worst case -> generic sans, never serif

Archivo is SIL OFL, so unlike Adobe Fonts it can legally be self-hosted and
redistributed from this repo. Its licence is bundled alongside the font files.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["index.html", "about/index.html", "contact/index.html",
         "disclaimer-terms-privacy/index.html", "custom-404/index.html"]

FONT_CSS = "assets/local-fonts/archivo/archivo.css"
STACK = '"acumin-pro","Archivo",sans-serif'
MARKER = "local-fonts/archivo"


def rel_prefix(page):
    return "../" * page.count("/")


def patch_css():
    """Append the fallback chain to every acumin-pro font-family declaration."""
    changed = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, "assets")):
        for fn in files:
            if not fn.endswith(".css") or "local-fonts" in dirpath:
                continue
            p = os.path.join(dirpath, fn)
            with open(p, encoding="utf-8", errors="replace") as f:
                s = f.read()
            if '"acumin-pro"' not in s:
                continue
            # only touch declarations not already carrying the fallback
            new = re.sub(r'"acumin-pro"(?!\s*,\s*"Archivo")', STACK, s)
            if new != s:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(new)
                changed.append((os.path.relpath(p, ROOT), s.count('"acumin-pro"')))
    return changed


def patch_html():
    """Link the Archivo @font-face stylesheet into each page."""
    n = 0
    for page in PAGES:
        p = os.path.join(ROOT, page)
        with open(p, encoding="utf-8") as f:
            s = f.read()
        if MARKER in s:
            continue
        link = '<link rel="stylesheet" href="%s%s"/>' % (rel_prefix(page), FONT_CSS)
        s = re.sub(r"(<head[^>]*>)", r"\1" + link, s, count=1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(s)
        n += 1
    return n


if __name__ == "__main__":
    for path, count in patch_css():
        print("  %-70s %d decls" % (path, count))
    print("  linked stylesheet into %d pages" % patch_html())
