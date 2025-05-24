# AIAvatarKit User Guide

A practical guide for building AI-based conversational avatars with AIAvatarKit.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Implementation](#basic-implementation)
3. [Common Use Cases](#common-use-cases)
4. [Advanced Features](#advanced-features)
5. [Platform Integration](#platform-integration)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

Before you begin, ensure you have:

1. **Python 3.10+** installed
2. **VOICEVOX** running locally (download from https://voicevox.hiroshiba.jp/)
3. **API Keys** for at least one service:
   - OpenAI API key (for ChatGPT and Whisper)
   - Google Cloud credentials (optional)
   - Azure Speech Services key (optional)

### Installation

```bash
# Install AIAvatarKit
pip install aiavatar

# For additional features
pip install google-generativeai  # For Gemini support
pip install anthropic            # For Claude support
```

### Quick Test

```python
import asyncio
from aiavatar import AIAvatar

# Minimal setup
app = AIAvatar(
    openai_api_key="your-api-key",
    debug=True
)

# Start listening
asyncio.run(app.start_listening())
```

Say "こんにちは" (or "Hello" in English) to start a conversation!

## Basic Implementation

### 1. Simple Conversational Avatar

```python
import asyncio
from aiavatar import AIAvatar

# Create avatar with custom personality
app = AIAvatar(
    openai_api_key="your-api-key",
    system_prompt="""You are a friendly assistant named Alice. 
    You are helpful, cheerful, and always eager to assist.
    Keep responses concise and natural.""",
    voicevox_speaker=46,  # Sayo voice
    debug=True
)

# Start conversation
asyncio.run(app.start_listening())
```

### 2. Using Different LLM Providers

#### Claude

```python
from aiavatar import AIAvatar
from aiavatar.sts.llm.claude import ClaudeService

# Configure Claude
llm = ClaudeService(
    anthropic_api_key="your-anthropic-key",
    model="claude-3-5-sonnet-latest",
    system_prompt="You are a helpful assistant."
)

# Create avatar with Claude
app = AIAvatar(
    llm=llm,
    openai_api_key="your-openai-key"  # Still needed for STT
)
```

#### Gemini

```python
from aiavatar.sts.llm.gemini import GeminiService

llm = GeminiService(
    gemini_api_key="your-gemini-key",
    model="gemini-2.0-flash-exp",
    system_prompt="You are a creative storyteller."
)

app = AIAvatar(llm=llm, openai_api_key="your-openai-key")
```

### 3. Custom Voice Configuration

#### Using AivisSpeech

```python
from aiavatar.sts.tts.voicevox import VoicevoxSpeechSynthesizer

# Configure AivisSpeech
tts = VoicevoxSpeechSynthesizer(
    base_url="http://127.0.0.1:10101",  # AivisSpeech API
    speaker="888753761"  # Anneli voice
)

app = AIAvatar(
    tts=tts,
    openai_api_key="your-api-key"
)
```

#### Using OpenAI TTS

```python
from aiavatar.sts.tts.openai import OpenAISpeechSynthesizer

tts = OpenAISpeechSynthesizer(
    openai_api_key="your-api-key",
    voice="nova",  # or "alloy", "echo", "fable", "onyx", "shimmer"
    model="tts-1-hd"
)

app = AIAvatar(tts=tts, openai_api_key="your-api-key")
```

### 4. Faster Speech Recognition with Azure

```python
from aiavatar.sts.stt.azure import AzureSpeechRecognizer

# Azure STT is much faster than OpenAI
stt = AzureSpeechRecognizer(
    azure_api_key="your-azure-key",
    azure_region="eastus"
)

app = AIAvatar(
    stt=stt,
    openai_api_key="your-api-key"  # For LLM
)
```

## Common Use Cases

### 1. Customer Service Avatar

```python
from aiavatar import AIAvatar

app = AIAvatar(
    openai_api_key="your-api-key",
    system_prompt="""You are a customer service representative for TechCorp.
    Be professional, helpful, and empathetic.
    You can help with:
    - Product information
    - Technical support
    - Order status
    - Returns and refunds
    
    Always ask for clarification if needed.""",
    voicevox_speaker=1,  # Professional voice
)

# Add face expressions for empathy
app.adapter.face_controller.faces = {
    "neutral": "😊",
    "concern": "😟",
    "happy": "😄",
    "thinking": "🤔"
}

# Update prompt to use expressions
app.sts.llm.system_prompt += """
Use these expressions:
- [face:concern] when customer has issues
- [face:happy] when providing solutions
- [face:thinking] when processing requests
"""
```

### 2. Educational Tutor

```python
from aiavatar import AIAvatar

app = AIAvatar(
    openai_api_key="your-api-key",
    system_prompt="""You are an educational tutor specializing in mathematics.
    Your teaching style:
    - Break down complex problems into simple steps
    - Use examples and analogies
    - Encourage students when they're correct
    - Gently correct mistakes with explanations
    - Ask follow-up questions to ensure understanding""",
    voicevox_speaker=3,  # Friendly teacher voice
)

# Add encouraging expressions
app.adapter.face_controller.faces = {
    "neutral": "🙂",
    "proud": "😊",
    "encouraging": "😄",
    "thinking": "🤔"
}
```

### 3. Virtual Companion

```python
app = AIAvatar(
    openai_api_key="your-api-key",
    system_prompt="""You are a virtual companion named Miku.
    Personality traits:
    - Cheerful and optimistic
    - Loves to chat about daily life
    - Remembers previous conversations
    - Shows genuine interest in the user
    - Uses casual, friendly language""",
    voicevox_speaker=46,
    wakewords=["Hey Miku", "みくちゃん"],
    wakeword_timeout=300  # 5 minutes
)
```

### 4. Multilingual Assistant

```python
app = AIAvatar(
    openai_api_key="your-api-key",
    system_prompt="""You are a multilingual assistant.
    - Detect the user's language automatically
    - Respond in the same language
    - Help with translations if asked
    - Cultural awareness in responses
    
    Supported languages: English, Japanese, Spanish, French, German""",
)

# Language detection hook
@app.sts.process_llm_chunk
async def detect_language(response):
    # Simple language detection based on response
    if any(char >= '\u3040' and char <= '\u309f' for char in response.text):
        return {"language": "ja-JP"}
    elif any(char >= '\u00c0' and char <= '\u00ff' for char in response.text):
        return {"language": "fr-FR"}
    return {"language": "en-US"}
```

## Advanced Features

### 1. Tool Integration

#### Weather Tool Example

```python
import httpx
from aiavatar import AIAvatar

app = AIAvatar(openai_api_key="your-api-key")

# Define tool specification
weather_spec = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or coordinates"
                }
            },
            "required": ["location"]
        }
    }
}

# Implement tool
@app.sts.llm.tool(weather_spec)
async def get_weather(location: str):
    async with httpx.AsyncClient() as client:
        # Example API call
        response = await client.get(
            f"https://api.weather.com/v1/current?q={location}"
        )
        return response.json()
```

#### Web Search Tool

```python
from examples.tools.gemini_websearch import GeminiWebSearchTool

# Add web search capability
search_tool = GeminiWebSearchTool(gemini_api_key="your-gemini-key")
app.sts.llm.add_tool(search_tool)

# Update system prompt
app.sts.llm.system_prompt += """
You can search the web for current information when needed.
Use web search for:
- Recent events
- Current prices
- Latest news
- Facts you're unsure about
"""
```

### 2. Dynamic Tool Loading

```python
# Enable dynamic tools
app.sts.llm.use_dynamic_tools = True

# Register tools as dynamic
from aiavatar.sts.llm import Tool

app.sts.llm.add_tool(
    Tool(
        "calculate",
        calculate_spec,
        calculate_func,
        instruction="Use this for mathematical calculations",
        is_dynamic=True
    )
)

app.sts.llm.add_tool(
    Tool(
        "translate",
        translate_spec,
        translate_func,
        instruction="Use this for language translation",
        is_dynamic=True
    )
)
```

### 3. Vision Capabilities

```python
import pyautogui
import base64
from aiavatar.device.video import VideoDevice

# Setup camera
camera = VideoDevice(device_index=0, width=1280, height=720)

# Implement image capture
@app.adapter.get_image_url
async def get_image_url(source: str) -> str:
    if source == "camera":
        image_bytes = await camera.capture_image()
    elif source == "screenshot":
        image = pyautogui.screenshot()
        # Convert to bytes
        import io
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
    
    # Return as base64 URL
    b64 = base64.b64encode(image_bytes).decode()
    return f"data:image/png;base64,{b64}"

# Update system prompt
app.sts.llm.system_prompt += """
When you need to see something, use:
- [vision:camera] to take a photo
- [vision:screenshot] to capture screen

Example: "Let me see that" → "[vision:camera] I'll take a look."
"""
```

### 4. Long-term Memory

```python
from examples.misc.chatmemory import ChatMemoryClient

# Setup memory service
memory = ChatMemoryClient(base_url="http://localhost:8000")

# Save conversations
@app.sts.on_finish
async def save_to_memory(request, response):
    await memory.enqueue_messages(request, response)

# Add memory search tool
memory_search_spec = {
    "type": "function",
    "function": {
        "name": "search_memory",
        "description": "Search past conversations",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            }
        }
    }
}

@app.sts.llm.tool(memory_search_spec)
async def search_memory(query: str, metadata: dict = None):
    return await memory.search(metadata["user_id"], query)
```

### 5. Custom Response Processing

```python
# Process responses before sending
@app.on_response("chunk")
async def process_chunk(response):
    # Add timestamps to certain responses
    if "time" in response.text.lower():
        from datetime import datetime
        response.text += f" (Current time: {datetime.now().strftime('%H:%M')})"
    
    # Auto-translate if needed
    if response.metadata.get("translate"):
        response.text = await translate(response.text)

# Set thinking face while processing
@app.on_response("start")
async def on_start(response):
    await app.adapter.face_controller.set_face("thinking", 3.0)

@app.on_response("chunk")
async def on_first_chunk(response):
    if response.metadata.get("is_first_chunk"):
        app.adapter.face_controller.reset()
```

## Platform Integration

### 1. Web Application (HTTP API)

#### Server Setup

```python
from fastapi import FastAPI
from aiavatar.adapter.http.server import AIAvatarHttpServer

# Create server
avatar_server = AIAvatarHttpServer(
    openai_api_key="your-api-key",
    api_key="your-secret-key",  # API protection
    debug=True
)

# Setup FastAPI
app = FastAPI()
app.include_router(avatar_server.get_api_router())

# Run with: uvicorn server:app
```

#### Client Example (JavaScript)

```javascript
async function chat(message) {
    const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer your-secret-key'
        },
        body: JSON.stringify({
            type: 'start',
            session_id: 'web-session-1',
            user_id: 'user123',
            text: message
        })
    });

    const reader = response.body.getReader();
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = new TextDecoder().decode(value);
        const lines = text.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                handleResponse(data);
            }
        }
    }
}

function handleResponse(data) {
    if (data.type === 'chunk') {
        // Display text
        console.log(data.text);
        
        // Play audio
        if (data.audio_data) {
            playAudio(data.audio_data);
        }
        
        // Update avatar
        if (data.avatar_control_request) {
            updateAvatar(data.avatar_control_request);
        }
    }
}
```

### 2. WebSocket Integration

#### Server

```python
from aiavatar.adapter.websocket.server import AIAvatarWebSocketServer

avatar_ws = AIAvatarWebSocketServer(
    openai_api_key="your-api-key",
    volume_db_threshold=-30,
    debug=True
)

app = FastAPI()
app.include_router(avatar_ws.get_websocket_router())
```

#### Client

```python
from aiavatar.adapter.websocket.client import AIAvatarWebSocketClient

client = AIAvatarWebSocketClient(
    url="ws://localhost:8000/ws"
)

await client.start_listening(
    session_id="client-1",
    user_id="user123"
)
```

### 3. VRChat Integration

```python
from aiavatar import AIAvatar
from aiavatar.face.vrchat import VRChatFaceController

# Configure face controller
face_controller = VRChatFaceController(
    faces={
        "neutral": 0,
        "joy": 1,
        "angry": 2,
        "sorrow": 3,
        "fun": 4
    }
)

# Setup audio routing
app = AIAvatar(
    openai_api_key="your-api-key",
    input_device=6,   # VB-Cable-B Output
    output_device=13,  # VB-Cable-A Input
    face_controller=face_controller,
    system_prompt="""You are an avatar in VRChat.
    
    Use expressions:
    - [face:joy] when happy
    - [face:sorrow] when sad
    - [face:fun] when excited
    """
)
```

## Best Practices

### 1. Audio Configuration

```python
# List available devices
from aiavatar import AudioDevice
AudioDevice().list_audio_devices()

# Configure for best quality
app = AIAvatar(
    input_device=2,  # Your microphone
    output_device=3,  # Your speakers
    input_sample_rate=16000,
    input_chunk_size=512,
    cancel_echo=True,  # Important for speakers
)
```

### 2. Noise Management

```python
# Auto-adjust noise threshold
app = AIAvatar(
    auto_noise_filter_threshold=True,
    noise_margin=20.0  # Adjust based on environment
)

# Or set manually
app = AIAvatar(
    auto_noise_filter_threshold=False,
    volume_db_threshold=-40  # Lower = more sensitive
)
```

### 3. Performance Optimization

```python
# Use faster STT
from aiavatar.sts.stt.azure import AzureSpeechRecognizer
stt = AzureSpeechRecognizer(azure_api_key="key", azure_region="region")

# Use faster TTS
from aiavatar.sts.tts.azure import AzureSpeechSynthesizer
tts = AzureSpeechSynthesizer(
    azure_api_key="key",
    azure_region="region",
    voice="en-US-JennyNeural"
)

# Optimize LLM
from aiavatar.sts.llm.chatgpt import ChatGPTService
llm = ChatGPTService(
    openai_api_key="key",
    model="gpt-4o-mini",  # Faster than gpt-4o
    temperature=0.7
)

app = AIAvatar(stt=stt, tts=tts, llm=llm)
```

### 4. Error Handling

```python
# Global error handling
@app.sts.on_finish
async def handle_errors(request, response):
    if response.type == "error":
        # Log error
        logger.error(f"Error: {response.metadata.get('error')}")
        
        # Notify user
        await app.adapter.face_controller.set_face("concern", 3.0)
        
        # Play error sound
        error_audio = await app.sts.tts.synthesize(
            "I'm sorry, I encountered an error. Please try again."
        )
        await app.adapter.play_audio(error_audio)

# Tool error handling
@app.sts.llm.tool(spec)
async def safe_tool(param: str):
    try:
        return await risky_operation(param)
    except Exception as e:
        return {"error": str(e), "status": "failed"}
```

### 5. Context Management

```python
# Custom context manager
from aiavatar.sts.llm.context_manager import ContextManager

class CustomContextManager(ContextManager):
    async def get_histories(self, context_id: str) -> List[Dict]:
        # Load from your database
        return await db.get_messages(context_id)
    
    async def save_histories(self, context_id: str, messages: List[Dict]):
        # Save to your database
        await db.save_messages(context_id, messages)
        
        # Trim old messages
        if len(messages) > 50:
            await db.trim_messages(context_id, keep_last=30)

# Use custom manager
llm = ChatGPTService(
    openai_api_key="key",
    context_manager=CustomContextManager()
)
```

## Troubleshooting

### Common Issues

#### 1. No Audio Input/Output

```python
# Check devices
from aiavatar import AudioDevice
devices = AudioDevice().list_audio_devices()
for d in devices:
    print(f"{d['index']}: {d['name']}")

# Test specific device
app = AIAvatar(
    input_device=0,  # Try different indexes
    output_device=1,
    debug=True  # See detailed logs
)
```

#### 2. High Latency

**Solutions:**
- Use Azure STT instead of OpenAI
- Use smaller LLM models (gpt-4o-mini)
- Enable streaming TTS
- Check network connection
- Reduce audio chunk size

#### 3. Wakeword Not Working

```python
# Debug wakewords
app = AIAvatar(
    wakewords=["Hello", "Hey there", "こんにちは"],
    wakeword_timeout=120,  # 2 minutes
    debug=True
)

# Check logs for:
# - "Wake by 'Hello': Hello, how are you?"
# - Timeout messages
```

#### 4. Voice Detection Issues

```python
# Adjust VAD settings
app = AIAvatar(
    volume_db_threshold=-45,  # More sensitive
    silence_duration_threshold=0.3,  # Shorter pauses
)

# Or use auto-adjustment
app = AIAvatar(
    auto_noise_filter_threshold=True,
    noise_margin=15.0  # Lower for quieter environments
)
```

#### 5. Memory Leaks

```python
# Proper cleanup
async def main():
    app = AIAvatar(openai_api_key="key")
    try:
        await app.start_listening()
    finally:
        # Clean shutdown
        await app.stop_listening("session")
        await app.sts.shutdown()
```

### Debug Mode

```python
# Enable all debug logs
import logging
logging.basicConfig(level=logging.DEBUG)

app = AIAvatar(
    openai_api_key="key",
    debug=True
)

# Performance monitoring
from aiavatar.sts.performance_recorder.sqlite import SQLitePerformanceRecorder
recorder = SQLitePerformanceRecorder("performance.db")

app = AIAvatar(
    openai_api_key="key",
    performance_recorder=recorder
)
```

### Getting Help

1. **Check logs** - Enable debug mode
2. **Test components** - Isolate STT/TTS/LLM
3. **Verify APIs** - Check API keys and quotas
4. **GitHub Issues** - https://github.com/uezo/aiavatar/issues
5. **Community** - Join Discord/discussions

## Next Steps

1. **Experiment** with different voices and personalities
2. **Add tools** for your specific use case
3. **Integrate** with your platform of choice
4. **Optimize** for your performance needs
5. **Contribute** to the project!

Remember: AIAvatarKit is designed to be modular and extensible. Don't hesitate to create custom components that fit your specific needs!