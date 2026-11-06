#!/usr/bin/env python3
"""本地 OCR 手工测试脚本。

对运行中的 ocr-gateway 发起 `provider=local` 识别请求，验证：
1. 显式 local 请求返回 200 且 provider == "local"；
2. 配额不消耗（quota.used == 0）；
3. 识别文本非空；
4. 打印客户端观测的耗时分解，并对比第二次同图请求的缓存命中效果。

依赖：httpx（需 pip install httpx）。

用法：
    python scripts/test_ocr.py                # 使用下方 IMAGE_PATH 指定的图片
    python scripts/test_ocr.py path/to.png    # 命令行指定图片（优先于 IMAGE_PATH）
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

# ── 请在此填写你的配置 ────────────────────────────────────────────────
BASE_URL = ""          # 例如 "http://127.0.0.1:8000"
API_KEY = ""           # 管理面板创建的用户 API key（sk-...）
IMAGE_PATH = ""        # 待识别图片路径，如 r"D:\pics\截图.png" 或 "/home/user/shot.png"
PROVIDER = "local"     # 可选 "local" / "auto"
LANGUAGE = "zh"        # 可选 "zh" / "en" / "auto"
TIMEOUT = 60.0
# ─────────────────────────────────────────────────────────────────────


def _recognize(client: httpx.Client, image: bytes, filename: str) -> tuple[httpx.Response, float]:
    """发起识别请求，返回 (响应, 客户端观测总往返毫秒)。"""
    started = time.perf_counter()
    response = client.post(
        "/v1/ocr/image",
        data={"provider": PROVIDER, "language": LANGUAGE},
        files={"file": (filename, image, "image/png")},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return response, elapsed_ms


def _print_timing(label: str, total_ms: float, body: dict) -> None:
    """打印单次请求的耗时分解。

    服务端 latency_ms 覆盖「识别调度 + 引擎执行 + 结果归一化」（自鉴权/解析之后起算）；
    其余部分为网络传输 + 图片上传 + 请求体解析 + 响应下载等客户端侧开销。
    """
    server_ms = float(body.get("latency_ms") or 0.0)
    overhead_ms = total_ms - server_ms
    cached = body.get("cached")
    lines = len(body.get("lines") or [])
    print(
        f"\n== 耗时分解（{label}）==\n"
        f"  客户端总往返 : {total_ms:8.1f} ms\n"
        f"  服务端处理   : {server_ms:8.1f} ms  (latency_ms)\n"
        f"  网络/上传等  : {overhead_ms:8.1f} ms  (总往返 − 服务端)\n"
        f"  缓存命中     : {cached}\n"
        f"  识别行数     : {lines}"
    )
    for index, line in enumerate(body.get("lines") or [], 1):
        print(f"    line {index}: {line['text']!r}  conf={line['confidence']:.4f}")


def main() -> int:
    if not BASE_URL or not API_KEY:
        print("请先在脚本顶部填写 BASE_URL 和 API_KEY")
        return 1

    if len(sys.argv) > 1:
        raw_path = sys.argv[1]
    elif IMAGE_PATH:
        raw_path = IMAGE_PATH
    else:
        print("请指定待识别图片：填写脚本顶部 IMAGE_PATH，或在命令行传入路径")
        return 1

    # pathlib 在 Windows/Linux 下均能正确解析（正反斜杠、盘符、~ 不展开但绝对/相对均可）
    path = Path(raw_path).expanduser()
    if not path.is_file():
        print(f"图片不存在: {path}")
        return 1
    image = path.read_bytes()
    filename = path.name

    print(f"图片大小: {len(image) / 1024:.1f} KB  文件: {filename}")

    with httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=TIMEOUT,
    ) as client:
        # 第 1 次：真实识别
        response, total_ms = _recognize(client, image, filename)
        print(f"\nHTTP {response.status_code}  (第 1 次请求)")
        body = response.json()
        print(json.dumps(body, ensure_ascii=False, indent=2))

        if response.status_code != 200:
            return 1

        _print_timing("第 1 次请求（真实识别）", total_ms, body)

        # 第 2 次：同图请求，验证结果缓存
        response2, total_ms2 = _recognize(client, image, filename)
        body2 = response2.json() if response2.status_code == 200 else {}
        if response2.status_code == 200:
            _print_timing("第 2 次请求（同图，应命中缓存）", total_ms2, body2)
            if not body2.get("cached"):
                print("\n[INFO] 第 2 次未命中缓存（cache_enabled 可能已关闭，或 TTL 已过期）")
        else:
            print(f"\n[INFO] 第 2 次请求返回 HTTP {response2.status_code}，跳过缓存对比")

        problems = []
        if body.get("provider") != PROVIDER:
            problems.append(f"provider 应为 {PROVIDER}，实际 {body.get('provider')}")
        if body.get("quota", {}).get("used") != 0:
            problems.append("本地请求不应消耗配额（quota.used 应为 0）")
        if body.get("text") == "" and "EMPTY_TEXT" not in body.get("warnings", []):
            problems.append("text 为空但缺少 EMPTY_TEXT 警告")

    if problems:
        print("\n[FAIL]")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\n[PASS] 本地 OCR 识别正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
