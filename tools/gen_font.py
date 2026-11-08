#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从社区参考项目提取 5x7 ASCII 点阵字库，生成 pixelbar/font5x7.py。

字库来源：github.com/3441293738/claude-edifier-pixelbar-usage（MIT）
一次性使用；生成后工具包自包含，不再依赖参考项目。
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent   # halo-pixelbar/
sys.path.insert(0, str(HERE / "ref-claude-pixelbar" / "src"))

import claude_usage_to_edifier_pixel_image as ref  # noqa: E402

font = ref.FONT_5X7
out = HERE / "pixelbar" / "font5x7.py"
out.parent.mkdir(exist_ok=True)

lines = [
    '#!/usr/bin/env python3',
    '# -*- coding: utf-8 -*-',
    '"""5x7 ASCII 点阵字库（生成文件，勿手改）。',
    '',
    '来源：github.com/3441293738/claude-edifier-pixelbar-usage (MIT)。',
    '由 tools/gen_font.py 自动提取。每个字形 7 行 x 5 列，字符 "1" 表示亮点。',
    '"""',
    '',
    'FONT_5X7: dict[str, list[str]] = {',
]
for k in sorted(font):
    lines.append(f"    {k!r}: {font[k]!r},")
lines += ["}", ""]
out.write_text("\n".join(lines), encoding="utf-8")
print(f"已生成 {out}（{len(font)} 个字形，{out.stat().st_size} 字节）")
