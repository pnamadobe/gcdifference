# Handoff: Static replica of gct.com/grand-circle-difference for GitHub Pages

**Goal:** Build a self-contained, pixel-faithful static replica of
<https://www.gct.com/grand-circle-difference> that can be pushed to GitHub Pages
for a demo. No external calls at runtime, everything local & relative-pathed.

> Resume tip: drop this file into the new working folder and tell a fresh Claude
> session "continue the work in HANDOFF.md". Everything needed is below.

---

## What the source page is (verified 2026-06-16)

- **Next.js (App Router), server-rendered.** `curl` returns the full rendered
  DOM — all text/content is in the HTML (321 KB). Good: no headless browser
  needed.
- Page title: `The Grand Circle Difference`.
- **12 CSS files** under `/_next/static/css/<hash>.css`.
- **25 JS chunks** under `/_next/static/chunks/` — we **strip all `<script>`
  tags**. Reason: on GitHub Pages the `/_next/*` paths 404, so React can't
  hydrate; leaving JS in risks console noise / hydration blanking. Stripping
  keeps the SSR HTML exactly as-is = faithful *visual* snapshot.
  ⚠️ Trade-off: JS-driven interactivity (carousels, mega-menu dropdowns)
  won't work. CSS hover/sticky still work. This is fine for a visual demo.
- **Fonts** are referenced via `url(/_next/static/media/<hash>.woff2)` *inside*
  the CSS files (not preloaded in HTML).
- **Images** come in two forms:
  1. **Direct scene7** content photos:
     `https://grandcircle.scene7.com/is/image/GrandCircle/G#####/16x9/<width>`
     (rendered `<img>` uses `/640`; scene7 serves any width via the last path
     segment — grab `/1920` for crispness).
     Asset IDs: **G24977, G37628, G38856, G46161, G49840, G55210** (6 photos).
  2. **Next image optimizer** `/_next/image?url=<urlencoded scene7>&w=..&q=75`
     for logos/badges. Decoded targets (download the decoded URL verbatim):
     - `GCT_GCCL_twoline?fmt=png-alpha`  → header logo
     - `footer_image_bbb_gct?&scl=1&fmt=png-alpha`
     - `footer_image_logo_gctgccl?&scl=1&fmt=png-alpha`
     - `footer_image_ustoa_gct?&scl=1&fmt=png-alpha`
- Favicons: `/gct-favicon.ico` and `/favicon.ico`.
- No `background-image` inline styles (checked).

## Target output layout

```
<repo-root>/
  index.html
  gct-favicon.ico
  favicon.ico
  assets/
    css/    <12 .css files, font url()s rewritten to ../media/>
    media/  <woff2 fonts referenced by the CSS>
    img/    <G*.jpg content photos + *.png logos/badges>
  .nojekyll        # so GitHub Pages serves /assets/_underscore-free paths fine
```

All paths are **relative** (no leading `/`) so it works on a GitHub *project*
page (`user.github.io/repo/`), not just a root user/org page.

---

## Build script (run once, from the new folder)

This is the whole job. Save as `build.py` in the new folder and run
`python3 build.py`. Idempotent; needs only Python 3 stdlib + network.

```python
#!/usr/bin/env python3
"""Build a static, self-contained replica of gct.com/grand-circle-difference."""
import os, re, sys, urllib.parse, urllib.request

SRC = "https://www.gct.com/grand-circle-difference"
GCT = "https://www.gct.com"
UA  = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OUT = os.path.dirname(os.path.abspath(__file__))

os.makedirs(os.path.join(OUT, "assets/css"),   exist_ok=True)
os.makedirs(os.path.join(OUT, "assets/media"), exist_ok=True)
os.makedirs(os.path.join(OUT, "assets/img"),   exist_ok=True)

def get(url, binary=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")

def save(path, data):
    mode = "wb" if isinstance(data, (bytes, bytearray)) else "w"
    with open(path, mode) as f:
        f.write(data)
    print("  wrote", os.path.relpath(path, OUT))

# 1) HTML --------------------------------------------------------------------
print("Fetching HTML...")
html = get(SRC, binary=False)

# 2) CSS + fonts -------------------------------------------------------------
print("CSS + fonts...")
css_hrefs = sorted(set(re.findall(r'/_next/static/css/[a-z0-9]+\.css', html)))
media_seen = set()
for href in css_hrefs:
    css = get(GCT + href, binary=False)
    # find font/media refs:  url(/_next/static/media/xxx.woff2)
    for m in set(re.findall(r'/_next/static/media/[A-Za-z0-9_.-]+', css)):
        fn = m.rsplit("/", 1)[-1]
        if fn not in media_seen:
            try:
                save(os.path.join(OUT, "assets/media", fn), get(GCT + m))
                media_seen.add(fn)
            except Exception as e:
                print("  ! media", m, e)
    css = css.replace("/_next/static/media/", "../media/")
    save(os.path.join(OUT, "assets/css", href.rsplit("/", 1)[-1]), css)

# 3) Content photos (direct scene7) -----------------------------------------
print("Content photos...")
S7 = "https://grandcircle.scene7.com/is/image/GrandCircle/"
for gid in sorted(set(re.findall(r'/is/image/GrandCircle/(G\d+)/16x9/\d+', html))):
    save(os.path.join(OUT, "assets/img", gid + ".jpg"), get(f"{S7}{gid}/16x9/1920"))

# 4) Next-image optimizer assets (logos / badges) ---------------------------
print("Logos / badges...")
# token form in HTML uses &amp; ; capture encoded url up to first & or &amp;
next_img = re.findall(r'/_next/image\?url=([^"&]+)(?:&amp;|&)[^"\' ]*', html)
asset_map = {}            # token-decoded scene7 url -> local filename
for enc in set(next_img):
    dec = urllib.parse.unquote(enc)                       # full scene7 url
    name = dec.split("/GrandCircle/")[-1].split("?")[0]   # asset id
    ext = "png" if "png" in dec else "jpg"
    fn = f"{name}.{ext}"
    if dec not in asset_map:
        try:
            save(os.path.join(OUT, "assets/img", fn), get(dec))
            asset_map[dec] = fn
        except Exception as e:
            print("  ! img", dec, e)

# 5) Favicons ----------------------------------------------------------------
for ico in ("/gct-favicon.ico", "/favicon.ico"):
    try:
        save(os.path.join(OUT, ico.lstrip("/")), get(GCT + ico))
    except Exception as e:
        print("  ! favicon", ico, e)

# 6) Rewrite HTML ------------------------------------------------------------
print("Rewriting HTML...")
# 6a strip all scripts + script preloads
html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
html = re.sub(r'<script\b[^>]*/>', '', html)
html = re.sub(r'<link[^>]*rel="preload"[^>]*as="script"[^>]*>', '', html)
# 6b css links -> local
html = html.replace("/_next/static/css/", "assets/css/")
# 6c content photos -> local (any width)
html = re.sub(r'https://grandcircle\.scene7\.com/is/image/GrandCircle/(G\d+)/16x9/\d+',
              r'assets/img/\1.jpg', html)
# 6d next/image tokens -> local
def repl_next_img(m):
    enc = re.match(r'/_next/image\?url=([^"&]+)', m.group(0)).group(1)
    dec = urllib.parse.unquote(enc)
    fn = asset_map.get(dec)
    return f"assets/img/{fn}" if fn else m.group(0)
html = re.sub(r'/_next/image\?url=[^"\' ]+', repl_next_img, html)
# 6e favicons -> relative
html = html.replace('href="/gct-favicon.ico"', 'href="gct-favicon.ico"')
html = html.replace('href="/favicon.ico"', 'href="favicon.ico"')
# 6f (optional) make site nav links absolute so they still work off-site.
#     Comment out if you'd rather they stay root-relative.
html = re.sub(r'href="/(?!/)', 'href="https://www.gct.com/', html)

save(os.path.join(OUT, "index.html"), html)
open(os.path.join(OUT, ".nojekyll"), "w").close()
print("DONE.")
```

### Notes / gotchas baked into the script
- Step **6f** rewrites remaining root-relative `href="/..."` (nav menu, footer
  links) to absolute `https://www.gct.com/...` so clicking them works from the
  demo. It runs **after** css/favicon rewrites so it won't clobber them.
  Remove that line if you want a fully offline page.
- `&amp;` vs `&`: in HTML attributes the optimizer URL separators are `&amp;`.
  The regexes account for both. The decoded `url=` param itself has no bare `&`
  (scene7's own `&scl=1` is `%26scl%3D1` when encoded), so capturing up to the
  first `&`/`&amp;` is safe.
- Content photos are pulled at `/1920` even though the page renders `/640` —
  sharper on retina; harmless. Lower to `/1280` if size matters.
- `.nojekyll` is added so GitHub Pages doesn't choke on any `_`-prefixed paths
  (none currently, but cheap insurance).

---

## Verify locally

```bash
cd <repo-root>
python3 -m http.server 8000
# open http://localhost:8000  — compare side-by-side with the live page
```

Spot-check: header logo, all 6 content photos load, fonts render (not fallback
serif), footer badges (BBB / USTOA / GCT-GCCL logo) present, layout matches.

If a content photo is missing, re-check its `G#####` id appears in
`re.findall(... G\d+ ...)`. If fonts fall back, confirm `assets/media/*.woff2`
downloaded and the CSS `url(../media/...)` rewrite happened.

---

## Publish to GitHub Pages

```bash
cd <repo-root>
git init && git add -A && git commit -m "Static replica of gct.com/grand-circle-difference"
gh repo create gct-grand-circle-difference --public --source=. --push
# then enable Pages:
gh api -X POST repos/{owner}/gct-grand-circle-difference/pages \
   -f 'source[branch]=main' -f 'source[path]=/'
# URL: https://<owner>.github.io/gct-grand-circle-difference/
```

(Or in the GitHub UI: Settings → Pages → Deploy from branch → `main` / `/root`.)

---

## Status when this handoff was written
- [x] Confirmed source is SSR Next.js; full HTML obtainable via `curl`.
- [x] Inventoried assets: 12 CSS, 6 content photos, 4 logo/badge images, fonts in CSS.
- [x] Wrote the complete build script (above) — **not yet executed.**
- [ ] Run `build.py`, verify locally, push to GitHub Pages.

Original folder created during investigation: `/Users/pnam/Sandbox/gct-grand-circle-difference/`
(safe to reuse or recreate elsewhere). The throwaway `curl` dump was at
`/tmp/gct.html` (may be gone; the script re-fetches anyway).
