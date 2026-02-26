"""
OpenAI Realtime API 兼容服务器
完全复刻 OpenAI Realtime API 的协议，支持替换为本地或第三方模型

使用方法:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

客户端连接:
    将 OpenAI SDK 的 baseUrl 修改为 ws://localhost:8000 即可
"""
import os
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import config, print_config, validate_config
from realtime_session import session_manager, RealtimeSession
from logger_config import setup_logging, get_logger

# 配置日志
setup_logging(
    level="DEBUG" if config.server.debug else "INFO",
    use_color=True
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("=" * 60)
    logger.info("OpenAI Realtime API 兼容服务器启动")
    logger.info(f"WebSocket 端点: ws://localhost:{config.server.port}{config.server.ws_path}")
    logger.info("=" * 60)
    print_config()  # 打印当前配置（内含验证结果输出）

    # 配置验证——仅对 error 级别拦截启动
    _errors = validate_config(config)
    _blocking = [e for e in _errors if e.level == "error"]
    if _blocking:
        for e in _blocking:
            logger.error("配置错误: %s — %s", e.field, e.message)
        logger.error("存在 %d 个配置错误，服务仍将启动但相关功能可能异常。请修正 .env 后重启。", len(_blocking))
    
    yield
    
    # 关闭时
    logger.info("服务器正在关闭...")


# 创建 FastAPI 应用
app = FastAPI(
    title="OpenAI Realtime API 兼容服务器",
    description="完全复刻 OpenAI Realtime API 协议的本地服务器",
    version="0.1.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
# 从环境变量加载允许的来源，多个来源用逗号分隔
# 例如: CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_allow_credentials = True


# 模块顶部定义常量
_DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]

def _parse_and_validate_cors_origins(env_value: str, *, debug: bool) -> tuple[list[str], bool]:
    """解析并校验 CORS_ORIGINS.
 
     Returns:
         (allowed_origins, allow_credentials)
     """
    raw = (env_value or "")
    stripped = raw.strip()

    candidates = [origin.strip() for origin in stripped.split(",") if origin.strip()]
    
    # 未配置或仅包含分隔符: 使用默认行为
    if not candidates:
        if debug:
            logger.warning(
                "CORS: 未配置 CORS_ORIGINS (为空/仅空格/仅分隔符), DEBUG 模式将使用 allow_origins=['*'];"
                 "allow_credentials 已禁用 (浏览器 CORS 规范要求)."
            )
            return ["*"], False

        defaults = _DEFAULT_CORS_ORIGINS
        
        logger.info(
            "CORS: 未配置 CORS_ORIGINS (为空/仅空格/仅分隔符), 生产模式将使用默认来源: %s",
            _DEFAULT_CORS_ORIGINS,
        )
        return _DEFAULT_CORS_ORIGINS, True
    
    # 校验 URL 格式
    invalid: list[str] = []
    for origin in candidates:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            invalid.append(origin)
 
    if invalid:
         raise ValueError(
            "CORS_ORIGINS 配置包含无效 URL (需要 http/https 且包含主机名，例如: http://localhost:3000), 请修正: "
            + ", ".join(invalid)
        )
 
    logger.info("CORS: 允许的来源: %s", candidates)
    return candidates, True

_cors_allowed_origins, _cors_allow_credentials = _parse_and_validate_cors_origins(
    _cors_origins_env,
    debug=config.server.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 静态文件 ====================

_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ==================== HTTP 端点 ====================

@app.get("/")
async def root():
    """WebUI 主页 - 提供浏览器语音交互界面"""
    index_html = _STATIC_DIR / "index.html"
    if index_html.exists():
        return HTMLResponse(index_html.read_text(encoding="utf-8"))
    # 回退：返回 API 信息
    return {
        "status": "running",
        "service": "OpenAI Realtime API Compatible Server",
        "version": "0.1.0",
        "message": "WebUI 未找到，请确保 static/index.html 存在",
        "endpoints": {
            "websocket": f"ws://localhost:{config.server.port}/v1/realtime",
            "health": "/health",
            "sessions": "/v1/sessions"
        }
    }


@app.get("/api/info")
async def api_info():
    """API 信息端点"""
    return {
        "status": "running",
        "service": "OpenAI Realtime API Compatible Server",
        "version": "0.1.0",
        "endpoints": {
            "websocket": f"ws://localhost:{config.server.port}/v1/realtime",
            "health": "/health",
            "sessions": "/v1/sessions",
            "webui": "/"
        }
    }


# ==================== 配置管理 API ====================

_ENV_FILE = Path(__file__).parent / ".env"
_ENV_EXAMPLE_FILE = Path(__file__).parent / ".env.example"

# 配置项元数据：定义 WebUI 设置面板展示的字段信息
CONFIG_SCHEMA: list[dict] = [
    # ── 服务器 ──
    {"key": "DEBUG", "label": "调试模式", "group": "server", "type": "select", "options": ["true", "false"], "default": "true"},
    {"key": "SERVER_HOST", "label": "监听地址", "group": "server", "type": "text", "default": "0.0.0.0"},
    {"key": "SERVER_PORT", "label": "端口号", "group": "server", "type": "text", "default": "8000"},
    {"key": "CORS_ORIGINS", "label": "CORS 允许来源", "group": "server", "type": "text", "default": "", "placeholder": "多个用逗号分隔"},
    # ── LLM (统一 OpenAI 格式) ──
    {"key": "LLM_MODEL_NAME", "label": "服务商名称", "group": "llm", "type": "text", "default": "", "placeholder": "如 SiliconFlow, OpenAI, DeepSeek"},
    {"key": "LLM_BASE_URL", "label": "API Base URL", "group": "llm", "type": "text", "default": "https://api.openai.com/v1"},
    {"key": "LLM_MODEL_ID", "label": "模型 ID", "group": "llm", "type": "text", "default": "gpt-4o", "placeholder": "如 gpt-4o, deepseek-ai/DeepSeek-V3"},
    {"key": "LLM_API_KEY", "label": "API 密钥", "group": "llm", "type": "password", "default": ""},
    {"key": "LLM_TEMPERATURE", "label": "Temperature", "group": "llm", "type": "text", "default": "0.7"},
    {"key": "LLM_MAX_TOKENS", "label": "Max Tokens", "group": "llm", "type": "text", "default": "4096"},
    {"key": "LLM_SYSTEM_PROMPT", "label": "系统提示词", "group": "llm", "type": "textarea", "default": "你是一个有帮助的AI助手。请用简洁的语言回答问题。"},
    # ── STT ──
    {"key": "STT_PROVIDER", "label": "STT 服务", "group": "stt", "type": "select", "options": ["deepgram", "openai_whisper", "local_whisper"], "default": "deepgram"},
    {"key": "DEEPGRAM_API_KEY", "label": "Deepgram API Key", "group": "stt", "type": "password", "default": "", "show_when": {"STT_PROVIDER": "deepgram"}},
    {"key": "DEEPGRAM_MODEL", "label": "Deepgram 模型", "group": "stt", "type": "text", "default": "nova-2", "show_when": {"STT_PROVIDER": "deepgram"}},
    {"key": "DEEPGRAM_LANGUAGE", "label": "Deepgram 语言", "group": "stt", "type": "text", "default": "zh-CN", "show_when": {"STT_PROVIDER": "deepgram"}},
    {"key": "STT_API_KEY", "label": "STT API Key", "group": "stt", "type": "password", "default": "", "show_when": {"STT_PROVIDER": "openai_whisper"}, "placeholder": "留空则复用 LLM API Key"},
    {"key": "STT_BASE_URL", "label": "STT Base URL", "group": "stt", "type": "text", "default": "", "show_when": {"STT_PROVIDER": "openai_whisper"}, "placeholder": "留空则复用 LLM Base URL"},
    {"key": "WHISPER_MODEL", "label": "Whisper 模型", "group": "stt", "type": "select", "options": ["tiny", "base", "small", "medium", "large"], "default": "base", "show_when": {"STT_PROVIDER": "local_whisper"}},
    # ── TTS ──
    {"key": "TTS_PROVIDER", "label": "TTS 服务", "group": "tts", "type": "select", "options": ["edge_tts", "openai_tts", "elevenlabs"], "default": "edge_tts"},
    {"key": "EDGE_TTS_VOICE", "label": "Edge TTS 声音", "group": "tts", "type": "text", "default": "zh-CN-XiaoxiaoNeural", "show_when": {"TTS_PROVIDER": "edge_tts"}},
    {"key": "EDGE_TTS_PROXY", "label": "Edge TTS 代理", "group": "tts", "type": "text", "default": "", "placeholder": "如 http://127.0.0.1:7890", "show_when": {"TTS_PROVIDER": "edge_tts"}},
    {"key": "TTS_API_KEY", "label": "TTS API Key", "group": "tts", "type": "password", "default": "", "show_when": {"TTS_PROVIDER": "openai_tts"}, "placeholder": "留空则复用 LLM API Key"},
    {"key": "TTS_BASE_URL", "label": "TTS Base URL", "group": "tts", "type": "text", "default": "https://api.openai.com/v1", "show_when": {"TTS_PROVIDER": "openai_tts"}},
    {"key": "TTS_MODEL_ID", "label": "TTS 模型", "group": "tts", "type": "select", "options": ["tts-1", "tts-1-hd"], "default": "tts-1", "show_when": {"TTS_PROVIDER": "openai_tts"}},
    {"key": "TTS_VOICE", "label": "TTS 声音", "group": "tts", "type": "select", "options": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"], "default": "alloy", "show_when": {"TTS_PROVIDER": "openai_tts"}},
    {"key": "ELEVENLABS_API_KEY", "label": "ElevenLabs API Key", "group": "tts", "type": "password", "default": "", "show_when": {"TTS_PROVIDER": "elevenlabs"}},
    {"key": "ELEVENLABS_VOICE_ID", "label": "ElevenLabs Voice ID", "group": "tts", "type": "text", "default": "21m00Tcm4TlvDq8ikWAM", "show_when": {"TTS_PROVIDER": "elevenlabs"}},
    # ── VAD ──
    {"key": "VAD_THRESHOLD", "label": "VAD 灵敏度", "group": "vad", "type": "text", "default": "0.5", "placeholder": "0.0-1.0，越高越不敏感"},
    {"key": "VAD_SILENCE_DURATION_MS", "label": "静音检测 (ms)", "group": "vad", "type": "text", "default": "500"},
    {"key": "VAD_PREFIX_PADDING_MS", "label": "前缀填充 (ms)", "group": "vad", "type": "text", "default": "300"},
]


def _parse_env_file(path: Path) -> dict[str, str]:
    """解析 .env 文件，返回 key=value 字典（忽略注释和空行）"""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # 去除可能的引号包裹
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    """将 key=value 写入 .env 文件，保留注释结构"""
    # 如果已有 .env，保留注释行并更新值；新增的 key 追加到末尾
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    written_keys: set[str] = set()
    output_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            output_lines.append(line)
            continue
        if "=" not in stripped:
            output_lines.append(line)
            continue
        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in values:
            val = values[key]
            # 包含空格或特殊字符时用引号包裹
            if " " in val or "#" in val or "'" in val:
                output_lines.append(f'{key}="{val}"')
            else:
                output_lines.append(f"{key}={val}")
            written_keys.add(key)
        else:
            output_lines.append(line)

    # 追加新增的 key
    for key, val in values.items():
        if key not in written_keys:
            if " " in val or "#" in val or "'" in val:
                output_lines.append(f'{key}="{val}"')
            else:
                output_lines.append(f"{key}={val}")

    path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


@app.get("/api/config/schema")
async def get_config_schema():
    """返回配置项元数据，供前端渲染表单"""
    return {"schema": CONFIG_SCHEMA}


@app.get("/api/config")
async def get_config():
    """读取当前 .env 配置值"""
    values = _parse_env_file(_ENV_FILE)
    # 对于 password 类型的字段，脱敏显示
    secret_keys = {item["key"] for item in CONFIG_SCHEMA if item.get("type") == "password"}
    masked = {}
    for k, v in values.items():
        if k in secret_keys and v:
            if len(v) > 8:
                masked[k] = v[:4] + "****" + v[-4:]
            else:
                masked[k] = "****"
        else:
            masked[k] = v
    return {"values": masked, "env_exists": _ENV_FILE.exists()}


@app.get("/api/config/raw")
async def get_config_raw():
    """读取 .env 原始值（密钥不脱敏，前端写回时使用）"""
    values = _parse_env_file(_ENV_FILE)
    return {"values": values}


@app.post("/api/config")
async def save_config(request: Request):
    """保存配置到 .env 文件"""
    body = await request.json()
    values: dict[str, str] = body.get("values", {})

    if not values:
        raise HTTPException(status_code=400, detail="没有提供任何配置项")

    # 如果 .env 不存在，先从 .env.example 复制一份作为模板
    if not _ENV_FILE.exists() and _ENV_EXAMPLE_FILE.exists():
        _ENV_FILE.write_text(_ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    _write_env_file(_ENV_FILE, values)

    logger.info("配置已保存到 .env 文件，变更的 key: %s", list(values.keys()))
    return {
        "status": "ok",
        "message": "配置已保存。部分配置需要重启服务器才能生效。",
        "changed_keys": list(values.keys()),
    }


@app.get("/settings")
async def settings_page():
    """设置页面"""
    settings_html = _STATIC_DIR / "settings.html"
    if settings_html.exists():
        return HTMLResponse(settings_html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>settings.html not found</h1>", status_code=404)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "active_sessions": session_manager.active_count
    }


@app.get("/v1/sessions")
async def list_sessions():
    """列出活跃会话"""
    return {
        "object": "list",
        "data": [
            {"id": sid, "status": "active"} 
            for sid in session_manager.list_session_ids()
        ],
        "count": session_manager.active_count
    }


# ==================== WebSocket 端点 ====================

@app.websocket("/v1/realtime")
async def websocket_realtime(
    websocket: WebSocket,
    model: Optional[str] = Query(default="gpt-4o-realtime-preview", description="模型名称"),
):
    """
    OpenAI Realtime API 兼容的 WebSocket 端点
    
    支持的查询参数:
    - model: 模型名称（默认: gpt-4o-realtime-preview）
    
    协议:
    - 完全兼容 OpenAI Realtime API 的 JSON 事件格式
    - 音频格式: PCM16, 24kHz, 单声道
    """
    # 验证请求（可选）
    # 在生产环境中，你可能需要验证 Authorization header
    
    await websocket.accept()
    logger.info(f"新的 WebSocket 连接，模型: {model}")
    
    session: Optional[RealtimeSession] = None
    
    try:
        # 创建会话，传递模型参数
        session = await session_manager.create_session(websocket, model=model)
        
        # 运行会话主循环
        await session.run()
        
    except WebSocketDisconnect:
        logger.info("客户端断开连接")
    except Exception as e:
        logger.exception(f"WebSocket 错误: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as close_err:
            logger.warning(f"关闭 WebSocket 时出错: {close_err}")
    finally:
        # 清理会话（不调用 session.stop，由 session.run() 的 finally 块负责）
        if session:
            await session_manager.remove_session(session.state.session_id)


# 备用端点，支持带模型参数的路径
@app.websocket("/v1/realtime/{model_path:path}")
async def websocket_realtime_with_model(
    websocket: WebSocket,
    model_path: str,
):
    """支持路径参数指定模型的 WebSocket 端点"""
    await websocket.accept()
    logger.info(f"新的 WebSocket 连接，模型路径: {model_path}")
    
    session: Optional[RealtimeSession] = None
    
    try:
        # 使用路径中的模型名称
        session = await session_manager.create_session(websocket, model=model_path)
        await session.run()
    except WebSocketDisconnect:
        logger.info("客户端断开连接")
    except Exception as e:
        logger.exception(f"WebSocket 错误: {e}")
    finally:
        # 清理会话（不调用 session.stop，由 session.run() 的 finally 块负责）
        if session:
            await session_manager.remove_session(session.state.session_id)


# ==================== 模拟 OpenAI REST API 端点 ====================

@app.post("/v1/chat/completions")
async def chat_completions():
    """模拟 Chat Completions API（用于兼容性测试）"""
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "message": "此服务器仅支持 Realtime API，请使用 WebSocket 连接",
                "type": "not_implemented",
                "code": "realtime_only"
            }
        }
    )


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4o-realtime-preview",
                "object": "model",
                "created": 1699999999,
                "owned_by": "local",
                "capabilities": {
                    "realtime": True,
                    "audio": True,
                    "text": True
                }
            },
            {
                "id": "gpt-4o-realtime-preview-2024-10-01",
                "object": "model",
                "created": 1699999999,
                "owned_by": "local",
                "capabilities": {
                    "realtime": True,
                    "audio": True,
                    "text": True
                }
            }
        ]
    }


# ==================== 错误处理 ====================

from protocol import generate_id

@app.exception_handler(Exception)
async def global_exception_handler(_request, exc):
    """全局异常处理"""
    # 生成唯一的请求 ID 用于关联日志
    request_id = generate_id("err")
    
    # 记录完整的异常和堆栈跟踪
    logger.exception(f"未处理的异常 [request_id={request_id}]: {exc}")
    
    # 返回通用错误响应，不泄露内部细节
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": "server_error",
                "request_id": request_id
            }
        }
    )


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug,
        log_level="debug" if config.server.debug else "info"
    )