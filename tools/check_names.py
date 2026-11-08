"""检查候选 npm 包名是否可用（无需登录，只读 registry）。

用法：python tools/check_names.py
"""
import json
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
NAMES = [
    "dsh-pixelbar-studio",
    "dsh-pixelbar-art",
    "dsh-pixelbar-canvas",
    "pixelbar-studio",
    "dsh-halo-pixelbar",
    "halo-pixelbar",
    "dsh-pixelbar-draw",
]


def check(name):
    url = "https://registry.npmjs.org/" + urllib.parse.quote(name)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        latest = (d.get("dist-tags") or {}).get("latest")
        author = d.get("author")
        if isinstance(author, dict):
            author = author.get("name")
        print(f"  [占用] {name:<24} latest={latest}  author={author}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  [可用] {name:<24} —")
        else:
            print(f"  [未知] {name:<24} HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        print(f"  [错误] {name:<24} {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("npm 包名可用性（registry.npmjs.org，2026-11-08）：")
    for n in NAMES:
        check(n)
