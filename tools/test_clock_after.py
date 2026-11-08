"""验证「推完自动回时钟」的**脱离式子进程**真的起来了。

为什么不走 `pixelbar image --clock-after` 来测：那条路会真往 category 2-6 写一张图，
把已经烧好的动画覆盖掉。所以这里直接调用 main() 用的那个排程函数，
测的就是同一条代码路径，但不碰设备内容。

用法：python tools/test_clock_after.py [秒数]
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar.cli import _spawn_clock_after  # noqa: E402

delay = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
_spawn_clock_after(delay)
print(f"已排程：{delay:g} 秒后切回时钟（父进程现在退出，子进程应继续存活）")
