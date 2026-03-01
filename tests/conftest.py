"""tests 包的路径配置，确保 src/ 在导入路径中。"""
import sys
from pathlib import Path

# 项目根目录和 src 目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
