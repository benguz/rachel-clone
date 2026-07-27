# rachelwestlake.com — static mirror

A byte-faithful static capture of <https://www.rachelwestlake.com/>, captured **2026-07-27**,
intended as the baseline for a rework. The live site is built on Squarespace; this is the
rendered public output, flattened to plain files with every asset pulled local.

## Run it

```bash
python3 -m http.server 4321
```

Then open <http://localhost:4321>. Any static server works — the layout mirrors the live URL
structure, so `/about` resolves to `about/index.html` and every internal link works unchanged.

## Layout

```
index.html                    /
about/index.html              /about
contact/index.html            /contact
disclaimer-terms-privacy/     /disclaimer-terms-privacy
cart/index.html               /cart
custom-404/index.html         /custom-404
assets/<host>/<path>          all third-party assets, by original host
scripts/                      Squarespace site-bundle webpack chunks (110 files)
universal/svg/                social-icon sprite
```

Assets keep their original host and path under `assets/` so any file can be traced back to
its source URL: `assets/images.squarespace-cdn.com/content/v1/…` came from
`https://images.squarespace-cdn.com/content/v1/…`.

## Fidelity

Verified against the live site at capture time:

- **Text**: visible text of all 6 pages diffs at ratio `1.0000` — identical.
- **Assets**: 397 local references across the 6 pages, **0 missing**.
- **Rendering**: fonts (Typekit `acumin-pro` + self-hosted `RosieRegular`), the SVG section
  dividers, image-effect shaders, and the custom logo all render as on the live site.

### Capture notes

Two things needed handling beyond a naive mirror, worth knowing if you re-run the capture:

1. **Image formats.** The Squarespace CDN content-negotiates and will hand you WebP bytes under
   a `.png`/`.jpg` filename, which browsers then refuse to decode. All 20 site images were
   re-fetched with an `Accept` header excluding WebP to get the true original format.
2. **Lazy-loaded chunks.** The site bundle pulls ~110 webpack chunks from the site's own
   `/scripts/` origin at runtime; these appear nowhere in the HTML. They were enumerated from the
   chunk manifest inside `site-bundle.*.js` and downloaded.

Squarespace image URLs carry a `?format=<width>w` query. Only one file per image is stored (the
largest rendition); static servers ignore the query, so every `?format=` variant resolves to it.

## Deliberate differences from live

- **Google Analytics removed.** The GTM/`gtag` tags were stripped so a local copy can't report
  hits to the live property. Nothing else was altered.
- **Dynamic backends don't work.** The contact form, cart/checkout, and Squarespace's
  `/api/census/*` analytics beacons POST to endpoints that don't exist here. They fail
  harmlessly and locally — no data leaves the machine.
- **`basics.rachelwestlake.com` not captured** (out of scope). Links to it still point at the
  live subdomain, as do external links (LinkedIn, Instagram, pacboard.org).
- **One asset missing**: `assets.squarespace.com/universal/images-v6/icons/icon-plus-16-dark.png`
  redirects to a host with a mismatched TLS certificate. It is referenced only from Squarespace's
  editor-dialog stylesheet, never from the visitor-facing site.

## Content ownership

The site content, copy, images, and branding are Rachel Westlake Consulting's. This mirror is a
working copy for the rework, not a redistributable asset.
