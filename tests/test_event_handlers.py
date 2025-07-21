"""event_handlers.py のテスト"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestAppEventHandlers:
    """AppEventHandlers クラスのテスト"""

    def test_init(self):
        """初期化のテスト"""
        from event_handlers import AppEventHandlers
        
        mock_memory_client = MagicMock()
        mock_session_manager = MagicMock()
        mock_deps_container = MagicMock()
        mock_vad_instance = MagicMock()
        mock_dock_client = MagicMock()
        
        handlers = AppEventHandlers(
            memory_client=mock_memory_client,
            session_manager=mock_session_manager,
            deps_container=mock_deps_container,
            vad_instance=mock_vad_instance,
            vad_auto_adjustment=True,
            stt_api_key="test_key",
            user_id="test_user",
            get_shared_context_id=lambda: "test_context",
            cocoro_dock_client=mock_dock_client
        )
        
        assert handlers.memory_client == mock_memory_client
        assert handlers.session_manager == mock_session_manager
        assert handlers.deps_container == mock_deps_container
        assert handlers.vad_instance == mock_vad_instance
        assert handlers.vad_auto_adjustment is True
        assert handlers.stt_api_key == "test_key"
        assert handlers.user_id == "test_user"
        assert handlers.cocoro_dock_client == mock_dock_client

    def test_init_with_defaults(self):
        """デフォルト値での初期化のテスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers()
        
        assert handlers.memory_client is None
        assert handlers.session_manager is None
        assert handlers.deps_container is None
        assert handlers.vad_instance is None
        assert handlers.vad_auto_adjustment is True
        assert handlers.stt_api_key is None
        assert handlers.user_id == "default"
        assert handlers.get_shared_context_id is None
        assert handlers.cocoro_dock_client is None
        assert handlers.timeout_check_task is None

    def test_create_startup_handler(self):
        """startupハンドラー作成のテスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers(user_id="test_user")
        
        startup_handler = handlers.create_startup_handler()
        
        # startupハンドラーが作成されることを確認
        assert startup_handler is not None
        assert callable(startup_handler)

    def test_create_shutdown_handler(self):
        """shutdownハンドラー作成のテスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers(user_id="test_user")
        
        # 必要な引数を渡してshutdownハンドラーを作成
        shutdown_handler = handlers.create_shutdown_handler(
            llm_status_manager=MagicMock(),
            cocoro_dock_client=MagicMock(),
            cocoro_shell_client=MagicMock(),
            stt_instance=MagicMock()
        )
        
        # shutdownハンドラーが作成されることを確認
        assert shutdown_handler is not None
        assert callable(shutdown_handler)

    @pytest.mark.asyncio
    async def test_startup_handler_execution(self):
        """startupハンドラー実行のテスト"""
        from event_handlers import AppEventHandlers
        
        mock_session_manager = AsyncMock()
        
        handlers = AppEventHandlers(
            session_manager=mock_session_manager,
            user_id="test_user"
        )
        
        startup_handler = handlers.create_startup_handler()
        
        # startupハンドラーを実行
        await startup_handler()
        
        # 処理が完了することを確認
        assert True  # エラーが発生しなければOK

    @pytest.mark.asyncio
    async def test_shutdown_handler_execution(self):
        """shutdownハンドラー実行のテスト"""
        from event_handlers import AppEventHandlers
        
        mock_memory_client = AsyncMock()
        mock_session_manager = AsyncMock()
        # get_all_sessions の戻り値を辞書として設定（user_id:session_id形式のキー）
        mock_session_manager.get_all_sessions.return_value = {"test_user:session1": {}, "test_user:session2": {}}
        
        handlers = AppEventHandlers(
            memory_client=mock_memory_client,
            session_manager=mock_session_manager,
            user_id="test_user"
        )
        
        # 必要な引数を渡してshutdownハンドラーを作成（非同期メソッド対応）
        mock_dock_client = AsyncMock()
        mock_shell_client = AsyncMock()
        mock_stt = AsyncMock()
        
        shutdown_handler = handlers.create_shutdown_handler(
            llm_status_manager=MagicMock(),
            cocoro_dock_client=mock_dock_client,
            cocoro_shell_client=mock_shell_client,
            stt_instance=mock_stt
        )
        
        # shutdownハンドラーを実行
        await shutdown_handler()
        
        # 処理が完了することを確認
        assert True  # エラーが発生しなければOK

    def test_timeout_check_task_management(self):
        """タイムアウトチェックタスク管理のテスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers(user_id="test_user")
        
        # 初期状態ではタスクがNone
        assert handlers.timeout_check_task is None
        
        # タスクを設定
        mock_task = MagicMock()
        handlers.timeout_check_task = mock_task
        
        assert handlers.timeout_check_task == mock_task

    def test_vad_auto_adjustment_flag(self):
        """VAD自動調整フラグのテスト"""
        from event_handlers import AppEventHandlers
        
        # 自動調整有効
        handlers_enabled = AppEventHandlers(vad_auto_adjustment=True)
        assert handlers_enabled.vad_auto_adjustment is True
        
        # 自動調整無効
        handlers_disabled = AppEventHandlers(vad_auto_adjustment=False)
        assert handlers_disabled.vad_auto_adjustment is False

    def test_shared_context_id_getter(self):
        """共有コンテキストID取得のテスト"""
        from event_handlers import AppEventHandlers
        
        test_context_id = "test_context_123"
        get_context_func = lambda: test_context_id
        
        handlers = AppEventHandlers(get_shared_context_id=get_context_func)
        
        # コンテキストID取得関数が設定されることを確認
        assert handlers.get_shared_context_id() == test_context_id

    def test_event_handlers_integration(self):
        """イベントハンドラー統合のテスト"""
        from event_handlers import AppEventHandlers
        
        # 全ての依存関係を持つハンドラーを作成
        handlers = AppEventHandlers(
            memory_client=AsyncMock(),
            session_manager=AsyncMock(),
            deps_container=MagicMock(),
            vad_instance=MagicMock(),
            vad_auto_adjustment=True,
            stt_api_key="test_key",
            user_id="integration_user",
            get_shared_context_id=lambda: "integration_context",
            cocoro_dock_client=AsyncMock()
        )
        
        # startupとshutdownハンドラーが両方とも作成できることを確認
        startup_handler = handlers.create_startup_handler()
        shutdown_handler = handlers.create_shutdown_handler(
            llm_status_manager=MagicMock(),
            cocoro_dock_client=MagicMock(),
            cocoro_shell_client=MagicMock(),
            stt_instance=MagicMock()
        )
        
        assert startup_handler is not None
        assert shutdown_handler is not None
        assert callable(startup_handler)
        assert callable(shutdown_handler)