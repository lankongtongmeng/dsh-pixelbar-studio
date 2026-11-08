"""看 SilverlingFox/dsh-pixelbar 现在到底有什么能力（重点：有没有 0x17 位图/动画）。

用法：python tools/probe_dsh_pixelbar.py
只读网络查询。
"""
import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/vnd.github+json"}
REPO = "SilverlingFox/dsh-pixelbar"


def get(url, raw=False, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
    return b.decode("utf-8", "replace") if raw else json.loads(b.decode("utf-8", "replace"))


print("===== 文件树 =====")
try:
    tree = get(f"https://api.github.com/repos/{REPO}/git/trees/HEAD?recursive=1")
    for e in tree.get("tree", []):
        if e["type"] == "blob":
            print(f"  {e.get('size', 0):>8}  {e['path']}")
except Exception as e:  # noqa: BLE001
    print(f"  失败：{type(e).__name__}: {e}")

print("\n===== package.json =====")
try:
    pkg = get(f"https://raw.githubusercontent.com/{REPO}/HEAD/package.json", raw=True)
    print(pkg[:1500])
except Exception as e:  # noqa: BLE001
    print(f"  失败：{type(e).__name__}: {e}")

print("\n===== README 关键能力检索 =====")
try:
    readme = get(f"https://raw.githubusercontent.com/{REPO}/HEAD/README.md", raw=True)
    print(f"  长度 {len(readme)}")
    for kw in ["0x17", "0x17", "bitmap", "位图", "anim", "动画", "gif", "sprite", "精灵", "1064", "133", "category", "槽位", "slot", "clock", "时钟", "color", "校准", "calib"]:
        n = len(re.findall(re.escape(kw), readme, re.I))
        if n:
            print(f"    {kw!r:>12} × {n}")
    print("\n  --- 前 3000 字 ---")
    print(readme[:3000])
except Exception as e:  # noqa: BLE001
    print(f"  失败：{type(e).__name__}: {e}")
