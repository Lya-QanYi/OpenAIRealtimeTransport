#!/usr/bin/env python
"""
WebUI 客户端启动器

启动 Realtime API 服务器并自动在浏览器中打开 WebUI。

使用方式:
    uv run python scripts/push_to_talk_app.py

也可以分开操作:
    1. 终端 1: uv run python main.py          # 启动服务器
    2. 浏览器: 打开 http://localhost:8000      # 访问 WebUI

环境变量:
    SERVER_PORT  - 服务器端口 (默认 8000)
    SERVER_HOST  - 服务器地址 (默认 0.0.0.0)
"""
import os
import time
import threading
import webbrowser

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    port = int(os.getenv("SERVER_PORT", "8000"))
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    url = f"http://localhost:{port}"

    print("=" * 50)
    print("  Realtime Voice Chat - WebUI 启动器")
    print("=" * 50)
    print(f"  服务器地址: {host}:{port}")
    print(f"  WebUI 地址: {url}")
    print("=" * 50)
    print()

    # 延迟 1.5 秒后自动打开浏览器
    def open_browser():
        time.sleep(1.5)
        print(f"🌐 正在打开浏览器: {url}")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    # 启动服务器
    import uvicorn
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
