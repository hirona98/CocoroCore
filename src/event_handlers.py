"""イベントハンドラー関連のモジュール"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AppEventHandlers:
    """アプリケーションイベントハンドラーを担当するクラス"""

    def __init__(
        self,
        memory_client: Optional[Any] = None,
        session_manager: Optional[Any] = None,
        deps_container: Optional[Any] = None,
        vad_instance: Optional[Any] = None,
        vad_auto_adjustment: bool = True,
        stt_api_key: Optional[str] = None,
        user_id: str = "default",
        get_shared_context_id: Optional[callable] = None,
        cocoro_dock_client: Optional[Any] = None,
    ):
        """初期化
        
        Args:
            memory_client: メモリクライアント
            session_manager: セッションマネージャー
            deps_container: 依存関係コンテナ
            vad_instance: VADインスタンス
            vad_auto_adjustment: VAD自動調整フラグ
            stt_api_key: STT APIキー
            user_id: ユーザーID
            get_shared_context_id: 共有context_id取得関数
            cocoro_dock_client: CocoroDockクライアント
        """
        self.memory_client = memory_client
        self.session_manager = session_manager
        self.deps_container = deps_container
        self.vad_instance = vad_instance
        self.vad_auto_adjustment = vad_auto_adjustment
        self.stt_api_key = stt_api_key
        self.user_id = user_id
        self.get_shared_context_id = get_shared_context_id
        self.cocoro_dock_client = cocoro_dock_client
        self.timeout_check_task = None

    def create_startup_handler(self):
        """startup イベントハンドラーを作成"""
        async def startup():
            """アプリケーション起動時の処理"""
            await self._setup_memory_timeout_checker()
            await self._setup_mic_input()

        return startup

    def create_shutdown_handler(
        self,
        llm_status_manager: Any,
        cocoro_dock_client: Optional[Any],
        cocoro_shell_client: Optional[Any],
        stt_instance: Optional[Any],
    ):
        """shutdown イベントハンドラーを作成"""
        async def cleanup():
            """アプリケーション終了時の処理"""
            await self._cleanup_timeout_checker()
            await self._cleanup_memory()
            await self._cleanup_llm_status(llm_status_manager)
            await self._cleanup_api_clients(cocoro_dock_client, cocoro_shell_client)
            await self._cleanup_stt(stt_instance)
            await self._cleanup_mic_input()

        return cleanup

    def create_vad_startup_handler(self):
        """VAD用startup イベントハンドラーを作成"""
        async def startup_event():
            """VAD定期調整タスクを開始"""
            if (
                self.vad_instance
                and hasattr(self.vad_instance, "start_periodic_adjustment_task")
                and self.vad_auto_adjustment
            ):
                asyncio.create_task(self.vad_instance.start_periodic_adjustment_task())
                logger.info("🔄 VAD定期調整タスクを開始しました")
            elif self.vad_instance and not self.vad_auto_adjustment:
                logger.info("🔧 VAD自動調整無効のため、定期調整タスクはスキップしました")
            
            # MCP初期化が保留中の場合は実行
            try:
                from mcp_tools import initialize_mcp_if_pending
                await initialize_mcp_if_pending()
            except Exception as e:
                logger.error(f"MCP初期化エラー: {e}")

        return startup_event

    async def _setup_memory_timeout_checker(self):
        """メモリタイムアウトチェッカーの設定"""
        if not self.memory_client:
            return

        from session_manager import create_timeout_checker

        # SessionManagerとChatMemoryClientでタイムアウトチェッカーを開始
        async def timeout_checker_with_context_clear():
            """タイムアウトチェッカーにcontext_idクリア機能を追加"""
            checker = create_timeout_checker(self.session_manager, self.memory_client)
            while True:
                await checker
                # セッションタイムアウト時に共有context_idもクリア
                active_sessions = await self.session_manager.get_all_sessions()
                if not active_sessions and self.get_shared_context_id and self.get_shared_context_id():
                    shared_context_id = self.get_shared_context_id()
                    logger.info(
                        f"全セッションタイムアウトにより共有context_idをクリア: {shared_context_id}"
                    )
                    # 共有context_idのクリアは外部で実装される

        self.timeout_check_task = asyncio.create_task(timeout_checker_with_context_clear())
        logger.info("セッションタイムアウトチェックタスクを開始しました")

    async def _setup_mic_input(self):
        """マイク入力の設定"""
        if not (self.deps_container and self.stt_api_key and self.vad_instance):
            return

        from voice_processor import process_mic_input

        # マイク入力の開始（STTが有効かつインスタンスが作成されている場合）
        if self.deps_container.is_use_stt:
            self.deps_container.mic_input_task = asyncio.create_task(
                process_mic_input(
                    self.vad_instance, 
                    self.user_id, 
                    self.get_shared_context_id, 
                    self.cocoro_dock_client
                )
            )
            logger.info("起動時にSTTが有効のため、マイク入力を開始しました")
        else:
            logger.info("STTインスタンスは準備済み、APIコマンドで有効化可能です")

    async def _cleanup_timeout_checker(self):
        """タイムアウトチェッカーのクリーンアップ"""
        if self.timeout_check_task:
            self.timeout_check_task.cancel()
            try:
                await self.timeout_check_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_memory(self):
        """ChatMemoryのクリーンアップ"""
        if not self.memory_client:
            return

        # すべてのアクティブなセッションの要約を生成
        all_sessions = await self.session_manager.get_all_sessions()
        for session_key, _ in all_sessions.items():
            try:
                user_id, session_id = session_key.split(":", 1)
                logger.info(f"シャットダウン時の要約生成: {session_key}")
                await self.memory_client.create_summary(user_id, session_id)
            except Exception as e:
                logger.error(f"シャットダウン時の要約生成エラー: {e}")

        await self.memory_client.close()

    async def _cleanup_llm_status(self, llm_status_manager: Any):
        """LLMステータス送信タスクのクリーンアップ"""
        # 残っているLLMステータス送信タスクをすべてキャンセル
        for request_id, task in list(llm_status_manager.active_requests.items()):
            llm_status_manager.stop_periodic_status(request_id)
        logger.info("すべてのLLMステータス送信タスクを停止しました")

    async def _cleanup_api_clients(self, cocoro_dock_client: Optional[Any], cocoro_shell_client: Optional[Any]):
        """REST APIクライアントのクリーンアップ"""
        if cocoro_dock_client:
            logger.info("CocoroDockクライアントを終了します")
            await cocoro_dock_client.close()

        if cocoro_shell_client:
            logger.info("CocoroShellクライアントを終了します")
            await cocoro_shell_client.close()

    async def _cleanup_stt(self, stt_instance: Optional[Any]):
        """STT（音声認識）のクリーンアップ"""
        if stt_instance:
            logger.info("音声認識クライアントを終了します")
            await stt_instance.close()

    async def _cleanup_mic_input(self):
        """マイク入力タスクのクリーンアップ"""
        if self.deps_container and self.deps_container.mic_input_task:
            logger.info("マイク入力タスクを停止します")
            self.deps_container.mic_input_task.cancel()
            try:
                await self.deps_container.mic_input_task
            except asyncio.CancelledError:
                pass