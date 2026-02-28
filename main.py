"""兼容入口：转发到 openai_realtime_transport.app。"""

from pathlib import Path
import importlib
import sys

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_app_module = importlib.import_module("openai_realtime_transport.app")
app = _app_module.app

if __name__ == "__main__":
    import uvicorn
    _config_module = importlib.import_module("openai_realtime_transport.config")
    config = _config_module.config

    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
        log_level="debug" if config.server.debug else "info",
    )
