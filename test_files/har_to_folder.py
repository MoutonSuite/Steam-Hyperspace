#!/usr/bin/env python3
"""
har_to_folder.py — turn a DevTools HAR export + an Elements-panel outerHTML
copy into a local, openable folder (HTML + CSS + JS + images), so you can
iterate on a Steam UI page without reloading the whole client.

Usage:
    1. In the Millennium/Steam CEF DevTools:
         - Elements panel -> right-click <html> -> Copy -> Copy outerHTML
           -> paste into a file, e.g. page_raw.html
         - Network panel -> right-click (or the download icon) ->
           "Save all as HAR with content" -> save as page.har
    2. pip install beautifulsoup4 --break-system-packages
    3. python har_to_folder.py page.har page_raw.html output_folder
    4. Open output_folder/page.html in a normal browser tab.

Notes:
    - This is a frozen snapshot: layout/markup/images are real, but Steam's
      React app isn't running, so nothing dynamic will happen. It's meant
      for CSS/layout iteration, not for testing JS behavior.
    - Resources are namespaced by host, so multiple origins (e.g. Steam's
      local UI host + a CDN) won't collide.
"""
import argparse
import base64
import json
import os
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup


def url_to_relpath(url: str) -> str:
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if not path or path.endswith("/"):
        path += "index.html"
    path = path.lstrip("/")
    host = parsed.netloc or "local"
    return os.path.join(host, path)


def dump_har(har_path: str, out_dir: str) -> dict:
    """Writes every resource body found in the HAR to out_dir, returns a
    map of {original_url: relative_path_used}."""
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)

    url_map = {}
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        content = entry.get("response", {}).get("content", {})
        text = content.get("text")
        if text is None:
            continue  # no body captured for this entry

        rel = url_to_relpath(url)
        full_path = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            if content.get("encoding") == "base64":
                with open(full_path, "wb") as out:
                    out.write(base64.b64decode(text))
            else:
                with open(full_path, "w", encoding="utf-8") as out:
                    out.write(text)
            url_map[url] = rel.replace(os.sep, "/")
        except Exception as e:
            print(f"  skipped {url}: {e}")

    print(f"Extracted {len(url_map)} resources from {har_path}")
    return url_map


def rewrite_html(html_path: str, url_map: dict, out_dir: str) -> str:
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    attr_targets = [("img", "src"), ("link", "href"), ("script", "src"), ("source", "src")]
    rewritten = 0
    for tag_name, attr in attr_targets:
        for el in soup.find_all(tag_name):
            src = el.get(attr)
            if src and src in url_map:
                el[attr] = url_map[src]
                rewritten += 1

    out_path = os.path.join(out_dir, "page.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"Rewrote {rewritten} references -> {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("har_file", help="Path to the exported .har file")
    ap.add_argument("html_file", help="Path to the pasted outerHTML snapshot")
    ap.add_argument("output_dir", help="Folder to write the mirrored page into")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    url_map = dump_har(args.har_file, args.output_dir)
    final_path = rewrite_html(args.html_file, url_map, args.output_dir)
    print(f"\nDone. Open this in a browser: {final_path}")


if __name__ == "__main__":
    main()
