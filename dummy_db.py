from aiavatar.sts.performance_recorder import PerformanceRecorder, PerformanceRecord
from aiavatar.sts.llm.context_manager import ContextManager
from aiavatar.sts.voice_recorder import VoiceRecorder
from datetime import datetime, timezone
from typing import List, Dict, Optional


class DummyPerformanceRecorder(PerformanceRecorder):
    """
    A performance recorder implementation that doesn't create a database file.
    """
    def __init__(self):
        pass
        
    def record(self, record: PerformanceRecord):
        pass
        
    def close(self):
        pass


class DummyContextManager(ContextManager):
    """
    A context manager implementation that doesn't create a database file.
    """
    def __init__(self):
        pass
        
    async def get_histories(self, context_id: str, limit: int = 100) -> List[Dict]:
        return []
        
    async def add_histories(self, context_id: str, data_list: List[Dict], context_schema: Optional[str] = None):
        pass
        
    async def get_last_created_at(self, context_id: str) -> datetime:
        return datetime.min.replace(tzinfo=timezone.utc)


class DummyVoiceRecorder(VoiceRecorder):
    """
    A voice recorder implementation that doesn't create a directory.
    """
    def __init__(self, *, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2):
        super().__init__(sample_rate=sample_rate, channels=channels, sample_width=sample_width)
        
    async def save_voice(self, id: str, voice_bytes: bytes, audio_format: str):
        pass
