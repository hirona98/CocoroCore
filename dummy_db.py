from aiavatar.sts.performance_recorder import PerformanceRecorder, PerformanceRecord
from aiavatar.sts.llm.context_manager import ContextManager
from datetime import datetime, timezone
from typing import List, Dict


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
        
    async def add_histories(self, context_id: str, data_list: List[Dict], context_schema: str = None):
        pass
        
    async def get_last_created_at(self, context_id: str) -> datetime:
        return datetime.min.replace(tzinfo=timezone.utc)
