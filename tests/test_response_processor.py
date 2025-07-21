"""response_processor.py のテスト"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestResponseProcessor:
    """ResponseProcessor クラスのテスト"""

    def test_init(self):
        """初期化のテスト"""
        from response_processor import ResponseProcessor
        
        mock_llm_status_manager = MagicMock()
        mock_session_manager = MagicMock()
        mock_memory_client = MagicMock()
        mock_dock_client = MagicMock()
        mock_shell_client = MagicMock()
        mock_vad_instance = MagicMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=mock_llm_status_manager,
            session_manager=mock_session_manager,
            memory_client=mock_memory_client,
            cocoro_dock_client=mock_dock_client,
            cocoro_shell_client=mock_shell_client,
            current_char={"name": "TestChar"},
            vad_instance=mock_vad_instance
        )
        
        assert processor.user_id == "test_user"
        assert processor.llm_status_manager == mock_llm_status_manager
        assert processor.session_manager == mock_session_manager
        assert processor.memory_client == mock_memory_client
        assert processor.cocoro_dock_client == mock_dock_client
        assert processor.cocoro_shell_client == mock_shell_client
        assert processor.current_char == {"name": "TestChar"}
        assert processor.vad_instance == mock_vad_instance

    @pytest.mark.asyncio
    async def test_process_response_complete(self):
        """レスポンス完了処理のテスト"""
        from response_processor import ResponseProcessor
        
        mock_session_manager = AsyncMock()
        mock_llm_status_manager = MagicMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=mock_llm_status_manager,
            session_manager=mock_session_manager
        )
        
        # モックリクエストとレスポンス
        mock_request = MagicMock()
        mock_request.user_id = "test_user"
        mock_request.session_id = "session_123"
        mock_request.context_id = "context_456"
        
        mock_response = MagicMock()
        mock_response.context_id = "context_456"
        
        mock_context_setter = MagicMock()
        
        # 処理実行
        await processor.process_response_complete(
            mock_request, mock_response, mock_context_setter
        )
        
        # セッションアクティビティが更新されることを確認
        mock_session_manager.update_activity.assert_called_once_with(
            "test_user", "session_123"
        )

    def test_stop_llm_status(self):
        """LLMステータス停止のテスト"""
        from response_processor import ResponseProcessor
        
        mock_llm_status_manager = MagicMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=mock_llm_status_manager,
            session_manager=MagicMock()
        )
        
        mock_request = MagicMock()
        mock_request.session_id = "session_123"
        mock_request.user_id = "test_user"
        mock_request.context_id = "context_456"
        
        # LLMステータス停止
        processor._stop_llm_status(mock_request)
        
        # stop_periodic_statusが呼ばれることを確認
        mock_llm_status_manager.stop_periodic_status.assert_called_once_with(
            "session_123_test_user_context_456"
        )

    def test_update_shared_context_id(self):
        """共有コンテキストID更新のテスト"""
        from response_processor import ResponseProcessor
        
        mock_vad_instance = MagicMock()
        mock_vad_instance.sessions = {"session1": {}, "session2": {}}
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock(),
            vad_instance=mock_vad_instance
        )
        
        mock_response = MagicMock()
        mock_response.context_id = "new_context"
        
        mock_context_setter = MagicMock()
        
        # 共有コンテキストID更新
        processor._update_shared_context_id(mock_response, mock_context_setter)
        
        # context_setterが呼ばれることを確認
        mock_context_setter.assert_called_once_with("new_context")
        
        # VADセッションのcontext_idが設定されることを確認
        assert mock_vad_instance.set_session_data.call_count == 2

    def test_update_shared_context_id_no_context(self):
        """context_idがない場合のテスト"""
        from response_processor import ResponseProcessor
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock()
        )
        
        mock_response = MagicMock()
        mock_response.context_id = None
        
        mock_context_setter = MagicMock()
        
        # 共有コンテキストID更新
        processor._update_shared_context_id(mock_response, mock_context_setter)
        
        # context_setterが呼ばれないことを確認
        mock_context_setter.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_external_services(self):
        """外部サービス送信のテスト"""
        from response_processor import ResponseProcessor
        
        mock_memory_client = AsyncMock()
        mock_dock_client = AsyncMock()
        mock_shell_client = AsyncMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock(),
            memory_client=mock_memory_client,
            cocoro_dock_client=mock_dock_client,
            cocoro_shell_client=mock_shell_client
        )
        
        mock_request = MagicMock()
        mock_request.user_id = "test_user"
        mock_request.session_id = "session_123"
        mock_request.text = "Hello"
        mock_request.audio_data = None
        
        mock_response = MagicMock()
        mock_response.text = "Hi there!"
        
        # 外部サービス送信
        await processor._send_to_external_services(mock_request, mock_response)
        
        # メモリクライアントが呼ばれることを確認
        mock_memory_client.enqueue_messages.assert_called_once_with(
            mock_request, mock_response
        )

    @pytest.mark.asyncio
    async def test_send_to_external_services_no_memory(self):
        """メモリクライアントがない場合のテスト"""
        from response_processor import ResponseProcessor
        
        mock_dock_client = AsyncMock()
        mock_shell_client = AsyncMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock(),
            memory_client=None,  # メモリクライアントなし
            cocoro_dock_client=mock_dock_client,
            cocoro_shell_client=mock_shell_client
        )
        
        mock_request = MagicMock()
        mock_request.audio_data = None
        mock_response = MagicMock()
        mock_response.text = "Hi there!"
        
        # 外部サービス送信（エラーが発生しないことを確認）
        await processor._send_to_external_services(mock_request, mock_response)
        
        # エラーが発生していないことを確認
        assert True

    def test_init_with_defaults(self):
        """デフォルト値での初期化のテスト"""
        from response_processor import ResponseProcessor
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock()
        )
        
        assert processor.user_id == "test_user"
        assert processor.memory_client is None
        assert processor.cocoro_dock_client is None
        assert processor.cocoro_shell_client is None
        assert processor.current_char == {}
        assert processor.vad_instance is None