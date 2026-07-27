#!/usr/bin/env python3
"""Make the mirror mount-point independent so it works at a site root AND under a
GitHub Pages project subpath (/rachel-clone/).

Three separate problems, three fixes:

1. HTML root-relative refs (/assets/..., /universal/..., /about) become paths
   relative to the page, so they resolve wherever the site is mounted.
2. CSS url(/assets/...) becomes a path relative to the stylesheet's own directory,
   for the same reason.
3. Webpack chunks can't use relative paths -- the bundle resolves them against the
   page URL, which differs per subpage. The bundle reads its publicPath from
   templateScriptsRootUrl, so that gets an origin-absolute value. It only applies
   off-localhost; localhost takes its own branch in the bundle and is unaffected.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = ["index.html", "about/index.html", "contact/index.html",
         "disclaimer-terms-privacy/index.html", "custom-404/index.html"]

# Pages project sites are always served under /<repo>/; chunk loading needs this absolute.
SCRIPTS_ROOT = "/rachel-clone/scripts/"

# Internal page links to rewrite, longest first so /custom-404 isn't clipped by /c...
PAGE_LINKS = ["/disclaimer-terms-privacy", "/custom-404", "/contact", "/about", "/cart"]

NOINDEX = ('<meta name="robots" content="noindex,nofollow,noarchive"/>'
           '<meta name="googlebot" content="noindex,nofollow"/>')

# A URL only starts after one of these; prevents mangling /assets/<host>/universal/...
DELIM = r'(?<=["\'\s,(])'


def rel_prefix(page):
    """'' for a root page, '../' per directory level deep."""
    depth = page.count("/")
    return "../" * depth


def fix_html(page):
    path = os.path.join(ROOT, page)
    with open(path, encoding="utf-8") as f:
        s = f.read()
    orig = s
    pre = rel_prefix(page)

    # 1. asset roots -> relative
    for top in ("assets", "universal", "scripts"):
        s = re.sub(DELIM + re.escape("/" + top + "/"), pre + top + "/", s)

    # 2. internal page links -> relative directory links
    for link in PAGE_LINKS:
        name = link.lstrip("/")
        s = s.replace('href="%s"' % link, 'href="%s%s/"' % (pre, name))
    # bare "/" home links (href="/" only, never a substring of a longer path)
    s = re.sub(r'href="/"', 'href="%s"' % (pre if pre else "./"), s)

    # 3. webpack publicPath source
    s = re.sub(r'"templateScriptsRootUrl":"[^"]*"',
               '"templateScriptsRootUrl":"%s"' % SCRIPTS_ROOT, s)

    # 4. noindex, so the clone can't compete with the real site in search
    if "noindex" not in s:
        s = re.sub(r"(<head[^>]*>)", r"\1" + NOINDEX, s, count=1)

    if s != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
    return len(orig) - len(s)


def fix_css():
    """Rewrite url(/assets/...) relative to each stylesheet's own directory."""
    n = 0
    for dirpath, _, files in os.walk(os.path.join(ROOT, "assets")):
        for fn in files:
            if not fn.endswith(".css"):
                continue
            p = os.path.join(dirpath, fn)
            with open(p, encoding="utf-8", errors="replace") as f:
                s = f.read()
            orig = s

            def to_rel(m):
                target = os.path.join(ROOT, m.group(1).lstrip("/"))
                return "url(" + os.path.relpath(target, dirpath)

            s = re.sub(r"url\(\s*(/(?:assets|universal|scripts)/[^)\s\"']+)", to_rel, s)
            s = re.sub(r"url\(\s*[\"'](/(?:assets|universal|scripts)/[^)\"']+)[\"']",
                       lambda m: "url(" + os.path.relpath(
                           os.path.join(ROOT, m.group(1).lstrip("/")), dirpath), s)
            if s != orig:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(s)
                n += 1
    return n


if __name__ == "__main__":
    for page in PAGES:
        fix_html(page)
        print("  rewrote %s" % page)
    print("  rewrote %d css files" % fix_css())
