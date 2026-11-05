#!/usr/bin/env python3
"""Download a zoomable image from himalayanart.org and stitch its tiles into
one full-resolution image.

Usage:
  python -I fetch_har_image.py <item_id | himalayanart.org URL> [-o OUT.jpg]
           [--proxy http://127.0.0.1:7890] [--keep-tiles] [--quality 95]

Only stdlib + Pillow are required.
"""
import argparse
import json
import math
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SITE = "https://www.himalayanart.org"
TILE_SIZE = 256


def make_opener(proxy=None):
    jar = CookieJar()
    handlers = [urllib.request.HTTPCookieProcessor(jar)]
    if proxy:
        handlers.append(urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def detect_proxy():
    """Return a proxy URL from env vars or a common local proxy port."""
    for k in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY",
              "all_proxy", "ALL_PROXY"):
        v = os.environ.get(k)
        if v:
            return v
    for port in (7890, 7897, 1080, 10808, 8888, 8118, 2080):
        s = socket.socket()
        s.settimeout(0.4)
        try:
            s.connect(("127.0.0.1", port))
            return "http://127.0.0.1:%d" % port
        except OSError:
            continue
        finally:
            s.close()
    return None


class Fetcher:
    """HTTP fetcher bound to one cookie jar.

    If a proxy is known up front it is used from the first request (direct
    connections to this site are commonly DNS-poisoned); otherwise the
    fetcher upgrades itself to a detected local proxy after the first
    network failure.
    """

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.opener = make_opener(proxy)

    def get(self, url, referer=None, timeout=45, retries=2):
        last = None
        for _ in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA,
                    "Accept": "*/*",
                    **({"Referer": referer} if referer else {}),
                })
                with self.opener.open(req, timeout=timeout) as r:
                    return r.read()
            except Exception as e:
                last = e
                if self.proxy is None:
                    p = detect_proxy()
                    if p:
                        print("direct fetch failed (%s); switching to "
                              "proxy %s" % (e.__class__.__name__, p))
                        self.proxy = p
                        self.opener = make_opener(p)
        raise last


def parse_item_id(arg):
    m = re.search(r"items/(\d+)", arg)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d{3,}", arg.strip()):
        return arg.strip()
    sys.exit("cannot parse an item id out of: %r" % arg)


def get_tile_base(fetcher, item_id, item_url):
    """Fetch the primary viewer page and extract the S3 tile base URL."""
    primary_url = "%s/items/%s/images/primary" % (SITE, item_id)
    try:
        html = fetcher.get(primary_url, referer=item_url)
        m = re.search(rb"https://har-assets[^\"']+?metadata\.json", html)
        if m:
            return m.group(0).decode()[: -len("/metadata.json")]
        print("primary page loaded but no metadata url found; "
              "falling back to id-pattern")
    except Exception as e:
        print("primary page unreachable (%s); falling back to id-pattern"
              % e.__class__.__name__)
    # Fallback: HAR stores tiles at tiles/<d1>/<d2>/<d3>/<id>
    i = str(item_id)
    return "%s/tiles/%s/%s/%s/%s" % (
        "https://har-assets.s3.amazonaws.com", i[0], i[1], i[2], i)


def download_tile(fetcher, url, dest, attempts=3):
    for k in range(attempts):
        try:
            data = fetcher.get(url, referer=SITE + "/", retries=0)
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except Exception:
            if k == attempts - 1:
                return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="item id or himalayanart.org URL")
    ap.add_argument("-o", "--output", default=None,
                    help="output jpg path (default har_<id>_full.jpg)")
    ap.add_argument("--proxy", default=None,
                    help="proxy url, e.g. http://127.0.0.1:7890 "
                         "(default: auto-detect)")
    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--keep-tiles", action="store_true")
    args = ap.parse_args()

    item_id = parse_item_id(args.target)
    item_url = "%s/items/%s" % (SITE, item_id)

    proxy = args.proxy
    if proxy is None:
        proxy = detect_proxy()
        if proxy:
            print("auto-detected local proxy: %s" % proxy)
    fetcher = Fetcher(proxy)

    # Warm up the session: visit the item page first so the site sets its
    # cookies; the primary route 403s without them.
    try:
        fetcher.get(item_url)
    except Exception:
        pass

    base = get_tile_base(fetcher, item_id, item_url)
    print("tile base: %s" % base)

    meta_bytes = fetcher.get(base + "/metadata.json")
    meta = json.loads(meta_bytes)
    width, height, max_zoom = (int(meta["width"]), int(meta["height"]),
                               int(meta["maxZoom"]))
    top = max_zoom - 1  # viewer uses mapMaxZoom = maxZoom - 1 (0-based)
    cols = math.ceil(width / TILE_SIZE)
    rows = math.ceil(height / TILE_SIZE)
    print("image %dx%d, zoom levels 0..%d (top=%d), grid %dx%d = %d tiles"
          % (width, height, max_zoom - 1, top, cols, rows, cols * rows))

    tiles_dir = tempfile.mkdtemp(prefix="har_%s_tiles_" % item_id)
    jobs = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for x in range(cols):
            for y in range(rows):
                url = "%s/%d/%d_%d.jpg" % (base, top, x, y)
                dest = os.path.join(tiles_dir, "%d_%d.jpg" % (x, y))
                jobs.append((x, y, pool.submit(download_tile, fetcher, url,
                                               dest)))
    failed = [(x, y) for x, y, f in jobs if not f.result()]
    ok = len(jobs) - len(failed)
    print("downloaded %d/%d tiles" % (ok, len(jobs)))
    if failed:
        print("FAILED tiles: %s" % failed)

    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow missing: pip install pillow "
                 "(mirror: -i https://pypi.tuna.tsinghua.edu.cn/simple)")

    canvas = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE),
                       (255, 255, 255))
    for x in range(cols):
        for y in range(rows):
            p = os.path.join(tiles_dir, "%d_%d.jpg" % (x, y))
            if os.path.exists(p):
                with Image.open(p) as t:
                    canvas.paste(t.convert("RGB"), (x * TILE_SIZE,
                                                    y * TILE_SIZE))
    final = canvas.crop((0, 0, width, height))

    out = args.output or "har_%s_full.jpg" % item_id
    final.save(out, "JPEG", quality=args.quality, subsampling=1)
    print("saved: %s (%dx%d, %.1f MB)" % (
        os.path.abspath(out), width, height,
        os.path.getsize(out) / 1048576))

    if args.keep_tiles:
        keep = os.path.join(os.path.dirname(os.path.abspath(out)),
                            "har_%s_tiles" % item_id)
        shutil.rmtree(keep, ignore_errors=True)
        shutil.move(tiles_dir, keep)
        print("tiles kept at: %s" % keep)
    else:
        shutil.rmtree(tiles_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
