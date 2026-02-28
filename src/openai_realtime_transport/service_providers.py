"""
服务提供商工厂 - 根据配置创建对应的 STT/LLM/TTS 服务实例
"""
import os
import asyncio
import logging
from typing import Optional, Callable, Awaitable
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ==================== STT 服务抽象基类 ====================

class BaseSTTProvider(ABC):
    """STT 服务抽象基类"""
    
    # 默认采样率（与 protocol.py AudioFormat 保持一致）
    DEFAULT_SAMPLE_RATE: int = 24000
    
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> str:
        """将音频转换为文本
        
        Args:
            audio_bytes: 原始 PCM 音频数据
            sample_rate: 音频采样率 (Hz)，默认 24000
        
        Returns:
            转录的文本
        """
        pass


class DeepgramSTTProvider(BaseSTTProvider):
    """Deepgram STT 服务"""
    
    def __init__(self, api_key: str, model: str = "nova-2", language: str = "zh-CN"):
        self.api_key = api_key
        self.model = model
        self.language = language
        self._client = None
        
    async def _get_client(self):
        if self._client is None:
            try:
                # deepgram-sdk>=5 使用关键字参数初始化；并提供 AsyncDeepgramClient 用于异步调用
                from deepgram import AsyncDeepgramClient
                self._client = AsyncDeepgramClient(api_key=self.api_key)
            except ImportError as err:
                raise ImportError("请安装 deepgram-sdk: pip install deepgram-sdk") from err
        return self._client
    
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = BaseSTTProvider.DEFAULT_SAMPLE_RATE) -> str:
        """使用 Deepgram 进行语音识别"""
        try:
            client = await self._get_client()

            if not audio_bytes:
                return ""

            # 防御性处理：PCM16 必须 2 字节对齐
            if len(audio_bytes) % 2 != 0:
                logger.warning("Deepgram: audio_bytes 长度非 2 字节对齐，已截断最后 1 字节")
                audio_bytes = audio_bytes[:-1]

            # Deepgram 对 raw PCM 的参数组合非常敏感（采样率/编码/头信息不匹配会报 400）。
            # 这里统一封装为 WAV 再上传，让服务端按 WAV 头解析。
            import io
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(int(sample_rate))
                wav_file.writeframes(audio_bytes)
            wav_bytes = wav_buffer.getvalue()

            from deepgram.core.request_options import RequestOptions
            request_options = RequestOptions(
                additional_headers={
                    "Content-Type": "audio/wav",
                }
            )

            response = await client.listen.v1.media.transcribe_file(
                request=wav_bytes,
                model=self.model,
                language=self.language,
                smart_format=True,
                request_options=request_options,
            )
            
            transcript = response.results.channels[0].alternatives[0].transcript
            logger.info(f"📝 转录: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"Deepgram 转录错误: {e}")
            return ""


class OpenAIWhisperSTTProvider(BaseSTTProvider):
    """OpenAI Whisper STT 服务"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
        
    async def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError as err:
                raise ImportError("请安装 openai: pip install openai") from err
        return self._client
    
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = BaseSTTProvider.DEFAULT_SAMPLE_RATE) -> str:
        """使用 OpenAI Whisper 进行语音识别"""
        try:
            import io
            import wave
            
            # 验证 sample_rate
            if not isinstance(sample_rate, int) or sample_rate <= 0:
                logger.warning(f"sample_rate 无效 ({sample_rate})，使用默认值 {self.DEFAULT_SAMPLE_RATE}")
                sample_rate = self.DEFAULT_SAMPLE_RATE
            
            client = await self._get_client()
            
            # 将 PCM 转换为 WAV 格式
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)
            wav_buffer.seek(0)
            wav_buffer.name = "audio.wav"
            
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_buffer,
                language="zh"
            )
            
            transcript = response.text
            logger.info(f"📝 转录: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"OpenAI Whisper 转录错误: {e}")
            return ""


class LocalWhisperSTTProvider(BaseSTTProvider):
    """本地 Whisper STT 服务"""
    
    def __init__(self, model: str = "base"):
        self.model_name = model
        self._model = None
        
    def _load_model(self):
        if self._model is None:
            try:
                import whisper  # type: ignore
                logger.info(f"加载本地 Whisper 模型: {self.model_name}")
                self._model = whisper.load_model(self.model_name)
            except ImportError:
                raise ImportError("请安装 openai-whisper: pip install openai-whisper")
        return self._model
    
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = BaseSTTProvider.DEFAULT_SAMPLE_RATE) -> str:
        """使用本地 Whisper 进行语音识别"""
        import os
        import tempfile
        import wave
        
        # 验证 sample_rate
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            logger.warning(f"sample_rate 无效 ({sample_rate})，使用默认值 {self.DEFAULT_SAMPLE_RATE}")
            sample_rate = self.DEFAULT_SAMPLE_RATE
        
        temp_path: str | None = None
        try:
            model = self._load_model()
            
            # 将音频写入临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_bytes)
            
            # 在线程池中运行 Whisper（使用 asyncio.get_running_loop 替代已弃用的 get_event_loop）
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: model.transcribe(temp_path, language="zh")
            )
            
            transcript = result["text"].strip()
            logger.info(f"📝 转录: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"本地 Whisper 转录错误: {e}")
            return ""
        finally:
            # 确保临时文件始终被删除
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except OSError as unlink_err:
                    logger.warning(f"删除临时文件失败 ({temp_path}): {unlink_err}")


# ==================== LLM 服务抽象基类 ====================

class BaseLLMProvider(ABC):
    """LLM 服务抽象基类"""
    
    @abstractmethod
    async def generate_stream(
        self, 
        prompt: str, 
        system_prompt: str,
        on_chunk: Callable[[str], Awaitable[None]]
    ) -> str:
        """流式生成文本响应"""
        pass


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI LLM 服务"""
    
    def __init__(
        self, 
        api_key: str, 
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None
        self._conversation_history = []
        
    async def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        return self._client
    
    def clear_history(self):
        """清空对话历史"""
        self._conversation_history = []
    
    async def generate_stream(
        self, 
        prompt: str, 
        system_prompt: str,
        on_chunk: Callable[[str], Awaitable[None]]
    ) -> str:
        """流式生成 OpenAI 响应"""
        try:
            client = await self._get_client()
            
            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self._conversation_history)
            messages.append({"role": "user", "content": prompt})
            
            # 添加到历史
            self._conversation_history.append({"role": "user", "content": prompt})
            
            full_response = ""
            
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response += text
                    await on_chunk(text)
            
            # 添加助手响应到历史
            self._conversation_history.append({"role": "assistant", "content": full_response})
            
            logger.info(f"💬 LLM: {full_response[:80]}...")
            return full_response
            
        except Exception as e:
            logger.error(f"OpenAI 生成错误: {e}")
            return f"抱歉，我遇到了一些问题: {str(e)}"


class OllamaLLMProvider(BaseLLMProvider):
    """Ollama LLM 服务"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:11434",
        model: str = "llama3:8b",
        temperature: float = 0.7
    ):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self._conversation_history = []
        
    def clear_history(self):
        """清空对话历史"""
        self._conversation_history = []
    
    async def generate_stream(
        self, 
        prompt: str, 
        system_prompt: str,
        on_chunk: Callable[[str], Awaitable[None]]
    ) -> str:
        """流式生成 Ollama 响应"""
        try:
            import aiohttp
            import json
            
            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self._conversation_history)
            messages.append({"role": "user", "content": prompt})
            
            # 添加到历史
            self._conversation_history.append({"role": "user", "content": prompt})
            
            full_response = ""
            
            # 配置超时：连接超时10秒，总超时300秒（5分钟，适合流式响应）
            timeout = aiohttp.ClientTimeout(total=300, connect=10)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "stream": True,
                            "options": {"temperature": self.temperature}
                        }
                    ) as response:
                        async for line in response.content:
                            if line:
                                try:
                                    data = json.loads(line.decode())
                                    if "message" in data and "content" in data["message"]:
                                        text = data["message"]["content"]
                                        full_response += text
                                        await on_chunk(text)
                                except json.JSONDecodeError:
                                    continue
            except asyncio.TimeoutError:
                logger.error(f"Ollama 请求超时 (base_url: {self.base_url})")
                return "抱歉，请求超时，请稍后重试。"
            except aiohttp.ClientError as client_err:
                logger.error(f"Ollama 连接错误: {client_err}")
                return f"抱歉，无法连接到 Ollama 服务: {str(client_err)}"
            
            # 添加助手响应到历史
            self._conversation_history.append({"role": "assistant", "content": full_response})
            
            logger.info(f"💬 LLM: {full_response[:80]}...")
            return full_response
            
        except Exception as e:
            logger.error(f"Ollama 生成错误: {e}")
            return f"抱歉，我遇到了一些问题: {str(e)}"


# ==================== TTS 服务抽象基类 ====================

class BaseTTSProvider(ABC):
    """TTS 服务抽象基类"""
    
    @abstractmethod
    async def synthesize_stream(
        self, 
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> bytes:
        """流式合成语音"""
        pass


class ElevenLabsTTSProvider(BaseTTSProvider):
    """ElevenLabs TTS 服务"""
    
    def __init__(
        self, 
        api_key: str, 
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        model: str = "eleven_monolingual_v1"
    ):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        
    async def synthesize_stream(
        self, 
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> bytes:
        """流式合成 ElevenLabs 语音（PCM16 16kHz 输出）"""
        try:
            import aiohttp
            
            # 请求 PCM16 输出 (16kHz)，避免 MP3 解码
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream?output_format=pcm_16000"
            headers = {
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            data = {
                "text": text,
                "model_id": self.model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            full_audio = b""
            
            # 配置超时：连接超时10秒，总超时60秒
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status == 200:
                            async for chunk in response.content.iter_chunked(4096):
                                # 确保 PCM16 字节对齐（2 bytes/sample）
                                full_audio += chunk
                                await on_audio_chunk(chunk)
                        else:
                            error = await response.text()
                            logger.error(f"ElevenLabs TTS 错误: {error}")
            except asyncio.TimeoutError:
                logger.error(f"ElevenLabs TTS 请求超时 (voice_id: {self.voice_id})")
                return b""
            except aiohttp.ClientError as client_err:
                logger.error(f"ElevenLabs TTS 连接错误: {client_err}")
                return b""
            
            # PCM16 必须 2 字节对齐
            if len(full_audio) % 2 != 0:
                full_audio = full_audio[:-1]

            logger.debug(f"🔊 TTS 完成: {len(full_audio)} bytes (PCM16 16kHz)")
            return full_audio
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS 错误: {e}")
            return b""


class EdgeTTSProvider(BaseTTSProvider):
    """Edge TTS 服务 (免费)"""
    
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice
        
    async def synthesize_stream(
        self, 
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> bytes:
        """流式合成 Edge TTS 语音

        edge_tts 仅支持 MP3 输出，因此收集完整 MP3 数据后解码为 PCM16，
        再分块发送。解码使用 miniaudio 内置解码器（无需 ffmpeg）。
        """
        try:
            import edge_tts
            from .audio_utils import decode_audio_to_pcm16, INTERNAL_SAMPLE_RATE

            text = (text or "").strip()
            if not text:
                logger.info("Edge TTS: 文本为空，跳过合成")
                return b""

            # 可选：通过环境变量配置代理与超时（适合国内网络环境）
            proxy = os.getenv("EDGE_TTS_PROXY") or None
            try:
                connect_timeout = int(os.getenv("EDGE_TTS_CONNECT_TIMEOUT", "10"))
            except ValueError:
                connect_timeout = 10
            try:
                receive_timeout = int(os.getenv("EDGE_TTS_RECEIVE_TIMEOUT", "60"))
            except ValueError:
                receive_timeout = 60

            # 失败时自动回退 voice（常见原因：voice 名不支持 / 服务端无音频返回）
            candidate_voices = [
                self.voice,
                "zh-CN-XiaoxiaoNeural",
                "zh-CN-YunxiNeural",
                "zh-CN-YunjianNeural",
            ]
            seen = set()
            voices_to_try = [v for v in candidate_voices if v and not (v in seen or seen.add(v))]
            
            last_error: Exception | None = None
            for voice in voices_to_try:
                try:
                    communicate = edge_tts.Communicate(
                        text,
                        voice,
                        proxy=proxy,
                        connect_timeout=connect_timeout,
                        receive_timeout=receive_timeout,
                    )

                    # 收集完整 MP3 数据（edge_tts 仅支持 MP3 输出）
                    mp3_buffer = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            mp3_buffer += chunk["data"]

                    if not mp3_buffer:
                        last_error = RuntimeError("No audio was received")
                        logger.warning(f"Edge TTS 无音频返回，尝试切换 voice: {voice}")
                        continue

                    # 解码 MP3 → PCM16 (16kHz mono)
                    pcm_audio = decode_audio_to_pcm16(mp3_buffer, target_rate=INTERNAL_SAMPLE_RATE)
                    if not pcm_audio:
                        last_error = RuntimeError("MP3 decode failed")
                        logger.warning(f"Edge TTS MP3 解码失败 (voice={voice})，尝试下一个")
                        continue

                    # 分块发送 PCM16 数据
                    chunk_size = 4096  # 2048 samples per chunk
                    for i in range(0, len(pcm_audio), chunk_size):
                        await on_audio_chunk(pcm_audio[i:i + chunk_size])

                    logger.debug(f"🔊 TTS 完成 (voice={voice}): MP3 {len(mp3_buffer)} bytes → PCM {len(pcm_audio)} bytes")
                    return pcm_audio

                except Exception as e:
                    last_error = e
                    msg = str(e)
                    # 对可恢复错误尝试下一个 voice
                    if "No audio was received" in msg or "voice" in msg.lower():
                        logger.warning(f"Edge TTS 失败 (voice={voice}): {e}，尝试下一个 voice")
                        continue
                    # 其他错误（网络/协议）也尝试一次回退，但避免刷屏
                    logger.warning(f"Edge TTS 失败 (voice={voice}): {e}")
                    continue

            diagnostic = ""
            if not proxy and last_error and "No audio was received" in str(last_error):
                diagnostic = " 如果未配置代理，请检查 EDGE_TTS_PROXY 配置以排查 'No audio was received' 问题"

            logger.error(f"Edge TTS 错误: {last_error}{diagnostic}")
            return b""
            
        except ImportError:
            raise ImportError("请安装 edge-tts: pip install edge-tts")


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI TTS 服务"""
    
    def __init__(
        self, 
        api_key: str, 
        voice: str = "alloy",
        model: str = "tts-1",
        base_url: str = "https://api.openai.com/v1"
    ):
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.base_url = base_url
        self._client = None
        
    async def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError as err:
                raise ImportError("请安装 openai: pip install openai") from err
        return self._client
    
    async def synthesize_stream(
        self, 
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> bytes:
        """流式合成 OpenAI TTS 语音"""
        client = await self._get_client()

        text = (text or "").strip()
        if not text:
            logger.info("OpenAI TTS: 文本为空，跳过合成")
            return b""
        
        response = await client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
            response_format="pcm"  # 16-bit PCM
        )
        
        full_audio = response.content
        if not full_audio:
            return b""

        # PCM16 必须 2 字节对齐
        if len(full_audio) % 2 != 0:
            full_audio = full_audio[:-1]

        # 统一到内部 16kHz。
        # 重要：如果重采样失败，不能把 24kHz 的音频当作 16kHz 往下游送，否则会造成
        # frame.sample_rate 元数据不一致，影响时长计算、静音检测等逻辑。
        from .audio_utils import resample_audio, SAMPLE_RATE as _CLIENT_SR, INTERNAL_SAMPLE_RATE as _INTERNAL_SR
        try:
            full_audio = resample_audio(full_audio, from_rate=_CLIENT_SR, to_rate=_INTERNAL_SR)
        except Exception as e:
            logger.error(
                "OpenAI TTS: 24kHz->16kHz 重采样失败，为避免 sample_rate 元数据不一致，本次合成将中断: %s",
                e,
            )
            raise
        
        # 分块发送
        chunk_size = 4096
        for i in range(0, len(full_audio), chunk_size):
            chunk = full_audio[i:i+chunk_size]
            await on_audio_chunk(chunk)
        
        logger.debug(f"🔊 TTS 完成: {len(full_audio)} bytes")
        return full_audio


# ==================== 服务工厂 ====================

class ServiceFactory:
    """服务工厂 - 根据配置创建服务实例"""
    
    @staticmethod
    def create_stt_provider(provider: str, **kwargs) -> BaseSTTProvider:
        """创建 STT 服务提供商"""
        providers = {
            "deepgram": lambda: DeepgramSTTProvider(
                api_key=kwargs.get("api_key", os.getenv("DEEPGRAM_API_KEY", "")),
                model=kwargs.get("model", os.getenv("DEEPGRAM_MODEL", "nova-2")),
                language=kwargs.get("language", os.getenv("DEEPGRAM_LANGUAGE", "zh-CN"))
            ),
            "openai_whisper": lambda: OpenAIWhisperSTTProvider(
                api_key=kwargs.get("api_key", ""),
                base_url=kwargs.get("base_url", "https://api.openai.com/v1")
            ),
            "local_whisper": lambda: LocalWhisperSTTProvider(
                model=kwargs.get("model", os.getenv("WHISPER_MODEL", "base"))
            )
        }
        
        if provider not in providers:
            raise ValueError(f"未知的 STT 服务提供商: {provider}. 可选: {list(providers.keys())}")
        
        logger.info(f"创建 STT 服务: {provider}")
        return providers[provider]()
    
    @staticmethod
    def create_llm_provider(**kwargs) -> BaseLLMProvider:
        """创建 LLM 服务提供商（统一 OpenAI 兼容格式）

        Kwargs:
            api_key:     API 密钥
            model:       模型 ID
            base_url:    API Base URL
            temperature: 生成温度
            max_tokens:  最大 token 数
        """
        provider = OpenAILLMProvider(
            api_key=kwargs.get("api_key", os.getenv("LLM_API_KEY", "")),
            model=kwargs.get("model", os.getenv("LLM_MODEL_ID", "gpt-4o")),
            base_url=kwargs.get("base_url", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")),
            temperature=float(kwargs.get("temperature", os.getenv("LLM_TEMPERATURE", "0.7"))),
            max_tokens=int(kwargs.get("max_tokens", os.getenv("LLM_MAX_TOKENS", "4096")))
        )
        logger.info("创建 LLM 服务: OpenAI 兼容 (base_url=%s, model=%s)", provider.base_url, provider.model)
        return provider
    
    @staticmethod
    def create_tts_provider(provider: str, **kwargs) -> BaseTTSProvider:
        """创建 TTS 服务提供商"""
        providers = {
            "elevenlabs": lambda: ElevenLabsTTSProvider(
                api_key=kwargs.get("api_key", os.getenv("ELEVENLABS_API_KEY", "")),
                voice_id=kwargs.get("voice_id", os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")),
                model=kwargs.get("model", os.getenv("ELEVENLABS_MODEL", "eleven_monolingual_v1"))
            ),
            "edge_tts": lambda: EdgeTTSProvider(
                voice=kwargs.get("voice", os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural"))
            ),
            "openai_tts": lambda: OpenAITTSProvider(
                api_key=kwargs.get("api_key", ""),
                voice=kwargs.get("voice", os.getenv("TTS_VOICE", "alloy")),
                model=kwargs.get("model", os.getenv("TTS_MODEL_ID", "tts-1")),
                base_url=kwargs.get("base_url", "https://api.openai.com/v1")
            )
        }
        
        if provider not in providers:
            raise ValueError(f"未知的 TTS 服务提供商: {provider}. 可选: {list(providers.keys())}")
        
        logger.info(f"创建 TTS 服务: {provider}")
        return providers[provider]()
