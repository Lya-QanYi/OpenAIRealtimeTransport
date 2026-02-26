# OpenAI Realtime API Compatible Server

[中文](README.md) | English

A local WebSocket server that mirrors the OpenAI Realtime API protocol, so you can swap OpenAI with local or third‑party model providers while keeping the client mostly unchanged.

## ✨ Features

- 🔄 **Protocol-compatible**: Mirrors OpenAI Realtime API style (URL, JSON events, audio encoding)
- 🔌 **Pluggable backends**: Uses an internal pipeline to connect STT/LLM/TTS providers (Deepgram, Ollama/Llama, ElevenLabs, SiliconFlow, etc.)
- 🚀 **Minimal client changes**: Usually only change `baseUrl` to point to this server
- 🎤 **Built-in Server VAD**: Integrates VAD (Silero when available) for hands-free “open mic” mode
- � **Browser WebUI**: Built-in browser voice interaction interface, no extra client installation needed
- 🌟 **SiliconFlow supported**: Faster & cheaper in mainland China; see [SILICONFLOW.md](SILICONFLOW.md)

## 📁 Project Structure

```
├── main.py                 # FastAPI server entry (serves WebUI static files)
├── config.py               # Config management (.env supported)
├── logger_config.py        # Logging configuration module
├── service_providers.py    # STT/LLM/TTS provider implementations
├── protocol.py             # OpenAI Realtime API protocol definitions
├── transport.py            # WebSocket Transport layer (protocol translator)
├── pipeline_manager.py     # Pipeline manager
├── realtime_session.py     # Session lifecycle manager
├── audio_utils.py          # Audio utilities (resampling, etc.)
├── static/                 # Browser WebUI static files
│   ├── index.html          # WebUI main page
│   └── audio-worklet.js    # Web Audio processors
├── push_to_talk_app.py     # WebUI launcher (starts server + opens browser)
├── test_client.py          # Simple test client
├── pyproject.toml          # Project config & dependency definitions
├── requirements.txt        # pip dependency list (fallback)
└── .python-version         # Python version constraint (3.10)
```

## 🚀 Quick Start

### 1) Install dependencies

> This project uses [uv](https://docs.astral.sh/uv/) to manage dependencies and virtual environments.
>
> Install uv:
> - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
> - Linux/Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`

```bash
# Create venv and install all dependencies in one step
uv sync

# Include local Whisper STT
uv sync --extra whisper
```

<details>
<summary>📌 Without uv (pip fallback)</summary>

```bash
python -m venv .venv

# Activate venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```
</details>

### 2) Configure services (important)

Copy and edit environment configuration:

```bash
cp .env.example .env
```

Recommended for users in mainland China (example):

```bash
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2

TTS_PROVIDER=edge_tts
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural
```

More docs:
- [QUICKSTART.md](QUICKSTART.md) (Chinese) – practical recipes
- [SILICONFLOW.md](SILICONFLOW.md) (Chinese) – SiliconFlow setup
- [.env.example](.env.example) – full config template

### 3) Start the server

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# or
uv run python main.py
```

### 4) Run a client

#### Option A: Browser WebUI (recommended)

The server includes a built-in WebUI. After starting the server, open your browser:

```bash
# Open in browser
http://localhost:8000

# Or use the launcher (starts server + opens browser automatically)
uv run python push_to_talk_app.py
```

Notes:
- Click the microphone button to start/stop voice capture
- Server VAD detects speech automatically
- You can also type text messages
- Auto-reconnects on disconnect
- Supports speech interruption (speaking stops AI audio playback)

#### Option B: Simple test client

```bash
uv run python test_client.py
uv run python test_client.py -i
```

#### Option C: Use OpenAI SDK (pointing to this server)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy-key"  # no real key needed for local server
)

async with client.realtime.connect(model="gpt-realtime") as conn:
    ...
```

## 🔧 Architecture

### Data flow

```
Client → OpenAI-style JSON → Transport (translate) → Pipeline
                                            ↓
Client ← OpenAI-style JSON ← Transport (translate) ← (VAD → STT → LLM → TTS)
```

### Key components

1. **Transport** ([transport.py](transport.py))
   - Converts OpenAI-style events to internal frames and back

2. **Pipeline Manager** ([pipeline_manager.py](pipeline_manager.py))
   - VAD / STT / LLM / TTS orchestration

3. **Session Manager** ([realtime_session.py](realtime_session.py))
   - WebSocket session lifecycle; connects Transport ↔ Pipeline

4. **Audio Utilities** ([audio_utils.py](audio_utils.py))
   - Audio resampling (24kHz ↔ 16kHz)
   - Audio buffer management

## 📊 Supported Services

### STT (Speech-to-Text)
| Provider | Config Value | Notes | API Key |
|----------|--------------|-------|---------|
| **Deepgram** 🌟 | `deepgram` | High quality, 200 min/month free | Required |
| OpenAI Whisper | `openai_whisper` | OpenAI official API | Required |
| Local Whisper | `local_whisper` | Completely free, needs model download | Not required |

### LLM (Language Model)
| Provider | Config Value | Notes | API Key |
|----------|--------------|-------|---------|
| **SiliconFlow** 🌟 | `siliconflow` | Fast in China, ~1/10 OpenAI price | Required |
| OpenAI | `openai` | GPT-4o and other models | Required |
| Ollama | `ollama` | Local, completely free | Not required |

### TTS (Text-to-Speech)
| Provider | Config Value | Notes | API Key |
|----------|--------------|-------|---------|
| **Edge TTS** 🌟 | `edge_tts` | Microsoft Edge TTS, free | Not required |
| ElevenLabs | `elevenlabs` | High quality, 10k chars/month free | Required |
| OpenAI TTS | `openai_tts` | OpenAI official TTS | Required |

🌟 = Recommended

## 📝 Configuration

All configuration is done via `.env` file. See [.env.example](.env.example) for the complete template.

### VAD Configuration (Open-mic mode)
```bash
VAD_THRESHOLD=0.5          # Sensitivity (0.0-1.0), higher = less sensitive
VAD_SILENCE_DURATION_MS=500  # Silence detection duration (ms)
VAD_PREFIX_PADDING_MS=300    # Speech prefix padding (ms)
```

## 📄 License

See [LICENSE](LICENSE).
