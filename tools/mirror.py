#!/usr/bin/env python3
"""Mirror www.rachelwestlake.com into a local static site."""

import os
import re
import sys
import time
import gzip
import shutil
import subprocess
import urllib.request
import urllib.parse
from collections import OrderedDict

SITE = "https://www.rachelwestlake.com"
OUT = "/Users/benguzovsky/rachel-rework"
ASSET_DIR = "assets"

PAGES = OrderedDict([
    ("/", "index.html"),
    ("/about", "about/index.html"),
    ("/contact", "contact/index.html"),
    ("/disclaimer-terms-privacy", "disclaimer-terms-privacy/index.html"),
    ("/cart", "cart/index.html"),
    ("/custom-404", "custom-404/index.html"),
])

ASSET_HOSTS = {
    "images.squarespace-cdn.com",
    "file.squarespace-cdn.com",
    "static1.squarespace.com",
    "assets.squarespace.com",
    "definitions.sqspcdn.com",
    "use.typekit.net",
    "p.typekit.net",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "code.jquery.com",
    "unpkg.com",
    "kit.fontawesome.com",
    "ka-p.fontawesome.com",
    "cdn.jsdelivr.net",
    "www.rachelwestlake.com",
}

ASSET_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".avif", ".ico", ".bmp",
    ".css", ".js", ".mjs", ".json", ".map",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".webm", ".mov", ".mp3", ".wav", ".pdf", ".txt", ".xml",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

URL_RE = re.compile(r"""(?:https?:)?//[^\s"'()<>\\\]}]+""")

# url -> local root-relative path
mapping = {}
failed = []
downloaded = set()


def fetch(url, tries=3):
    """Fetch via curl (system cert store); returns (bytes, content-type) or (None, err)."""
    if url.startswith("//"):
        url = "https:" + url
    for attempt in range(tries):
        proc = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", "90",
             "-A", UA, "-w", "\n%{http_code}\t%{content_type}", "--output", "-", url],
            capture_output=True)
        if proc.returncode == 0:
            out = proc.stdout
            nl = out.rfind(b"\n")
            trailer = out[nl + 1:].decode("utf-8", "replace")
            body = out[:nl]
            code, _, ctype = trailer.partition("\t")
            if code.startswith("2"):
                return body, ctype
            err = "HTTP " + code
        else:
            err = proc.stderr.decode("utf-8", "replace").strip()[:200] or "curl error"
        if attempt == tries - 1:
            return None, err
        time.sleep(1 + attempt)
    return None, "unreachable"


def base_of(url):
    """Scheme+host+path, no query/fragment."""
    if url.startswith("//"):
        url = "https:" + url
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("https", p.netloc, p.path, "", ""))


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def is_asset(url):
    if url.startswith("//"):
        url = "https:" + url
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or p.netloc not in ASSET_HOSTS:
        return False
    if p.netloc == "www.rachelwestlake.com" and ext_of(p.path) not in ASSET_EXT:
        return False
    if ext_of(p.path) in ASSET_EXT:
        return True
    # extension-less JS packages (unpkg, typekit)
    if p.netloc in ("unpkg.com", "use.typekit.net", "p.typekit.net"):
        return True
    return False


def sanitize(seg):
    seg = urllib.parse.unquote(seg)
    seg = re.sub(r"[^A-Za-z0-9._@+-]", "_", seg)
    return seg[:120] or "_"


def local_path_for(url):
    """Root-relative local path for an asset URL (query stripped)."""
    b = base_of(url)
    if b in mapping:
        return mapping[b]
    p = urllib.parse.urlsplit(b)
    segs = [sanitize(s) for s in p.path.split("/") if s]
    if not segs:
        segs = ["index"]
    if ext_of(segs[-1]) not in ASSET_EXT:
        # give extension-less resources a .js suffix (they are JS in practice)
        segs[-1] = segs[-1] + ".js"
    rel = "/".join([ASSET_DIR, sanitize(p.netloc)] + segs)
    # avoid file/dir collisions
    full = os.path.join(OUT, rel)
    n = 1
    while os.path.isdir(full):
        root, e = os.path.splitext(rel)
        rel = "%s-%d%s" % (root, n, e)
        full = os.path.join(OUT, rel)
        n += 1
    mapping[b] = "/" + rel
    return "/" + rel


def best_variant(base, seen_urls):
    """Pick the URL to actually download for a given base path."""
    if "images.squarespace-cdn.com" in base or "static1.squarespace.com" in base:
        if ext_of(base) in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"):
            # request the largest Squarespace rendition
            if "/content/" in base or "/static/" in base:
                return base + "?format=2500w"
    # otherwise reuse the longest original query seen (e.g. ?nocustom=true)
    best = base
    for u in seen_urls:
        if base_of(u) == base and len(u) > len(best):
            best = u
    return best


def save(rel_path, data):
    full = os.path.join(OUT, rel_path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(data)


def collect_urls(text):
    out = []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;:")
        # trim trailing junk from srcset / css
        u = u.split("\\")[0]
        if is_asset(u):
            out.append(u)
    return out


def process_css(css_text, css_url):
    """Download assets referenced from a CSS file; return rewritten CSS."""
    found = []

    def resolve(ref):
        ref = ref.strip().strip('"').strip("'")
        if not ref or ref.startswith("data:") or ref.startswith("#"):
            return None
        return urllib.parse.urljoin(css_url, ref)

    refs = set()
    for m in re.finditer(r"url\(\s*([^)]+?)\s*\)", css_text):
        r = resolve(m.group(1))
        if r:
            refs.add(r)
    for m in re.finditer(r"""@import\s+(?:url\()?\s*["']([^"')]+)["']""", css_text):
        r = resolve(m.group(1))
        if r:
            refs.add(r)

    for r in refs:
        if is_asset(r):
            found.append(r)

    return found


def download_asset(url, seen_urls, depth=0):
    b = base_of(url)
    if b in downloaded:
        return
    downloaded.add(b)
    rel = local_path_for(b)
    dl_url = best_variant(b, seen_urls)
    data, ctype = fetch(dl_url)
    if data is None:
        # retry without the format upgrade
        if dl_url != b:
            data, ctype = fetch(b)
    if data is None:
        failed.append((b, ctype))
        print("  FAIL %s (%s)" % (b, ctype))
        return
    if ext_of(rel) == ".css" and depth < 4:
        text = data.decode("utf-8", "replace")
        refs = process_css(text, b)
        for r in refs:
            download_asset(r, seen_urls, depth + 1)
        text = rewrite(text)
        data = text.encode("utf-8")
    save(rel, data)
    print("  ok  %-9s %s" % (len(data), b))


def rewrite(text):
    """Replace absolute asset URLs with local root-relative paths."""
    if not mapping:
        return text
    # longest first so prefixes don't clobber
    for b in sorted(mapping, key=len, reverse=True):
        local = mapping[b]
        p = urllib.parse.urlsplit(b)
        variants = [
            b,
            "http://" + p.netloc + p.path,
            "//" + p.netloc + p.path,
        ]
        for v in variants:
            if v in text:
                text = text.replace(v, local)
    return text


def strip_analytics(html):
    """Remove Google Analytics/GTM so the clone doesn't report to the live property."""
    html = re.sub(
        r'<script[^>]*googletagmanager\.com[^>]*>\s*</script>', "", html, flags=re.I)
    html = re.sub(
        r"<script>\s*window\.dataLayer[\s\S]{0,600}?</script>", "", html, flags=re.I)
    return html


def main():
    # 1. fetch all pages
    print("== fetching pages ==")
    raw = OrderedDict()
    for path, dest in PAGES.items():
        data, ctype = fetch(SITE + path)
        if data is None:
            print("  FAIL page %s (%s)" % (path, ctype))
            continue
        raw[dest] = data.decode("utf-8", "replace")
        print("  ok  %-9s %s" % (len(data), path))

    # 2. collect every asset URL across all pages
    print("== collecting assets ==")
    seen_urls = []
    for html in raw.values():
        seen_urls.extend(collect_urls(html))
    bases = []
    for u in seen_urls:
        b = base_of(u)
        if b not in bases:
            bases.append(b)
    print("  %d unique assets" % len(bases))

    # 3. download them (CSS recursion pulls in fonts/images)
    print("== downloading assets ==")
    for b in bases:
        download_asset(b, seen_urls)

    # 4. rewrite + write pages
    print("== writing pages ==")
    for dest, html in raw.items():
        html = rewrite(html)
        html = strip_analytics(html)
        save(dest, html.encode("utf-8"))
        print("  wrote %s" % dest)

    print("\n%d assets saved, %d failed" % (len(downloaded) - len(failed), len(failed)))
    for u, e in failed:
        print("  failed: %s -- %s" % (u, e))


if __name__ == "__main__":
    main()
