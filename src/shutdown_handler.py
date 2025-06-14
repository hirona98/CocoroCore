"""グレースフルシャットダウンの実装"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """アプリケーションのグレースフルシャットダウンを管理"""
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.grace_period = 30  # デフォルト30秒
        self._shutdown_tasks = []
        
    def request_shutdown(self, grace_period: Optional[int] = None):
        """シャットダウンをリクエスト
        
        Args:
            grace_period: 猶予期間（秒）
        """
        if grace_period is not None:
            self.grace_period = grace_period
        
        logger.info(f"シャットダウンリクエストを受信しました。猶予期間: {self.grace_period}秒")
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self):
        """シャットダウンイベントを待機"""
        await self.shutdown_event.wait()
    
    def register_cleanup_task(self, task_func, task_name: str = ""):
        """クリーンアップタスクを登録
        
        Args:
            task_func: 非同期関数
            task_name: タスクの名前（ログ用）
        """
        self._shutdown_tasks.append((task_func, task_name))
    
    async def execute_shutdown(self):
        """登録されたクリーンアップタスクを実行"""
        logger.info("シャットダウン処理を開始します")
        
        # 猶予期間のカウントダウン
        for remaining in range(self.grace_period, 0, -5):
            if remaining > 5:
                logger.info(f"シャットダウンまで {remaining} 秒...")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(remaining)
                break
        
        # クリーンアップタスクを実行
        for task_func, task_name in self._shutdown_tasks:
            try:
                logger.info(f"クリーンアップタスクを実行: {task_name or task_func.__name__}")
                await task_func()
            except Exception as e:
                logger.error(f"クリーンアップタスクでエラー: {task_name or task_func.__name__} - {e}")
        
        logger.info("シャットダウン処理が完了しました")


# グローバルインスタンス
shutdown_handler = ShutdownHandler()