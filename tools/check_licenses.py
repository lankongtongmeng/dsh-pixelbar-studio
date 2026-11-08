"""核对本项目借用/派生的第三方仓库的授权，用于写 NOTICE.md。

用法：python tools/check_licenses.py
只读网络查询。
"""
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/vnd.github+json"}
REPOS = [
    "ethan71950701/PixelBar-Display-Hook",   # wiretest/captures.json 的 OUT 帧来源
    "3441293738/claude-edifier-pixelbar-usage",  # 5x7 字库来源
    "Serius117/wafer_pixelbar_public",       # 表情槽位架构参考（未直接抄代码）
    "XFEstudio/HaloPixelToolBox",            # 协议交叉验证
]


def main():
    for full in REPOS:
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{full}", headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            print(f"  {full}: 查询失败 {type(e).__name__}: {e}")
            continue
        lic = d.get("license") or {}
        print(f"  {full}")
        print(f"      license = {lic.get('spdx_id')}  ({lic.get('name')})")
        print(f"      archived={d.get('archived')}  stars={d.get('stargazers_count')}")


if __name__ == "__main__":
    print("第三方来源授权核对：")
    main()
