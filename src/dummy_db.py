from aiavatar.sts.performance_recorder import PerformanceRecord, PerformanceRecorder
from aiavatar.sts.voice_recorder import VoiceRecorder


class DummyPerformanceRecorder(PerformanceRecorder):
    """A performance recorder implementation that doesn't create a database file."""

    def __init__(self):
        pass

    def record(self, record: PerformanceRecord):
        pass

    def close(self):
        pass


class DummyVoiceRecorder(VoiceRecorder):
    """A voice recorder implementation that doesn't create a directory."""

    def __init__(self, *, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2):
        super().__init__(sample_rate=sample_rate, channels=channels, sample_width=sample_width)

    async def save_voice(self, id: str, voice_bytes: bytes, audio_format: str):
        pass
