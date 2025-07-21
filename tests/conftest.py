"""pytest設定ファイル"""
import pytest
import sys
import os
from unittest.mock import MagicMock

# srcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# aiavatarモジュールのモック
sys.modules['aiavatar'] = MagicMock()
sys.modules['aiavatar.adapter'] = MagicMock()
sys.modules['aiavatar.adapter.http'] = MagicMock()
sys.modules['aiavatar.adapter.http.server'] = MagicMock()
sys.modules['aiavatar.device'] = MagicMock()
sys.modules['aiavatar.device.audio'] = MagicMock()
sys.modules['aiavatar.sts'] = MagicMock()
sys.modules['aiavatar.sts.pipeline'] = MagicMock()
sys.modules['aiavatar.sts.tts'] = MagicMock()
sys.modules['aiavatar.sts.vad'] = MagicMock()
sys.modules['aiavatar.sts.stt'] = MagicMock()
sys.modules['aiavatar.sts.stt.amivoice'] = MagicMock()
sys.modules['aiavatar.sts.voice_recorder'] = MagicMock()
sys.modules['aiavatar.sts.voice_recorder.file'] = MagicMock()
sys.modules['aiavatar.sts.performance_recorder'] = MagicMock()

# モックされたクラスを作成
class MockAIAvatarHttpServer:
    def __init__(self, *args, **kwargs):
        pass

class MockAudioDevice:
    def __init__(self):
        self.input_device = 0

class MockAudioRecorder:
    def __init__(self, **kwargs):
        self.params = kwargs
        
    async def record_from_device(self, handler, **kwargs):
        await asyncio.sleep(0.1)
        return b"mock_audio_data"
        
    def start_stream(self):
        async def mock_stream():
            for i in range(10):
                await asyncio.sleep(0.1)
                yield b"mock_audio_chunk"
        return mock_stream()

class MockSTSPipeline:
    def __init__(self, *args, **kwargs):
        pass

class MockSpeechSynthesizerDummy:
    def __init__(self, *args, **kwargs):
        pass

class MockFileVoiceRecorder:
    def __init__(self, *args, **kwargs):
        pass

class MockStandardSpeechDetector:
    def __init__(self, *args, **kwargs):
        pass

class MockAmiVoiceSpeechRecognizer:
    def __init__(self, *args, **kwargs):
        pass
    
    async def transcribe(self, data: bytes) -> str:
        return "mock transcription"

class MockPerformanceRecord:
    def __init__(self, *args, **kwargs):
        pass

class MockPerformanceRecorder:
    def __init__(self, *args, **kwargs):
        pass
    
    def record(self, record):
        pass
    
    def close(self):
        pass

class MockVoiceRecorder:
    def __init__(self, *args, **kwargs):
        pass
    
    def save(self, data):
        pass

# モジュールにクラスを設定
sys.modules['aiavatar.adapter.http.server'].AIAvatarHttpServer = MockAIAvatarHttpServer
sys.modules['aiavatar.device.audio'].AudioDevice = MockAudioDevice
sys.modules['aiavatar.device.audio'].AudioRecorder = MockAudioRecorder
sys.modules['aiavatar.sts.pipeline'].STSPipeline = MockSTSPipeline
sys.modules['aiavatar.sts.tts'].SpeechSynthesizerDummy = MockSpeechSynthesizerDummy
sys.modules['aiavatar.sts.voice_recorder.file'].FileVoiceRecorder = MockFileVoiceRecorder
sys.modules['aiavatar.sts.vad'].StandardSpeechDetector = MockStandardSpeechDetector
sys.modules['aiavatar.sts.stt.amivoice'].AmiVoiceSpeechRecognizer = MockAmiVoiceSpeechRecognizer
sys.modules['aiavatar.sts.performance_recorder'].PerformanceRecord = MockPerformanceRecord
sys.modules['aiavatar.sts.performance_recorder'].PerformanceRecorder = MockPerformanceRecorder
sys.modules['aiavatar.sts.voice_recorder'].VoiceRecorder = MockVoiceRecorder

import asyncio


@pytest.fixture
def sample_config():
    """テスト用設定データ"""
    return {
        "CharacterName": "TestCharacter",
        "LLMProvider": "openai",
        "apiUrl": "http://localhost:55601",
        "ports": {
            "CocoroCore": 55601,
            "ChatMemory": 55602,
            "CocoroDock": 55600,
            "CocoroShell": 55605
        },
        "systemPrompt": "テスト用システムプロンプト"
    }


@pytest.fixture
def sample_request():
    """テスト用リクエストオブジェクト"""
    from unittest.mock import MagicMock
    
    request = MagicMock()
    request.text = "テストメッセージ"
    request.session_id = "test_session"
    request.user_id = "test_user"
    request.metadata = {}
    return request


@pytest.fixture
def sample_response():
    """テスト用レスポンスオブジェクト"""
    from unittest.mock import MagicMock
    
    response = MagicMock()
    response.text = "テストレスポンス"
    return response