"""从 community/ 里 vendored 的第三方抓包中，抽出本项目自检真正需要的那部分，
生成本仓库自带的 wiretest/captures.json（只保留 OUT 帧，去掉设备回包与图像 hex）。

为什么要这么做：
  - `pixelbar/cli.py` 的 selftest 只用 `caps[name]["out"]`（第 142 行）与 replay（第 779 行）；
  - 其余字段（`in` / `image_hex` / `ef_payload`）本仓库代码从不读取；
  - 仓库不再需要 vendored 第三方目录即可跑通 52 项自检。

这是一次性脚本：生成的 wiretest/captures.json 会进仓库，community/ 不进。

用法：python tools/make_fixture.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = (ROOT / "community" / "ethan71950701__PixelBar-Display-Hook"
       / "tests__fixtures__captured_uploads.json")
DST = ROOT / "wiretest" / "captures.json"

NOTE = ("OUT 帧抽自 ethan71950701/PixelBar-Display-Hook 的 tests/fixtures/captured_uploads.json"
        "（MIT）。仅保留本项目自检与 replay 用到的 OUT 帧；设备回包与图像 hex 未收录。")


def main() -> int:
    if not SRC.exists():
        print(f"源文件不存在：{SRC}")
        return 1
    src = json.loads(SRC.read_text(encoding="utf-8"))
    out = {"_note": NOTE}
    for name in ("20", "21", "23"):
        if name not in src:
            print(f"[跳过] 源里没有 capture {name}")
            continue
        frames = src[name]["out"]
        out[name] = {"out": frames}
        print(f"capture {name}: {len(frames)} 条 OUT 帧")
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"已写出 {DST}（{DST.stat().st_size:,} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
