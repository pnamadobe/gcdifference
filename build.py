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
    # Find ALL root-relative url(...) refs and pull them into assets/media/.
    # Covers both /_next/static/media/xxx.woff2 AND brand fonts at /fonts/*.woff2
    # (the latter are NOT under /_next and were missed by the original script,
    #  which silently dropped CircularXX and fell back to serif). Skips data:
    #  URIs (inlined fonts) and absolute http(s) urls (e.g. picsum placeholder).
    for m in set(re.findall(r'url\(\s*["\']?(/[^"\')]+)', css)):
        fn = m.rsplit("/", 1)[-1]
        if fn not in media_seen:
            try:
                save(os.path.join(OUT, "assets/media", fn), get(GCT + m))
                media_seen.add(fn)
            except Exception as e:
                print("  ! media", m, e)
        # rewrite this specific root-relative ref -> ../media/<basename>
        css = css.replace(m, "../media/" + fn)
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
