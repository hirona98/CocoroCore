# AIAvatarKit Library Specification

## Overview

AIAvatarKit is a Python library for building AI-based conversational avatars with multimodal input/output support. It provides a modular Speech-to-Speech (STS) framework that can serve as the backend for various conversational AI systems.

**Version**: 0.7.2  
**License**: Apache v2  
**Repository**: https://github.com/uezo/aiavatar

## Architecture

### Core Components

```
AIAvatarKit
├── STS Pipeline (Speech-to-Speech)
│   ├── VAD (Voice Activity Detection)
│   ├── STT (Speech-to-Text)
│   ├── LLM (Large Language Model)
│   └── TTS (Text-to-Speech)
├── Adapters
│   ├── Local Client
│   ├── HTTP Server/Client
│   └── WebSocket Server/Client
├── Controllers
│   ├── Face Controller
│   └── Animation Controller
└── Device Management
    ├── Audio Device
    └── Video Device
```

### Component Flow

```
Audio Input → VAD → STT → LLM → TTS → Audio Output
                            ↓
                    Avatar Control
                    (Face/Animation)
```

## Installation

```bash
pip install aiavatar
```

### Dependencies

- Python 3.10+
- httpx>=0.27.0
- openai>=1.55.3
- aiofiles>=24.1.0
- numpy>=2.2.3
- PyAudio>=0.2.14

## Core Classes

### AIAvatar

Main entry point for local avatar applications.

```python
class AIAvatar(AIAvatarClientBase):
    def __init__(
        self,
        # STS Pipeline components
        sts: STSPipeline = None,
        vad: SpeechDetector = None,
        stt: SpeechRecognizer = None,
        llm: LLMService = None,
        tts: SpeechSynthesizer = None,
        
        # Default component parameters
        volume_db_threshold: float = -50.0,
        silence_duration_threshold: float = 0.5,
        openai_api_key: str = None,
        openai_model: str = "gpt-4o-mini",
        system_prompt: str = None,
        voicevox_url: str = "http://127.0.0.1:50021",
        voicevox_speaker: int = 46,
        
        # Wakeword settings
        wakewords: List[str] = None,
        wakeword_timeout: float = 60.0,
        
        # Audio settings
        input_device_index: int = -1,
        output_device_index: int = -1,
        
        # Other settings
        debug: bool = False
    )
```

### STSPipeline

Core pipeline managing the speech-to-speech flow.

```python
class STSPipeline:
    def __init__(self, ...):
        # Component initialization
        
    async def invoke(self, request: STSRequest) -> AsyncGenerator[STSResponse, None]:
        # Main processing pipeline
        
    @property
    def on_before_llm(self):
        # Hook before LLM processing
        
    @property
    def on_before_tts(self):
        # Hook before TTS processing
        
    @property
    def on_finish(self):
        # Hook after completion
```

### Data Models

#### STSRequest

```python
class STSRequest:
    type: str  # "start", "chunk", "final"
    session_id: str
    user_id: str
    context_id: str
    text: str
    audio_data: bytes
    files: List[Dict[str, str]]
    system_prompt_params: Dict[str, any]
```

#### STSResponse

```python
class STSResponse:
    type: str  # "start", "chunk", "final", "error", "tool_call"
    session_id: str
    user_id: str
    context_id: str
    text: str
    voice_text: str
    audio_data: bytes
    tool_call: ToolCall
    metadata: Dict[str, any]
```

#### AIAvatarResponse

```python
class AIAvatarResponse:
    type: str
    session_id: str
    user_id: str
    context_id: str
    text: str
    voice_text: str
    avatar_control_request: AvatarControlRequest
    audio_data: bytes
    metadata: Dict[str, any]
```

## Component Interfaces

### SpeechDetector (VAD)

```python
class SpeechDetector(ABC):
    @abstractmethod
    async def process_samples(self, samples: bytes, session_id: str):
        pass
    
    @property
    def on_speech_detected(self):
        # Callback when speech is detected
```

### SpeechRecognizer (STT)

```python
class SpeechRecognizer(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        pass
```

### LLMService

```python
class LLMService(ABC):
    @abstractmethod
    async def chat_stream(
        self,
        context_id: str,
        user_id: str,
        text: str,
        files: List[Dict[str, str]] = None,
        system_prompt_params: Dict[str, any] = None
    ) -> AsyncGenerator[LLMResponse, None]:
        pass
```

### SpeechSynthesizer (TTS)

```python
class SpeechSynthesizer(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        style_info: Dict[str, any] = None,
        language: str = None
    ) -> bytes:
        pass
```

## Supported Services

### Speech-to-Text (STT)
- OpenAI Whisper
- Google Cloud Speech-to-Text
- Azure Cognitive Services Speech

### Large Language Models (LLM)
- OpenAI ChatGPT (GPT-4, GPT-4o, etc.)
- Anthropic Claude
- Google Gemini
- Dify Platform
- LiteLLM (supports 100+ models)

### Text-to-Speech (TTS)
- VOICEVOX
- AivisSpeech
- OpenAI TTS
- Azure Cognitive Services Speech
- Google Cloud Text-to-Speech
- SpeechGateway (Style-Bert-VITS2, NijiVoice)

## Adapter Types

### Local Adapter
Direct interaction with local audio devices.

### HTTP Adapter
RESTful API with Server-Sent Events (SSE) for streaming.

**Endpoints**:
- `POST /chat` - Send message and receive streaming response
- `POST /listener/start` - Start listening
- `POST /listener/stop` - Stop listening
- `GET /listener/status` - Get listener status
- `POST /avatar/face` - Set face expression
- `POST /avatar/animation` - Set animation

### WebSocket Adapter
Real-time bidirectional communication.

**Message Types**:
- `start` - Initialize session
- `chunk` - Stream audio/text chunks
- `final` - Complete response
- `error` - Error notification

## Avatar Control

### Face Expression Control

```python
# Define face expressions
face_controller.faces = {
    "neutral": "🙂",
    "joy": "😀",
    "angry": "😠",
    "sorrow": "😞",
    "fun": "🥳"
}

# Use in prompts with [face:expression] tags
"[face:joy]Hello! [face:fun]Let's have fun!"
```

### Animation Control

```python
# Use in prompts with [animation:name] tags
"[animation:wave]Hello there!"
```

## Tool System

### Standard Tools

```python
@aiavatar_app.sts.llm.tool(tool_spec)
async def my_tool(param1: str, param2: int):
    # Tool implementation
    return result
```

### Dynamic Tools

```python
# Register dynamic tool
llm.add_tool(
    Tool(
        name="get_weather",
        spec=weather_spec,
        func=get_weather,
        instruction="Weather retrieval instructions",
        is_dynamic=True
    )
)

# Enable dynamic tools
llm.use_dynamic_tools = True
```

### Tool with Progress

```python
@llm.tool(spec)
async def long_running_tool(param: str):
    yield {"message": "Starting..."}, False
    # ... processing ...
    yield {"message": "Processing..."}, False
    # ... more processing ...
    yield {"result": "Complete"}, True  # Final result
```

## Performance Monitoring

### PerformanceRecord

Tracks metrics for each request:
- `transaction_id`
- `user_id`
- `request_text`
- `response_text`
- `stt_time`
- `llm_time`
- `llm_first_chunk_time`
- `tts_time`
- `tts_first_chunk_time`
- `total_time`

### PerformanceRecorder

```python
class PerformanceRecorder(ABC):
    @abstractmethod
    def record(self, performance: PerformanceRecord):
        pass
```

## Context Management

### ContextManager

```python
class ContextManager(ABC):
    @abstractmethod
    async def get_histories(self, context_id: str) -> List[Dict]:
        pass
    
    @abstractmethod
    async def save_histories(self, context_id: str, messages: List[Dict]):
        pass
```

## Voice Recording

### VoiceRecorder

```python
class VoiceRecorder(ABC):
    @abstractmethod
    async def record(self, voice: Union[RequestVoice, ResponseVoices]):
        pass
```

## Platform Integrations

### VRChat Integration

```python
from aiavatar.face.vrchat import VRChatFaceController

vrc_face_controller = VRChatFaceController(
    faces={
        "neutral": 0,
        "joy": 1,
        "angry": 2,
        # ...
    }
)
```

## Error Handling

### AIAvatarException

```python
class AIAvatarException(Exception):
    def __init__(self, message: str, response: STSResponse = None):
        self.message = message
        self.response = response
```

## Threading Model

AIAvatarKit uses asyncio for concurrent operations:
- Audio recording/playback runs in separate threads
- All processing is async/await based
- Supports cancellation of ongoing operations

## Security Considerations

### API Key Management
- Store API keys in environment variables
- Never commit API keys to version control

### HTTP API Protection
```python
AIAvatarHttpServer(api_key="YOUR_SECRET_KEY")
```

### Input Validation
- All user inputs are validated
- File uploads are restricted by type
- Audio data is validated before processing

## Performance Tips

1. **Use Azure STT** for lower latency
2. **Enable echo cancellation** for better audio quality
3. **Adjust VAD thresholds** based on environment
4. **Use streaming TTS** for faster response
5. **Cache context** for repeated queries

## Debugging

Enable debug mode:
```python
AIAvatar(debug=True)
```

Logs include:
- Component initialization
- Request/response flow
- Performance metrics
- Error traces

## Version History

- **0.7.x**: Integrated LiteSTS into core
- **0.6.x**: Added dynamic tools
- **0.5.x**: Initial public release