"""国内网络可达性检查（无代理直连）。

检查本项目会用到的关键端点，输出每个端点的连通状态。
用法：python scripts/check_network.py
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

ENDPOINTS = [
    ("百炼 DashScope（LLM API）", "https://dashscope.aliyuncs.com/compatible-mode/v1/models"),
    ("Bing 中国（新闻 RSS 宿主）", "https://cn.bing.com"),
    ("GitHub 主页", "https://github.com"),
    ("GitHub API（参考检索）", "https://api.github.com"),
    ("Gitee（国内备选源）", "https://gitee.com"),
    ("清华 PyPI 镜像（uv 依赖源）", "https://pypi.tuna.tsinghua.edu.cn/simple/"),
]


def check(name: str, url: str) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": "CrawlerAgent-network-check/0.1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            print(f"[OK]   {name}  HTTP {resp.status}  {url}")
    except urllib.error.HTTPError as exc:
        print(f"[OK]   {name}  HTTP {exc.code}（可达，鉴权/路径原因）  {url}")
    except Exception as exc:
        print(f"[FAIL] {name}  {exc}  {url}")


def main() -> None:
    socket.setdefaulttimeout(8)
    print("国内网络可达性检查（无代理直连）\n")
    for name, url in ENDPOINTS:
        check(name, url)
    print("\n检查完成：FAIL 表示该端点当前不可达，需要调整方案。")


if __name__ == "__main__":
    main()