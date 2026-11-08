"""确认 GitHub 上是否已有 PixelBar 相关的 DSH 插件，以及它们的现状。

用法：python tools/probe_gh_pixelbar.py
只读网络查询。
"""
import json
import urllib.parse
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/vnd.github+json",
}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def show_repo(full):
    try:
        d = get(f"https://api.github.com/repos/{full}")
    except Exception as e:  # noqa: BLE001
        print(f"  [{full}] 取用失败：{type(e).__name__}: {e}")
        return
    print(f"  [{d.get('full_name')}] stars={d.get('stargazers_count')} pushed={d.get('pushed_at')} "
          f"license={(d.get('license') or {}).get('spdx_id')} archived={d.get('archived')}")
    print(f"      desc: {(d.get('description') or '')[:220]}")
    print(f"      url : {d.get('html_url')}")


def search(q):
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": q, "sort": "stars", "order": "desc", "per_page": 15}
    )
    try:
        d = get(url)
    except Exception as e:  # noqa: BLE001
        print(f"  搜索 [{q}] 失败：{type(e).__name__}: {e}")
        return
    print(f"  搜索 [{q}] → 命中 {d.get('total_count')}")
    for it in d.get("items", []):
        print(f"    - {it['full_name']}  ★{it['stargazers_count']}  push={it.get('pushed_at')}")
        print(f"        {(it.get('description') or '')[:180]}")


print("===== 直接确认记忆里的那个插件 =====")
show_repo("SilverlingFox/dsh-pixelbar")

print("\n===== GitHub 搜索 =====")
for q in ["dsh-pixelbar", "pixelbar dsh plugin", "halo pixelbar", "edifier pixelbar"]:
    search(q)
