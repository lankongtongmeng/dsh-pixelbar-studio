"""查 DSH 插件市场目录里是否已有 PixelBar 相关条目，并确认 SilverlingFox/dsh-pixelbar 现状。

用法：python tools/probe_market.py
只做只读网络查询，不写任何文件。
"""
import json
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PAT = re.compile(r"pixelbar|halo|edifier|2d99|a106", re.I)

CATALOGS = [
    "https://awesome-dsh-plugin.com/plugins.json",
    "https://cdn.jsdelivr.net/npm/dsh-plugin-catalog/index.json",
    "https://dshmarket.com/index.json",
]


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def find_plugins(obj):
    """在任意嵌套结构里找出最像「插件条目」的 dict 列表。"""
    best = []
    for d in walk(obj):
        if not isinstance(d, dict):
            continue
        keys = set(d)
        # 典型条目：有 name/id/package + (description|version|repository)
        if ({"name"} <= keys or {"id"} <= keys) and ({"description", "version", "repository", "source"} & keys):
            best.append(d)
    return best


def main():
    for url in CATALOGS:
        print(f"\n===== {url} =====")
        try:
            raw = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"  取用失败：{type(e).__name__}: {e}")
            continue
        text = raw.decode("utf-8", "replace")
        print(f"  字节数：{len(raw)}   含关键词次数：{len(PAT.findall(text))}")
        try:
            obj = json.loads(text)
        except Exception as e:  # noqa: BLE001
            print(f"  JSON 解析失败：{e}")
            for m in PAT.finditer(text):
                a, b = max(0, m.start() - 300), m.end() + 300
                print("  …", text[a:b].replace("\n", " ")[:650])
            continue

        entries = find_plugins(obj)
        print(f"  解析出候选条目：{len(entries)}")
        hits = [d for d in entries if PAT.search(json.dumps(d, ensure_ascii=False))]
        print(f"  命中 PixelBar/Halo/Edifier 的条目：{len(hits)}")
        for d in hits[:6]:
            print("  ---")
            print(json.dumps(d, ensure_ascii=False, indent=1)[:1800])


if __name__ == "__main__":
    main()
