# OpenAI Realtime API 兼容服务器

中文 | [English](README.en.md)

一个完全复刻 OpenAI Realtime API 协议的本地 WebSocket 服务器，允许你使用本地或第三方模型替代 OpenAI。

## ✨ 特性

- 🔄 **完全兼容**：对外复刻 OpenAI Realtime API 的协议（URL、JSON 事件格式、音频编码）
- 🔌 **统一 OpenAI 兼容格式**：LLM 配置采用统一的 OpenAI 兼容接口格式，仅需 4 项配置即可接入任意服务商
- 🚀 **零客户端修改**：你的客户端应用只需修改 `baseUrl` 即可连接
- 🎤 **内置 Server VAD**：集成 Pipecat 的 Silero VAD，默认启用自由麦模式，自动检测语音活动
- 💻 **浏览器 WebUI**：内置浏览器语音交互界面，支持语音/文字双模式交互式输入
- 📝 **Markdown 实时渲染**：AI 回复支持 Markdown 实时预览，代码高亮、一键复制、原文/渲染切换
- ⚙️ **浏览器配置管理**：内置 Settings 页面，可直接在浏览器中编辑 .env 配置
- 🌟 **支持硅基流动**：国内访问快，价格低廉（约为 OpenAI 的 1/10），详见 [SILICONFLOW.md](SILICONFLOW.md)

## 📁 项目结构

```
├── main.py                 # FastAPI 主服务器（含 WebUI 静态文件服务）
├── config.py               # 配置管理（支持 .env）
├── logger_config.py        # 日志配置模块
├── service_providers.py    # STT/LLM/TTS 服务提供商
├── protocol.py             # OpenAI Realtime API 协议定义
├── transport.py            # WebSocket Transport 层（协议翻译官）
├── pipeline_manager.py     # Pipecat 管道管理器
├── realtime_session.py     # 会话生命周期管理
├── audio_utils.py          # 音频处理工具（重采样等）
├── static/                 # 浏览器 WebUI 静态文件
│   ├── index.html          # WebUI 主页面（语音对话 + Markdown 渲染）
│   ├── settings.html       # 配置管理页面（在线编辑 .env）
│   └── audio-worklet.js    # Web Audio 音频处理器
├── push_to_talk_app.py     # WebUI 启动器（启动服务+打开浏览器）
├── test_client.py          # 简单测试客户端
├── tests/
│   └── test_config.py      # 配置模块单元测试（29 条）
├── pyproject.toml          # 项目配置与依赖定义
├── requirements.txt        # pip 依赖列表（兼容退路）
└── .python-version         # Python 版本约束 (3.10)
```

## 🚀 快速开始

### 1. 安装依赖

> 本项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖和虚拟环境。
>
> 安装 uv：
> - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
> - Linux/Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
# 克隆项目后，一键创建虚拟环境并安装所有依赖
uv sync

# 如需使用本地 Whisper STT
uv sync --extra whisper
```

<details>
<summary>📌 不使用 uv 的替代方案</summary>

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```
</details>

### 2. 配置服务（重要！）

```bash
# 复制配置文件模板
cp .env.example .env

# 编辑 .env 文件，配置你的服务
# Windows:
notepad .env
# Linux/Mac:
nano .env
```

**推荐配置**（国内用户）：
```bash
# LLM 配置（统一 OpenAI 兼容格式，仅需 4 项）
LLM_MODEL_NAME=SiliconFlow
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL_ID=deepseek-ai/DeepSeek-V3
LLM_API_KEY=你的_api_key

# 使用 Edge TTS（完全免费）
TTS_PROVIDER=edge_tts
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

> 💡 也可以启动服务器后访问 `http://localhost:8000/settings` 在浏览器中直接编辑配置。

详细配置说明请查看：
- [QUICKSTART.md](QUICKSTART.md) - 快速入门指南
- [SILICONFLOW.md](SILICONFLOW.md) - 硅基流动配置指南
- [.env.example](.env.example) - 完整配置模板

### 3. 启动服务器

```bash
# 开发模式（自动重载）
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 或直接运行
uv run python main.py
```

服务器启动后会显示当前配置：
```
==================================================
当前服务配置:
==================================================
LLM 服务: SiliconFlow
  - 接口: https://api.siliconflow.cn/v1
  - 模型: deepseek-ai/DeepSeek-V3
STT 服务: deepgram
TTS 服务: edge_tts
==================================================
```

### 4. 运行客户端测试

#### 方式 1: 浏览器 WebUI（推荐）

服务器启动后内置浏览器 WebUI，无需安装任何额外依赖：

```bash
# 方法 A: 直接在浏览器中打开
http://localhost:8000

# 方法 B: 使用启动器（自动启动服务器+打开浏览器）
uv run python push_to_talk_app.py
```

**使用说明：**
- 点击麦克风按钮开始/停止语音采集
- Server VAD 自动检测语音开始和结束
- 也可以在文本框中输入文字消息
- 网页自动连接 WebSocket，断线自动重连
- 支持打断：说话时自动停止 AI 音频播放

**功能特性：**
- ✅ 浏览器内麦克风采集 (Web Audio API + AudioWorklet)
- ✅ 实时 AI 音频播放
- ✅ 实时显示 AI 响应文本（流式）
- ✅ **Markdown 实时渲染**（标题、列表、代码块、表格、链接、图片等）
- ✅ 代码块语法高亮 + 一键复制
- ✅ 消息原文/渲染切换（全局 + 单条）
- ✅ 自动语音活动检测 (VAD) 状态指示
- ✅ 交互式输入栏（语音/文字 50/50 自动展开动画）
- ✅ 连接状态显示 + 自动重连
- ✅ 响应式暗色主题 UI
- ✅ 内置配置管理页面 (`/settings`)

#### 方式 2: 简单测试客户端

```bash
# 自动测试模式
uv run python test_client.py

# 交互模式
uv run python test_client.py -i
```

#### 方式 3: 使用 OpenAI SDK

在你的客户端代码中：

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy-key"  # 本地服务器不需要真实 key
)

async with client.realtime.connect(model="gpt-realtime") as conn:
    # 你的代码...
```

## 🔧 架构设计

### 数据流向

```
客户端 → OpenAI 格式 JSON → Transport (翻译) → Pipecat Pipeline
                                                    ↓
客户端 ← OpenAI 格式 JSON ← Transport (翻译) ← (VAD→STT→LLM→TTS)
```

### 核心组件

1. **Transport 层** (`transport.py`)
   - 接收 OpenAI 格式的客户端事件
   - 转换为 Pipecat 内部帧格式
   - 将输出转换回 OpenAI 格式

2. **Pipeline 管理器** (`pipeline_manager.py`)
   - VAD：语音活动检测
   - STT：语音转文字
   - LLM：语言模型推理
   - TTS：文字转语音

3. **会话管理** (`realtime_session.py`)
   - 管理 WebSocket 会话生命周期
   - 协调 Transport 和 Pipeline

4. **音频处理** (`audio_utils.py`)
   - 音频重采样（24kHz ↔ 16kHz）
   - 音频缓冲区管理

## 📋 支持的事件

### 客户端 → 服务器

| 事件类型 | 描述 |
|---------|------|
| `session.update` | 更新会话配置（VAD 参数、指令等） |
| `input_audio_buffer.append` | 追加音频数据（Server VAD 自动处理） |
| `input_audio_buffer.commit` | 手动提交音频缓冲区（手动 VAD 模式） |
| `input_audio_buffer.clear` | 清空音频缓冲区 |
| `conversation.item.create` | 创建对话项（支持文本注入 LLM 上下文） |
| `response.create` | 请求生成响应 |
| `response.cancel` | 取消当前响应 |

### 服务器 → 客户端

| 事件类型 | 描述 |
|---------|------|
| `session.created` | 会话已创建 |
| `session.updated` | 会话已更新 |
| `input_audio_buffer.speech_started` | 检测到语音开始 |
| `input_audio_buffer.speech_stopped` | 检测到语音停止 |
| `input_audio_buffer.committed` | 音频缓冲区已提交 |
| `conversation.item.input_audio_transcription.completed` | 输入音频转录完成 |
| `response.created` | 响应已创建 |
| `response.audio.delta` | 音频增量 |
| `response.audio_transcript.delta` | 转录增量 |
| `response.done` | 响应完成 |

## ⚙️ 配置说明

所有配置都通过 `.env` 文件管理，支持以下配置项：

### 基础配置
```bash
# 服务器配置
DEBUG=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### LLM 配置（统一 OpenAI 兼容格式）

所有 LLM 均通过 OpenAI 兼容接口调用，只需填写以下四项：

```bash
LLM_MODEL_NAME=SiliconFlow        # 服务商名称（仅用于日志显示）
LLM_BASE_URL=https://api.siliconflow.cn/v1  # API 服务地址
LLM_MODEL_ID=deepseek-ai/DeepSeek-V3        # 模型 ID
LLM_API_KEY=your_api_key_here               # API 密钥
```

支持的预设：

| 服务商 | LLM_BASE_URL | 示例模型 |
|---------|-------------|----------|
| **硅基流动** 🌟 | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Ollama | `http://localhost:11434/v1` | `llama3:8b` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |

### STT 配置
```bash
STT_PROVIDER=deepgram  # 或 openai_whisper, local_whisper
DEEPGRAM_API_KEY=你的_api_key
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=zh-CN
```

### TTS 配置
```bash
TTS_PROVIDER=edge_tts  # 或 openai_tts, elevenlabs
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

### VAD 配置（自由麦模式）
```bash
VAD_THRESHOLD=0.5  # 灵敏度 (0.0-1.0)，越高越不敏感
VAD_SILENCE_DURATION_MS=500  # 静音检测时长（毫秒）
VAD_PREFIX_PADDING_MS=300  # 语音前缀填充（毫秒）
```

完整配置选项请查看 [.env.example](.env.example)

> 💡 **在线配置**: 启动服务器后访问 `http://localhost:8000/settings` 可在浏览器中直接编辑所有配置项。

**注意**: 自由麦模式使用 Silero VAD 做语音活动检测；运行时会直接 `import torch`，因此需要安装 PyTorch (`torch`)。

## 🎯 支持的服务

### STT（语音转文字）
| 服务 | 配置值 | 说明 | API Key |
|------|--------|------|--------|
| **Deepgram** 🌟 | `deepgram` | 高质量，每月 200 分钟免费 | 需要 |
| OpenAI Whisper | `openai_whisper` | OpenAI 官方 API | 需要 |
| 本地 Whisper | `local_whisper` | 完全免费，需下载模型 | 不需要 |

### LLM（语言模型）

> LLM 采用统一 OpenAI 兼容格式，任何支持 OpenAI API 格式的服务商均可接入。

| 服务 | LLM_BASE_URL | 说明 | API Key |
|------|-------------|------|--------|
| **硅基流动** 🌟 | `https://api.siliconflow.cn/v1` | 国内访问快，价格约 OpenAI 1/10 | 需要 |
| OpenAI | `https://api.openai.com/v1` | GPT-4o 等模型 | 需要 |
| DeepSeek | `https://api.deepseek.com/v1` | DeepSeek 官方 API | 需要 |
| Ollama | `http://localhost:11434/v1` | 本地运行，完全免费 | 不需要 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云 DashScope | 需要 |

### TTS（文字转语音）
| 服务 | 配置值 | 说明 | API Key |
|------|--------|------|--------|
| **Edge TTS** 🌟 | `edge_tts` | 微软 Edge 浏览器 TTS，完全免费 | 不需要 |
| ElevenLabs | `elevenlabs` | 高质量语音，每月 10000 字符免费 | 需要 |
| OpenAI TTS | `openai_tts` | OpenAI 官方 TTS | 需要 |

🌟 = 推荐选项

### 推荐组合

**最佳性价比**（推荐）：
```bash
STT: Deepgram（每月 200 分钟免费）
LLM: 硅基流动 (DeepSeek-V3)（¥0.35/M tokens）
TTS: Edge TTS（完全免费）
成本: 约 ¥0.05/分钟对话
```

**完全免费**：
```bash
STT: 本地 Whisper
LLM: Ollama (http://localhost:11434/v1)
TTS: Edge TTS
成本: ¥0（需要本地计算资源）
```

**高质量**：
```bash
STT: Deepgram
LLM: OpenAI GPT-4o (https://api.openai.com/v1)
TTS: ElevenLabs
成本: 较高，适合商业应用
```

## ⚠️ 注意事项

### 音频采样率
- OpenAI 协议使用 **24kHz**
- 大多数 STT 模型使用 **16kHz**
- `audio_utils.py` 自动处理重采样

### 内置 Server VAD（自由麦模式）

服务器内置了 Pipecat 的 Silero VAD，默认启用 `server_vad` 模式，自动检测用户的语音活动：

**工作流程：**
1. 客户端连续发送音频数据（`input_audio_buffer.append`）
2. VAD 自动检测到用户开始说话 → 发送 `input_audio_buffer.speech_started` 事件
3. VAD 检测到用户停止说话 → 发送 `input_audio_buffer.speech_stopped` 事件
4. 服务器自动触发 STT → LLM → TTS 流程
5. 客户端收到 AI 响应的音频和文本

**打断功能：**
- 客户端收到 `speech_started` 事件后应立即停止播放 AI 音频
- 实现自然的对话打断体验

**VAD 参数调优：**
可以通过 `session.update` 事件调整 VAD 参数：
- `threshold`: 灵敏度阈值 (0.0-1.0)
- `silence_duration_ms`: 静音检测时长
- `prefix_padding_ms`: 语音前缀填充

### JSON 格式严格性
`response_id` 和 `item_id` 字段必须存在，使用随机 UUID 填充。

### 客户端音频设备
WebUI 通过浏览器的 Web Audio API 采集和播放音频，需要：
- 现代浏览器（Chrome / Firefox / Edge / Safari）
- 允许麦克风权限（首次使用时浏览器会弹出提示）
- HTTPS 或 localhost 访问（浏览器安全策略要求）

## 🎬 快速演示

### 1. 启动服务器（终端 1）
```bash
uv run python main.py
```
输出：
```
OpenAI Realtime API 兼容服务器启动
WebSocket 端点: ws://localhost:8000/v1/realtime
```

### 2. 启动客户端（浏览器）
```bash
# 直接在浏览器中打开 http://localhost:8000
# 或使用启动器（自动启动服务+打开浏览器）
uv run python push_to_talk_app.py
```

### 3. 开始对话

1. 点击麦克风按钮开始监听
2. 直接对着麦克风说话（例如：“你好，今天天气怎么样？”）
3. Server VAD 自动检测你的语音开始和结束
4. 等待 AI 响应（文本会流式显示，音频会自动播放）
5. 可以随时打断 AI 的回答，继续说话
6. 也可以在文本框中输入文字消息

## 🔄 替换为本地/第三方模型

本项目 LLM 采用统一 OpenAI 兼容格式，任何支持 OpenAI API 格式的服务商均可接入。STT 和 TTS 通过 `.env` 中的 `STT_PROVIDER` / `TTS_PROVIDER` 切换。

### 快速配置

1. 复制环境变量示例文件（首次启动时会自动创建）：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，或访问 `http://localhost:8000/settings` 在浏览器中配置：

### STT 服务配置

| 服务提供商 | 说明 | 需要 API Key |
|-----------|------|-------------|
| `deepgram` 🌟 | Deepgram Nova-2，高准确率 | ✅ |
| `openai_whisper` | OpenAI Whisper API | ✅ |
| `local_whisper` | 本地 Whisper 模型 | ❌ |

### LLM 服务配置（统一 OpenAI 兼容格式）

只需 4 项配置即可接入任意服务商：

| 服务提供商 | LLM_BASE_URL | 示例模型 | API Key |
|-----------|-------------|---------|---------|
| **硅基流动** 🌟 | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3` | ✅ |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` | ✅ |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | ✅ |
| Ollama | `http://localhost:11434/v1` | `llama3:8b` | ❌ |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` | ✅ |

```bash
# 硅基流动 (推荐)
LLM_MODEL_NAME=SiliconFlow
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL_ID=deepseek-ai/DeepSeek-V3
LLM_API_KEY=your_key_here

# 或 Ollama (本地，免费)
# LLM_MODEL_NAME=Ollama
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_MODEL_ID=llama3:8b
# LLM_API_KEY=ollama
```

### TTS 服务配置

| 服务提供商 | 说明 | 需要 API Key |
|-----------|------|-------------|
| `edge_tts` 🌟 | Microsoft Edge TTS（免费） | ❌ |
| `openai_tts` | OpenAI TTS | ✅ |
| `elevenlabs` | ElevenLabs 高质量语音 | ✅ |

### 完整 .env 示例

```bash
# ==================== 服务器配置 ====================
DEBUG=true
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# ==================== LLM 配置 (统一 OpenAI 兼容格式) ====================
LLM_MODEL_NAME=SiliconFlow
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL_ID=deepseek-ai/DeepSeek-V3
LLM_API_KEY=your_api_key_here
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
LLM_SYSTEM_PROMPT=你是一个有帮助的AI助手。

# ==================== STT 配置 ====================
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your_deepgram_api_key
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=zh-CN

# ==================== TTS 配置 ====================
TTS_PROVIDER=edge_tts
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural

# ==================== VAD 配置 ====================
VAD_THRESHOLD=0.5
VAD_SILENCE_DURATION_MS=500
VAD_PREFIX_PADDING_MS=300
```

### 免费方案（无需 API Key）

如果你没有 API Key，可以使用以下完全免费的配置：

```bash
# 本地 Whisper (需要安装 openai-whisper)
STT_PROVIDER=local_whisper
WHISPER_MODEL=base

# Ollama (需要安装并运行 Ollama 服务)
LLM_MODEL_NAME=Ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_ID=llama3:8b
LLM_API_KEY=ollama

# Edge TTS (免费)
TTS_PROVIDER=edge_tts
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

安装本地模型：
```bash
# 安装本地 Whisper
uv sync --extra whisper

# 安装 Ollama (访问 https://ollama.ai)
# 然后下载模型
ollama pull llama3:8b
```

## 🐛 故障排除

### 客户端无法连接
```bash
# 检查服务器是否运行
curl http://localhost:8000/health

# 应返回: {"status":"healthy","active_sessions":0}
```

如果返回 404，通常表示你连到了其他服务（例如 ComfyUI），而不是本项目网关。
请确认服务端口，或设置 `LOCAL_SERVER_URL`（或 `REALTIME_WS_URL`）为正确的 WebSocket 地址。

### 音频设备问题
WebUI 使用浏览器 Web Audio API，如遇问题：
- 确保使用 HTTPS 或 localhost 访问（浏览器安全策略要求）
- 检查浏览器是否已授予麦克风权限
- 尝试使用 Chrome 或 Edge 浏览器（对 AudioWorklet 支持最好）

### 模块导入错误
```bash
# 重新同步依赖
uv sync

# 或使用 pip
pip install --upgrade -r requirements.txt
```

### WebSocket 连接断开
- 检查防火墙设置
- 确保端口 8000 未被占用
- 查看服务器日志以获取详细错误信息

## 📊 性能优化

### 音频重采样
- 安装 `soxr` 以获得更高质量的重采样：
```bash
uv add soxr
```

### 减少延迟
- 调整 `config.py` 中的 VAD 参数
- 使用更快的本地模型
- 减小音频缓冲区大小

## 🔜 后续计划

- [x] 完整的协议实现
- [x] 浏览器 WebUI 语音交互界面
- [x] 音频处理和重采样
- [x] 内置 Server VAD (Silero VAD)，纯自由麦模式
- [x] 集成真实的 STT 服务（Deepgram/Whisper/本地 Whisper）
- [x] 集成真实的 LLM 服务（OpenAI/Ollama）
- [x] 集成真实的 TTS 服务（ElevenLabs/Edge TTS/OpenAI TTS）
- [x] 支持 .env 环境变量配置
- [x] 统一 OpenAI 兼容 LLM 配置格式（支持硅基流动/OpenAI/DeepSeek/Ollama/通义千问等）
- [x] 浏览器内 Settings 配置管理页面
- [x] Markdown 实时渲染（代码高亮、表格、一键复制、XSS 防护）
- [x] 交互式语音/文字输入栏（动态展开动画）
- [x] 配置模块单元测试（29 条）
- [ ] 支持函数调用
- [ ] 支持多模态输入
- [ ] Docker 部署支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发指南
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

MIT License
