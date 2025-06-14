"""セッション管理とタイムアウト処理"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """セッション管理クラス"""
    
    def __init__(self, timeout_seconds: int = 300, max_sessions: int = 1000):
        """
        Args:
            timeout_seconds: セッションタイムアウト時間（秒）
            max_sessions: 最大セッション数
        """
        self.timeout_seconds = timeout_seconds
        self.max_sessions = max_sessions
        self.sessions: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        
    async def update_activity(self, user_id: str, session_id: str) -> None:
        """セッションのアクティビティを更新"""
        session_key = f"{user_id}:{session_id}"
        async with self._lock:
            # 最大セッション数を超えている場合、古いものを削除
            if len(self.sessions) >= self.max_sessions:
                # 最も古いセッションを削除
                oldest_key = min(self.sessions.items(), key=lambda x: x[1])[0]
                del self.sessions[oldest_key]
                logger.warning(f"最大セッション数に達したため、古いセッションを削除: {oldest_key}")
            
            self.sessions[session_key] = datetime.now()
    
    async def get_timed_out_sessions(self) -> list:
        """タイムアウトしたセッションのリストを取得"""
        current_time = datetime.now()
        timeout_threshold = current_time - timedelta(seconds=self.timeout_seconds)
        
        timed_out = []
        async with self._lock:
            for session_key, last_activity in list(self.sessions.items()):
                if last_activity < timeout_threshold:
                    timed_out.append(session_key)
                    del self.sessions[session_key]
        
        return timed_out
    
    async def remove_session(self, user_id: str, session_id: str) -> None:
        """セッションを削除"""
        session_key = f"{user_id}:{session_id}"
        async with self._lock:
            self.sessions.pop(session_key, None)
    
    def get_active_session_count(self) -> int:
        """アクティブなセッション数を取得"""
        return len(self.sessions)
    
    async def get_all_sessions(self) -> Dict[str, datetime]:
        """すべてのセッションを取得（シャットダウン時用）"""
        async with self._lock:
            return self.sessions.copy()


async def create_timeout_checker(session_manager: SessionManager, memory_client, check_interval: int = 30):
    """タイムアウトチェッカータスクを作成
    
    Args:
        session_manager: SessionManagerインスタンス
        memory_client: ChatMemoryClientインスタンス
        check_interval: チェック間隔（秒）
    """
    logger.info(f"セッションタイムアウトチェッカーを開始: {check_interval}秒ごとにチェック")
    
    while True:
        try:
            await asyncio.sleep(check_interval)
            
            # タイムアウトしたセッションを取得
            timed_out_sessions = await session_manager.get_timed_out_sessions()
            
            # 各セッションの要約を生成
            for session_key in timed_out_sessions:
                try:
                    user_id, session_id = session_key.split(":", 1)
                    logger.info(f"セッションタイムアウト検出: {session_key}")
                    await memory_client.create_summary(user_id, session_id)
                except Exception as e:
                    logger.error(f"タイムアウト処理エラー: {session_key} - {e}")
            
            # デバッグ情報
            if logger.isEnabledFor(logging.DEBUG):
                active_count = session_manager.get_active_session_count()
                logger.debug(f"アクティブセッション数: {active_count}")
                
        except asyncio.CancelledError:
            logger.info("セッションタイムアウトチェッカーを停止します")
            raise
        except Exception as e:
            logger.error(f"セッションタイムアウトチェックエラー: {e}")
            # エラーが発生しても継続
            await asyncio.sleep(5)  # エラー時は短い間隔で再試行