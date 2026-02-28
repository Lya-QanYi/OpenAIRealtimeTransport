"""
单元测试 - .env 自动创建、配置验证、预设模板检查
运行: uv run python -m pytest tests/test_config.py -v
"""
import os
import shutil
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# 测试辅助：项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

import sys
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# ========== .env 自动创建 ==========

class TestEnsureEnvFile:
    """测试 ensure_env_file() 自动创建 .env"""

    def _isolate(self, tmp_path: Path):
        """创建隔离环境: 复制 .env.example 到临时目录，返回 (.env, .env.example) 路径"""
        example = tmp_path / ".env.example"
        env = tmp_path / ".env"
        return env, example

    def test_create_from_example(self, tmp_path):
        """若 .env 不存在但 .env.example 存在 → 复制创建"""
        env, example = self._isolate(tmp_path)
        example.write_text("LLM_MODEL_NAME=Test\n", encoding="utf-8")

        # Mock 路径常量
        import openai_realtime_transport.config as cfg_mod
        with patch.object(cfg_mod, "_ENV_FILE", env), \
             patch.object(cfg_mod, "_ENV_EXAMPLE_FILE", example):
            result = cfg_mod.ensure_env_file()

        assert result is True
        assert env.exists()
        assert env.read_text(encoding="utf-8") == "LLM_MODEL_NAME=Test\n"

    def test_no_overwrite(self, tmp_path):
        """若 .env 已存在 → 不覆盖，返回 False"""
        env, example = self._isolate(tmp_path)
        env.write_text("EXISTING=1\n", encoding="utf-8")
        example.write_text("LLM_MODEL_NAME=ShouldNotOverwrite\n", encoding="utf-8")

        import openai_realtime_transport.config as cfg_mod
        with patch.object(cfg_mod, "_ENV_FILE", env), \
             patch.object(cfg_mod, "_ENV_EXAMPLE_FILE", example):
            result = cfg_mod.ensure_env_file()

        assert result is False
        assert "EXISTING=1" in env.read_text(encoding="utf-8")

    def test_no_example_creates_minimal(self, tmp_path):
        """若 .env 和 .env.example 均不存在 → 创建最小化 .env"""
        env, example = self._isolate(tmp_path)

        import openai_realtime_transport.config as cfg_mod
        with patch.object(cfg_mod, "_ENV_FILE", env), \
             patch.object(cfg_mod, "_ENV_EXAMPLE_FILE", example):
            result = cfg_mod.ensure_env_file()

        assert result is True
        assert env.exists()
        content = env.read_text(encoding="utf-8")
        for key in ["LLM_MODEL_NAME", "LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY"]:
            assert key in content


# ========== 配置验证 ==========

class TestValidateConfig:
    """测试 validate_config() 验证逻辑"""

    def _make_config(self, **overrides):
        """创建一个带有合理默认值的 Config 实例"""
        from openai_realtime_transport.config import (
            Config, AudioConfig, VADConfig, STTConfig, LLMConfig, TTSConfig, ServerConfig,
        )
        llm_kw = {
            "model_name": "Test",
            "base_url": "https://api.openai.com/v1",
            "model_id": "gpt-4o",
            "api_key": "sk-test-key-12345678",
            "temperature": 0.7,
            "max_tokens": 4096,
            "system_prompt": "hello",
        }
        stt_kw = {
            "provider": "deepgram",
            "deepgram_api_key": "test-deepgram-key",
            "deepgram_model": "nova-2",
            "deepgram_language": "zh-CN",
            "stt_api_key": "",
            "stt_base_url": "",
            "whisper_model": "base",
        }
        tts_kw = {
            "provider": "edge_tts",
            "edge_tts_voice": "zh-CN-XiaoxiaoNeural",
            "tts_api_key": "",
            "tts_base_url": "",
            "tts_model_id": "tts-1",
            "tts_voice": "alloy",
            "elevenlabs_api_key": "",
            "elevenlabs_voice_id": "x",
            "elevenlabs_model": "x",
        }
        vad_kw = {"threshold": 0.5, "silence_duration_ms": 500, "prefix_padding_ms": 300}
        server_kw = {"host": "0.0.0.0", "port": 8000, "debug": True}

        # Apply overrides by prefix
        for k, v in overrides.items():
            if k.startswith("llm_"):
                llm_kw[k[4:]] = v
            elif k.startswith("stt_"):
                stt_kw[k[4:]] = v
            elif k.startswith("tts_"):
                tts_kw[k[4:]] = v
            elif k.startswith("vad_"):
                vad_kw[k[4:]] = v
            elif k.startswith("server_"):
                server_kw[k[7:]] = v

        return Config(
            audio=AudioConfig(),
            vad=VADConfig(**vad_kw),
            stt=STTConfig(**stt_kw),
            llm=LLMConfig(**llm_kw),
            tts=TTSConfig(**tts_kw),
            server=ServerConfig(**server_kw),
        )

    def test_valid_config_no_errors(self):
        """完全合法的配置应无错误"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config()
        errors = validate_config(cfg)
        real_errors = [e for e in errors if e.level == "error"]
        assert real_errors == []

    def test_missing_llm_api_key(self):
        """LLM_API_KEY 为空应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_API_KEY" in fields

    def test_missing_llm_base_url(self):
        """LLM_BASE_URL 为空应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_base_url="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_BASE_URL" in fields

    def test_invalid_llm_base_url(self):
        """LLM_BASE_URL 无效格式应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_base_url="not-a-url")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_BASE_URL" in fields

    def test_missing_llm_model_id(self):
        """LLM_MODEL_ID 为空应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_model_id="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_MODEL_ID" in fields

    def test_missing_llm_model_name_warning(self):
        """LLM_MODEL_NAME 为空应产生 warning（非 error）"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_model_name="")
        errors = validate_config(cfg)
        warnings = [e for e in errors if e.level == "warning" and e.field == "LLM_MODEL_NAME"]
        assert len(warnings) == 1

    def test_temperature_out_of_range(self):
        """LLM_TEMPERATURE 超出范围应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(llm_temperature=3.0)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_TEMPERATURE" in fields

    def test_invalid_stt_provider(self):
        """不支持的 STT_PROVIDER 应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(stt_provider="unknown")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "STT_PROVIDER" in fields

    def test_deepgram_missing_api_key(self):
        """使用 Deepgram 但无 API Key 应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(stt_provider="deepgram", stt_deepgram_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "DEEPGRAM_API_KEY" in fields

    def test_openai_whisper_fallback_llm_key(self):
        """openai_whisper 使用 STT_API_KEY 为空时回退 LLM_API_KEY 应通过"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(stt_provider="openai_whisper", stt_stt_api_key="")
        errors = validate_config(cfg)
        stt_errors = [e for e in errors if e.field == "STT_API_KEY"]
        assert stt_errors == []  # LLM_API_KEY 非空，回退成功

    def test_openai_whisper_no_key_at_all(self):
        """openai_whisper 且 STT_API_KEY 和 LLM_API_KEY 均为空应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(stt_provider="openai_whisper", stt_stt_api_key="", llm_api_key="")
        errors = validate_config(cfg)
        stt_fields = [e.field for e in errors if e.field == "STT_API_KEY"]
        assert len(stt_fields) >= 1

    def test_invalid_tts_provider(self):
        """不支持的 TTS_PROVIDER 应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(tts_provider="google_tts")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "TTS_PROVIDER" in fields

    def test_elevenlabs_missing_api_key(self):
        """使用 ElevenLabs 但无 API Key 应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(tts_provider="elevenlabs", tts_elevenlabs_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "ELEVENLABS_API_KEY" in fields

    def test_openai_tts_fallback_llm_key(self):
        """openai_tts 使用 TTS_API_KEY 为空时回退 LLM_API_KEY 应通过"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(tts_provider="openai_tts", tts_tts_api_key="")
        errors = validate_config(cfg)
        tts_errors = [e for e in errors if e.field == "TTS_API_KEY"]
        assert tts_errors == []

    def test_openai_tts_no_key_at_all(self):
        """openai_tts 且 TTS_API_KEY 和 LLM_API_KEY 均为空应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(tts_provider="openai_tts", tts_tts_api_key="", llm_api_key="")
        errors = validate_config(cfg)
        tts_fields = [e.field for e in errors if e.field == "TTS_API_KEY"]
        assert len(tts_fields) >= 1

    def test_vad_threshold_out_of_range(self):
        """VAD_THRESHOLD 超出 0-1 应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(vad_threshold=1.5)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "VAD_THRESHOLD" in fields

    def test_server_port_out_of_range(self):
        """SERVER_PORT 超出范围应报错"""
        from openai_realtime_transport.config import validate_config
        cfg = self._make_config(server_port=99999)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "SERVER_PORT" in fields


# ========== .env.example 模板完整性 ==========

class TestEnvExampleCompleteness:
    """.env.example 应包含所有必须的预设模板和四要素"""

    @pytest.fixture
    def example_content(self) -> str:
        example_path = PROJECT_ROOT / ".env.example"
        assert example_path.exists(), ".env.example 不存在"
        return example_path.read_text(encoding="utf-8")

    def test_llm_four_fields_present(self, example_content):
        """LLM 四要素配置应存在（作为活跃配置或注释预设）"""
        for key in ["LLM_MODEL_NAME", "LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY"]:
            assert key in example_content, f".env.example 缺少 {key}"

    def test_siliconflow_preset(self, example_content):
        """硅基流动 (SiliconFlow) 预设应完整"""
        assert "SiliconFlow" in example_content
        assert "siliconflow" in example_content.lower()
        # 至少包含 SiliconFlow 的 base_url
        assert "api.siliconflow.cn" in example_content

    def test_openai_preset(self, example_content):
        """OpenAI 预设应完整"""
        assert "api.openai.com" in example_content
        # 应有 gpt-4o 或其它 OpenAI 模型
        assert "gpt-4o" in example_content

    def test_deepseek_preset(self, example_content):
        """DeepSeek 预设应存在"""
        assert "deepseek" in example_content.lower()

    def test_ollama_preset(self, example_content):
        """Ollama 预设应存在"""
        assert "ollama" in example_content.lower()
        assert "localhost" in example_content

    def test_each_preset_has_four_fields(self, example_content):
        """每个 LLM 预设应包含完整四要素 (在注释块中)

        .env.example 中的 LLM 预设块解析规则：
        - 任何含有 "预设:" 或 "预设：" 的行始终开始一个新块（保存先前的块，开始新 current_block）
        - 空行结束当前块（保存并清空 current_block）
        - 其他行（无论注释还是活跃配置）追加到 current_block
        - 解析结束后若 current_block 非空则追加
        - 每个块内必须包含 LLM_MODEL_NAME/LLM_BASE_URL/LLM_MODEL_ID/LLM_API_KEY
        """
        lines = example_content.splitlines()
        preset_blocks: list[list[str]] = []
        current_block: list[str] = []
        in_preset = False
        for line in lines:
            if "预设:" in line or "预设：" in line:
                # 新预设块开始：保存先前的块（如有）
                if current_block:
                    preset_blocks.append(current_block)
                current_block = [line]
                in_preset = True
            elif in_preset:
                if line.strip() == "":
                    # 空行结束当前块
                    if current_block:
                        preset_blocks.append(current_block)
                    current_block = []
                    in_preset = False
                else:
                    current_block.append(line)
        # 最后一个块
        if current_block:
            preset_blocks.append(current_block)

        assert len(preset_blocks) >= 2, f"至少应有 2 个 LLM 预设，找到 {len(preset_blocks)}"

        four_keys = {"LLM_MODEL_NAME", "LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY"}
        for block in preset_blocks:
            block_text = "\n".join(block)
            found = {k for k in four_keys if k in block_text}
            assert found == four_keys, (
                f"预设块缺少字段: {four_keys - found}\n块内容:\n{block_text}"
            )

    def test_stt_providers_documented(self, example_content):
        """STT 所有 provider 应有文档说明"""
        for p in ["deepgram", "openai_whisper", "local_whisper"]:
            assert p in example_content, f".env.example 缺少 STT provider '{p}' 说明"

    def test_tts_providers_documented(self, example_content):
        """TTS 所有 provider 应有文档说明"""
        for p in ["edge_tts", "openai_tts", "elevenlabs"]:
            assert p in example_content, f".env.example 缺少 TTS provider '{p}' 说明"

    def test_chinese_comments(self, example_content):
        """应包含中文注释说明"""
        # 至少有多个中文注释行
        chinese_comment_count = sum(
            1 for line in example_content.splitlines()
            if line.strip().startswith("#") and any("\u4e00" <= c <= "\u9fff" for c in line)
        )
        assert chinese_comment_count >= 5, f"中文注释行太少: {chinese_comment_count}"
