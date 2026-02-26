"""
配置文件 - 存放所有服务配置参数
支持从 .env 文件加载配置

LLM 统一使用 OpenAI 兼容格式：MODEL_NAME / BASE_URL / MODEL_ID / API_KEY
STT / TTS 保留 provider 模式，OpenAI 兼容的子类型自动复用 LLM 密钥
"""
import os
import shutil
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── .env 自动创建 ──────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent
_ENV_FILE = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_FILE = _PROJECT_ROOT / ".env.example"


def ensure_env_file() -> bool:
    """确保 .env 文件存在，若不存在则从 .env.example 复制创建。

    Returns:
        True 表示新创建了 .env，False 表示 .env 已存在。
    """
    if _ENV_FILE.exists():
        return False
    if _ENV_EXAMPLE_FILE.exists():
        shutil.copy2(_ENV_EXAMPLE_FILE, _ENV_FILE)
        logger.info("未检测到 .env 文件，已自动从 .env.example 创建。请编辑 .env 填入你的配置后重启。")
        return True
    # 两个文件都不存在时创建最小化 .env
    _ENV_FILE.write_text(
        "# 自动生成的最小配置文件，请补充必要配置项\n"
        "LLM_MODEL_NAME=\nLLM_BASE_URL=\nLLM_MODEL_ID=\nLLM_API_KEY=\n",
        encoding="utf-8",
    )
    logger.warning("未找到 .env 和 .env.example，已创建最小化 .env，请补充配置。")
    return True


# 启动时确保 .env 存在
ensure_env_file()

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass


# ── 数据类 ─────────────────────────────────────────────────

@dataclass
class AudioConfig:
    """音频配置"""
    OPENAI_SAMPLE_RATE: int = 24000
    INTERNAL_SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    SAMPLE_WIDTH: int = 2  # 16-bit PCM
    FRAME_DURATION_MS: int = 20


@dataclass
class VADConfig:
    """语音活动检测配置（内置 Server VAD，自由麦模式）"""
    type: str = "server_vad"
    silence_duration_ms: int = field(default_factory=lambda: int(os.getenv("VAD_SILENCE_DURATION_MS", "500")))
    threshold: float = field(default_factory=lambda: float(os.getenv("VAD_THRESHOLD", "0.5")))
    prefix_padding_ms: int = field(default_factory=lambda: int(os.getenv("VAD_PREFIX_PADDING_MS", "300")))
    enabled: bool = True


@dataclass
class STTConfig:
    """语音转文字配置"""
    # STT 服务提供商: "deepgram", "openai_whisper", "local_whisper"
    provider: str = field(default_factory=lambda: os.getenv("STT_PROVIDER", "deepgram"))

    # Deepgram 配置
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))
    deepgram_model: str = field(default_factory=lambda: os.getenv("DEEPGRAM_MODEL", "nova-2"))
    deepgram_language: str = field(default_factory=lambda: os.getenv("DEEPGRAM_LANGUAGE", "zh-CN"))

    # OpenAI Whisper 配置 — 留空则自动复用 LLM_API_KEY / LLM_BASE_URL
    stt_api_key: str = field(default_factory=lambda: os.getenv("STT_API_KEY", ""))
    stt_base_url: str = field(default_factory=lambda: os.getenv("STT_BASE_URL", ""))

    # 本地 Whisper 配置
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "base"))

    # ── 运行时辅助 ──
    def get_whisper_api_key(self, llm_api_key: str = "") -> str:
        """获取 OpenAI Whisper 实际使用的 API Key（优先 STT_API_KEY，回退 LLM_API_KEY）"""
        return self.stt_api_key or llm_api_key

    def get_whisper_base_url(self, llm_base_url: str = "") -> str:
        """获取 OpenAI Whisper 实际使用的 Base URL（优先 STT_BASE_URL，回退 LLM_BASE_URL）"""
        return self.stt_base_url or llm_base_url or "https://api.openai.com/v1"


@dataclass
class LLMConfig:
    """语言模型配置 (统一 OpenAI 兼容格式)

    四要素:
        model_name — 服务商/配置名称（仅标识用途）
        base_url   — API Base URL
        model_id   — Model ID
        api_key    — API 密钥
    """
    model_name: str = field(default_factory=lambda: os.getenv("LLM_MODEL_NAME", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    model_id: str = field(default_factory=lambda: os.getenv("LLM_MODEL_ID", "gpt-4o"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))

    # 通用参数
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))
    system_prompt: str = field(default_factory=lambda: os.getenv("LLM_SYSTEM_PROMPT", "你是一个有帮助的AI助手。请用简洁的语言回答问题。"))


@dataclass
class TTSConfig:
    """文字转语音配置"""
    # TTS 服务提供商: "edge_tts", "openai_tts", "elevenlabs"
    provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge_tts"))

    # Edge TTS 配置 (免费)
    edge_tts_voice: str = field(default_factory=lambda: os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural"))

    # OpenAI TTS 统一字段 — 留空则自动复用 LLM_API_KEY / LLM_BASE_URL
    tts_api_key: str = field(default_factory=lambda: os.getenv("TTS_API_KEY", ""))
    tts_base_url: str = field(default_factory=lambda: os.getenv("TTS_BASE_URL", "https://api.openai.com/v1"))
    tts_model_id: str = field(default_factory=lambda: os.getenv("TTS_MODEL_ID", "tts-1"))
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "alloy"))

    # ElevenLabs 配置
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))
    elevenlabs_model: str = field(default_factory=lambda: os.getenv("ELEVENLABS_MODEL", "eleven_monolingual_v1"))

    # ── 运行时辅助 ──
    def get_tts_api_key(self, llm_api_key: str = "") -> str:
        """获取 OpenAI TTS 实际使用的 API Key（优先 TTS_API_KEY，回退 LLM_API_KEY）"""
        return self.tts_api_key or llm_api_key

    def get_tts_base_url(self, llm_base_url: str = "") -> str:
        """获取 OpenAI TTS 实际使用的 Base URL（优先 TTS_BASE_URL，回退 LLM_BASE_URL）"""
        return self.tts_base_url or llm_base_url or "https://api.openai.com/v1"


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = field(default_factory=lambda: os.getenv("SERVER_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("SERVER_PORT", "8000")))
    ws_path: str = "/v1/realtime"
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true")


@dataclass
class Config:
    """主配置类"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


# ── 配置验证 ───────────────────────────────────────────────

class ConfigValidationError:
    """单条验证错误"""

    def __init__(self, field: str, message: str, level: str = "error"):
        self.field = field
        self.message = message
        self.level = level  # "error" | "warning"

    def __repr__(self):
        return f"[{self.level.upper()}] {self.field}: {self.message}"


def validate_config(cfg: "Config") -> list[ConfigValidationError]:
    """验证配置完整性和格式。

    Returns:
        验证错误/警告列表，空列表表示通过。
    """
    errors: list[ConfigValidationError] = []

    # ── LLM 四要素 ──
    if not cfg.llm.base_url:
        errors.append(ConfigValidationError("LLM_BASE_URL", "LLM Base URL 未配置"))
    elif not cfg.llm.base_url.startswith(("http://", "https://")):
        errors.append(ConfigValidationError("LLM_BASE_URL", f"LLM Base URL 格式无效 (需要 http/https): {cfg.llm.base_url}"))

    if not cfg.llm.model_id:
        errors.append(ConfigValidationError("LLM_MODEL_ID", "LLM Model ID 未配置"))

    if not cfg.llm.api_key:
        errors.append(ConfigValidationError("LLM_API_KEY", "LLM API Key 未配置"))

    if not cfg.llm.model_name:
        errors.append(ConfigValidationError("LLM_MODEL_NAME", "LLM 模型名称未配置（仅用于标识）", level="warning"))

    # temperature / max_tokens 范围
    if not (0.0 <= cfg.llm.temperature <= 2.0):
        errors.append(ConfigValidationError("LLM_TEMPERATURE", f"Temperature 应在 0.0-2.0 之间，当前: {cfg.llm.temperature}"))
    if cfg.llm.max_tokens < 1:
        errors.append(ConfigValidationError("LLM_MAX_TOKENS", f"Max tokens 应 ≥ 1，当前: {cfg.llm.max_tokens}"))

    # ── STT ──
    valid_stt = {"deepgram", "openai_whisper", "local_whisper"}
    if cfg.stt.provider not in valid_stt:
        errors.append(ConfigValidationError("STT_PROVIDER", f"不支持的 STT Provider: {cfg.stt.provider}，可选: {valid_stt}"))

    if cfg.stt.provider == "deepgram" and not cfg.stt.deepgram_api_key:
        errors.append(ConfigValidationError("DEEPGRAM_API_KEY", "使用 Deepgram STT 但未配置 API Key"))

    if cfg.stt.provider == "openai_whisper":
        actual_key = cfg.stt.get_whisper_api_key(cfg.llm.api_key)
        if not actual_key:
            errors.append(ConfigValidationError("STT_API_KEY", "使用 OpenAI Whisper 但 STT_API_KEY 和 LLM_API_KEY 均为空"))

    # ── TTS ──
    valid_tts = {"edge_tts", "openai_tts", "elevenlabs"}
    if cfg.tts.provider not in valid_tts:
        errors.append(ConfigValidationError("TTS_PROVIDER", f"不支持的 TTS Provider: {cfg.tts.provider}，可选: {valid_tts}"))

    if cfg.tts.provider == "elevenlabs" and not cfg.tts.elevenlabs_api_key:
        errors.append(ConfigValidationError("ELEVENLABS_API_KEY", "使用 ElevenLabs TTS 但未配置 API Key"))

    if cfg.tts.provider == "openai_tts":
        actual_key = cfg.tts.get_tts_api_key(cfg.llm.api_key)
        if not actual_key:
            errors.append(ConfigValidationError("TTS_API_KEY", "使用 OpenAI TTS 但 TTS_API_KEY 和 LLM_API_KEY 均为空"))

    # ── VAD ──
    if not (0.0 <= cfg.vad.threshold <= 1.0):
        errors.append(ConfigValidationError("VAD_THRESHOLD", f"VAD 阈值应在 0.0-1.0 之间，当前: {cfg.vad.threshold}"))
    if cfg.vad.silence_duration_ms < 0:
        errors.append(ConfigValidationError("VAD_SILENCE_DURATION_MS", f"静音时长应 ≥ 0，当前: {cfg.vad.silence_duration_ms}"))

    # ── Server ──
    if not (1 <= cfg.server.port <= 65535):
        errors.append(ConfigValidationError("SERVER_PORT", f"端口号应在 1-65535 之间，当前: {cfg.server.port}"))

    return errors


# ── 全局实例 ───────────────────────────────────────────────

config = Config()


def print_config():
    """打印当前配置（隐藏敏感信息）"""
    def mask_key(key: str) -> str:
        if key and len(key) > 8:
            return key[:4] + "****" + key[-4:]
        return "****" if key else "(未设置)"

    print("=" * 50)
    print("当前服务配置:")
    print("=" * 50)

    # LLM
    print(f"LLM 服务: {config.llm.model_name or '(未命名)'}")
    print(f"  - Base URL: {config.llm.base_url}")
    print(f"  - Model ID: {config.llm.model_id}")
    print(f"  - API Key:  {mask_key(config.llm.api_key)}")

    # STT
    print(f"STT 服务: {config.stt.provider}")
    if config.stt.provider == "deepgram":
        print(f"  - API Key: {mask_key(config.stt.deepgram_api_key)}")
        print(f"  - 模型: {config.stt.deepgram_model}")
        print(f"  - 语言: {config.stt.deepgram_language}")
    elif config.stt.provider == "openai_whisper":
        print(f"  - API Key: {mask_key(config.stt.get_whisper_api_key(config.llm.api_key))}")
        print(f"  - Base URL: {config.stt.get_whisper_base_url(config.llm.base_url)}")
    elif config.stt.provider == "local_whisper":
        print(f"  - 模型: {config.stt.whisper_model}")

    # TTS
    print(f"TTS 服务: {config.tts.provider}")
    if config.tts.provider == "elevenlabs":
        print(f"  - API Key: {mask_key(config.tts.elevenlabs_api_key)}")
        print(f"  - Voice ID: {config.tts.elevenlabs_voice_id}")
    elif config.tts.provider == "edge_tts":
        print(f"  - 声音: {config.tts.edge_tts_voice}")
    elif config.tts.provider == "openai_tts":
        print(f"  - API Key: {mask_key(config.tts.get_tts_api_key(config.llm.api_key))}")
        print(f"  - Base URL: {config.tts.get_tts_base_url(config.llm.base_url)}")
        print(f"  - Model: {config.tts.tts_model_id}")
        print(f"  - Voice: {config.tts.tts_voice}")

    # VAD
    print(f"VAD 配置:")
    print(f"  - 阈值: {config.vad.threshold}")
    print(f"  - 静音时长: {config.vad.silence_duration_ms}ms")

    # 验证结果
    validation_errors = validate_config(config)
    if validation_errors:
        print("=" * 50)
        print("⚠️  配置验证问题:")
        for err in validation_errors:
            print(f"  {err}")
    print("=" * 50)
