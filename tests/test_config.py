"""
鍗曞厓娴嬭瘯 - .env 鑷姩鍒涘缓銆侀厤缃獙璇併€侀璁炬ā鏉挎鏌?
杩愯: uv run python -m pytest tests/test_config.py -v
"""
import os
import shutil
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# 娴嬭瘯杈呭姪锛氶」鐩牴鐩綍
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from openai_realtime_transport.config import (
    Config, AudioConfig, VADConfig, STTConfig, LLMConfig, TTSConfig, ServerConfig,
    validate_config,
)


# ========== .env 鑷姩鍒涘缓 ==========

class TestEnsureEnvFile:
    """娴嬭瘯 ensure_env_file() 鑷姩鍒涘缓 .env"""

    def _isolate(self, tmp_path: Path):
        """鍒涘缓闅旂鐜: 澶嶅埗 .env.example 鍒颁复鏃剁洰褰曪紝杩斿洖 (.env, .env.example) 璺緞"""
        example = tmp_path / ".env.example"
        env = tmp_path / ".env"
        return env, example

    def test_create_from_example(self, tmp_path):
        """鑻?.env 涓嶅瓨鍦ㄤ絾 .env.example 瀛樺湪 鈫?澶嶅埗鍒涘缓"""
        env, example = self._isolate(tmp_path)
        example.write_text("LLM_MODEL_NAME=Test\n", encoding="utf-8")

        # Mock 璺緞甯搁噺
        import openai_realtime_transport.config as cfg_mod
        with patch.object(cfg_mod, "_ENV_FILE", env), \
             patch.object(cfg_mod, "_ENV_EXAMPLE_FILE", example):
            result = cfg_mod.ensure_env_file()

        assert result is True
        assert env.exists()
        assert env.read_text(encoding="utf-8") == "LLM_MODEL_NAME=Test\n"

    def test_no_overwrite(self, tmp_path):
        """鑻?.env 宸插瓨鍦?鈫?涓嶈鐩栵紝杩斿洖 False"""
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
        """鑻?.env 鍜?.env.example 鍧囦笉瀛樺湪 鈫?鍒涘缓鏈€灏忓寲 .env"""
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


# ========== 閰嶇疆楠岃瘉 ==========

class TestValidateConfig:
    """娴嬭瘯 validate_config() 楠岃瘉閫昏緫"""

    def _make_config(self, **overrides):
        """鍒涘缓涓€涓甫鏈夊悎鐞嗛粯璁ゅ€肩殑 Config 瀹炰緥"""
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
        """瀹屽叏鍚堟硶鐨勯厤缃簲鏃犻敊璇?""
        cfg = self._make_config()
        errors = validate_config(cfg)
        real_errors = [e for e in errors if e.level == "error"]
        assert real_errors == []

    def test_missing_llm_api_key(self):
        """LLM_API_KEY 涓虹┖搴旀姤閿?""
        cfg = self._make_config(llm_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_API_KEY" in fields

    def test_missing_llm_base_url(self):
        """LLM_BASE_URL 涓虹┖搴旀姤閿?""
        cfg = self._make_config(llm_base_url="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_BASE_URL" in fields

    def test_invalid_llm_base_url(self):
        """LLM_BASE_URL 鏃犳晥鏍煎紡搴旀姤閿?""
        cfg = self._make_config(llm_base_url="not-a-url")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_BASE_URL" in fields

    def test_missing_llm_model_id(self):
        """LLM_MODEL_ID 涓虹┖搴旀姤閿?""
        cfg = self._make_config(llm_model_id="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_MODEL_ID" in fields

    def test_missing_llm_model_name_warning(self):
        """LLM_MODEL_NAME 涓虹┖搴斾骇鐢?warning (闈?error)"""
        cfg = self._make_config(llm_model_name="")
        errors = validate_config(cfg)
        warnings = [e for e in errors if e.level == "warning" and e.field == "LLM_MODEL_NAME"]
        assert len(warnings) == 1

    def test_temperature_out_of_range(self):
        """LLM_TEMPERATURE 瓒呭嚭鑼冨洿搴旀姤閿?""
        cfg = self._make_config(llm_temperature=3.0)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "LLM_TEMPERATURE" in fields

    def test_invalid_stt_provider(self):
        """涓嶆敮鎸佺殑 STT_PROVIDER 搴旀姤閿?""
        cfg = self._make_config(stt_provider="unknown")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "STT_PROVIDER" in fields

    def test_deepgram_missing_api_key(self):
        """浣跨敤 Deepgram 浣嗘棤 API Key 搴旀姤閿?""
        cfg = self._make_config(stt_provider="deepgram", stt_deepgram_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "DEEPGRAM_API_KEY" in fields

    def test_openai_whisper_fallback_llm_key(self):
        """openai_whisper 浣跨敤 STT_API_KEY 涓虹┖鏃跺洖閫€ LLM_API_KEY 搴旈€氳繃"""
        cfg = self._make_config(stt_provider="openai_whisper", stt_stt_api_key="")
        errors = validate_config(cfg)
        stt_errors = [e for e in errors if e.field == "STT_API_KEY"]
        assert stt_errors == []  # LLM_API_KEY 闈炵┖, 鍥為€€鎴愬姛

    def test_openai_whisper_no_key_at_all(self):
        """openai_whisper 涓?STT_API_KEY 鍜?LLM_API_KEY 鍧囦负绌哄簲鎶ラ敊"""
        cfg = self._make_config(stt_provider="openai_whisper", stt_stt_api_key="", llm_api_key="")
        errors = validate_config(cfg)
        stt_fields = [e.field for e in errors if e.field == "STT_API_KEY"]
        assert len(stt_fields) >= 1

    def test_invalid_tts_provider(self):
        """涓嶆敮鎸佺殑 TTS_PROVIDER 搴旀姤閿?""
        cfg = self._make_config(tts_provider="google_tts")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "TTS_PROVIDER" in fields

    def test_elevenlabs_missing_api_key(self):
        """浣跨敤 ElevenLabs 浣嗘棤 API Key 搴旀姤閿?""
        cfg = self._make_config(tts_provider="elevenlabs", tts_elevenlabs_api_key="")
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "ELEVENLABS_API_KEY" in fields

    def test_openai_tts_fallback_llm_key(self):
        """openai_tts 浣跨敤 TTS_API_KEY 涓虹┖鏃跺洖閫€ LLM_API_KEY 搴旈€氳繃"""
        cfg = self._make_config(tts_provider="openai_tts", tts_tts_api_key="")
        errors = validate_config(cfg)
        tts_errors = [e for e in errors if e.field == "TTS_API_KEY"]
        assert tts_errors == []

    def test_openai_tts_no_key_at_all(self):
        """openai_tts 涓?TTS_API_KEY 鍜?LLM_API_KEY 鍧囦负绌哄簲鎶ラ敊"""
        cfg = self._make_config(tts_provider="openai_tts", tts_tts_api_key="", llm_api_key="")
        errors = validate_config(cfg)
        tts_fields = [e.field for e in errors if e.field == "TTS_API_KEY"]
        assert len(tts_fields) >= 1

    def test_vad_threshold_out_of_range(self):
        """VAD_THRESHOLD 瓒呭嚭 0-1 搴旀姤閿?""
        cfg = self._make_config(vad_threshold=1.5)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "VAD_THRESHOLD" in fields

    def test_server_port_out_of_range(self):
        """SERVER_PORT 瓒呭嚭鑼冨洿搴旀姤閿?""
        cfg = self._make_config(server_port=99999)
        errors = validate_config(cfg)
        fields = [e.field for e in errors if e.level == "error"]
        assert "SERVER_PORT" in fields


# ========== .env.example 妯℃澘瀹屾暣鎬?==========

class TestEnvExampleCompleteness:
    """.env.example 搴斿寘鍚墍鏈夊繀椤荤殑棰勮妯℃澘鍜屽洓瑕佺礌"""

    @pytest.fixture
    def example_content(self) -> str:
        example_path = PROJECT_ROOT / ".env.example"
        assert example_path.exists(), ".env.example 涓嶅瓨鍦?
        return example_path.read_text(encoding="utf-8")

    def test_llm_four_fields_present(self, example_content):
        """LLM 鍥涜绱犻厤缃簲瀛樺湪锛堜綔涓烘椿璺冮厤缃垨娉ㄩ噴棰勮锛?""
        for key in ["LLM_MODEL_NAME", "LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY"]:
            assert key in example_content, f".env.example 缂哄皯 {key}"

    def test_siliconflow_preset(self, example_content):
        """纭呭熀娴佸姩 (SiliconFlow) 棰勮搴斿畬鏁?""
        assert "SiliconFlow" in example_content
        assert "siliconflow" in example_content.lower()
        # 鑷冲皯鍖呭惈 SiliconFlow 鐨?base_url
        assert "api.siliconflow.cn" in example_content

    def test_openai_preset(self, example_content):
        """OpenAI 棰勮搴斿畬鏁?""
        assert "api.openai.com" in example_content
        # 搴旀湁 gpt-4o 鎴栧叾瀹?OpenAI 妯″瀷
        assert "gpt-4o" in example_content

    def test_deepseek_preset(self, example_content):
        """DeepSeek 棰勮搴斿瓨鍦?""
        assert "deepseek" in example_content.lower()

    def test_ollama_preset(self, example_content):
        """Ollama 棰勮搴斿瓨鍦?""
        assert "ollama" in example_content.lower()
        assert "localhost" in example_content

    def test_each_preset_has_four_fields(self, example_content):
        """姣忎釜 LLM 棰勮搴斿寘鍚畬鏁村洓瑕佺礌 (鍦ㄦ敞閲婂潡涓?

        .env.example 涓殑 LLM 棰勮鍧楄В鏋愯鍒欙細
        - 浠讳綍鍚湁 "棰勮:" 鎴?"棰勮锛? 鐨勮濮嬬粓寮€濮嬩竴涓柊鍧楋紙淇濆瓨鍏堝墠鐨勫潡锛屽紑濮嬫柊 current_block锛?
        - 绌鸿缁撴潫褰撳墠鍧楋紙淇濆瓨骞舵竻绌?current_block锛?
        - 鍏朵粬琛岋紙鏃犺娉ㄩ噴杩樻槸娲昏穬閰嶇疆锛夎拷鍔犲埌 current_block
        - 瑙ｆ瀽缁撴潫鍚庤嫢 current_block 闈炵┖鍒欒拷鍔?
        - 姣忎釜鍧楀唴蹇呴』鍖呭惈 LLM_MODEL_NAME/LLM_BASE_URL/LLM_MODEL_ID/LLM_API_KEY
        """
        lines = example_content.splitlines()
        preset_blocks: list[list[str]] = []
        current_block: list[str] = []
        in_preset = False
        for line in lines:
            if "棰勮:" in line or "棰勮锛? in line:
                # 鏂伴璁惧潡寮€濮嬶細淇濆瓨鍏堝墠鐨勫潡锛堝鏈夛級
                if current_block:
                    preset_blocks.append(current_block)
                current_block = [line]
                in_preset = True
            elif in_preset:
                if line.strip() == "":
                    # 绌鸿缁撴潫褰撳墠鍧?
                    if current_block:
                        preset_blocks.append(current_block)
                    current_block = []
                    in_preset = False
                else:
                    current_block.append(line)
        # 鏈€鍚庝竴涓潡
        if current_block:
            preset_blocks.append(current_block)

        assert len(preset_blocks) >= 2, f"鑷冲皯搴旀湁 2 涓?LLM 棰勮锛屾壘鍒?{len(preset_blocks)}"

        four_keys = {"LLM_MODEL_NAME", "LLM_BASE_URL", "LLM_MODEL_ID", "LLM_API_KEY"}
        for block in preset_blocks:
            block_text = "\n".join(block)
            found = {k for k in four_keys if k in block_text}
            assert found == four_keys, (
                f"棰勮鍧楃己灏戝瓧娈? {four_keys - found}\n鍧楀唴瀹?\n{block_text}"
            )

    def test_stt_providers_documented(self, example_content):
        """STT 鎵€鏈?provider 搴旀湁鏂囨。璇存槑"""
        for p in ["deepgram", "openai_whisper", "local_whisper"]:
            assert p in example_content, f".env.example 缂哄皯 STT provider '{p}' 璇存槑"

    def test_tts_providers_documented(self, example_content):
        """TTS 鎵€鏈?provider 搴旀湁鏂囨。璇存槑"""
        for p in ["edge_tts", "openai_tts", "elevenlabs"]:
            assert p in example_content, f".env.example 缂哄皯 TTS provider '{p}' 璇存槑"

    def test_chinese_comments(self, example_content):
        """搴斿寘鍚腑鏂囨敞閲婅鏄?""
        # 鑷冲皯鏈夊涓腑鏂囨敞閲婅
        chinese_comment_count = sum(
            1 for line in example_content.splitlines()
            if line.strip().startswith("#") and any("\u4e00" <= c <= "\u9fff" for c in line)
        )
        assert chinese_comment_count >= 5, f"涓枃娉ㄩ噴琛屽お灏? {chinese_comment_count}"
