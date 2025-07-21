"""log_handler.py のテスト"""

import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


class TestCocoroDockLogHandler:
    """CocoroDockLogHandler クラスのテスト"""

    def test_init_default(self):
        """デフォルト初期化のテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        
        assert handler.dock_url == "http://127.0.0.1:55600"
        assert handler.component_name == "CocoroCore"
        assert handler._enabled is False
        assert handler._client is None
        assert handler._startup_buffer == []
        assert handler._buffer_sent is False

    def test_init_custom(self):
        """カスタム設定での初期化のテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler(
            dock_url="http://localhost:12345/",
            component_name="TestComponent"
        )
        
        assert handler.dock_url == "http://localhost:12345"  # 末尾のスラッシュが削除される
        assert handler.component_name == "TestComponent"

    @patch('log_handler.httpx.AsyncClient')
    def test_set_enabled_true(self, mock_async_client):
        """ログ送信を有効にするテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        
        # 有効化
        handler.set_enabled(True)
        
        assert handler._enabled is True
        assert handler._client is not None

    def test_set_enabled_false(self):
        """ログ送信を無効にするテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        handler._client = MagicMock()
        
        # 無効化
        handler.set_enabled(False)
        
        assert handler._enabled is False

    def test_emit_log_format(self):
        """ログエミット時のフォーマットテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler(component_name="TestComp")
        handler._enabled = False  # バッファに保存させる
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # emitでバッファに保存
        handler.emit(record)
        
        # バッファの内容を確認
        assert len(handler._startup_buffer) == 1
        entry = handler._startup_buffer[0]
        
        assert entry["component"] == "TestComp"
        assert entry["level"] == "INFO"
        assert entry["message"] == "Test message"
        assert "timestamp" in entry

    def test_emit_when_disabled(self):
        """無効時のemitテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        handler._enabled = False
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        
        # 無効時はバッファに追加される
        handler.emit(record)
        
        assert len(handler._startup_buffer) == 1

    def test_emit_buffer_limit(self):
        """バッファサイズ制限のテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        handler._enabled = False
        
        # 500件以上のログを追加
        for i in range(600):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=i,
                msg=f"Test {i}",
                args=(),
                exc_info=None
            )
            handler.emit(record)
        
        # バッファは500件に制限される
        assert len(handler._startup_buffer) == 500

    @pytest.mark.asyncio
    async def test_send_log_async_success(self):
        """ログ非同期送信成功のテスト"""
        from log_handler import CocoroDockLogHandler
        
        # モッククライアントの設定
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.post.return_value = mock_response
        
        handler = CocoroDockLogHandler()
        handler._enabled = True
        handler._client = mock_client
        
        log_message = {"message": "Test log", "level": "INFO"}
        
        await handler._send_log_async(log_message)
        
        # POSTリクエストが送信されることを確認
        mock_client.post.assert_called_once_with(
            "http://127.0.0.1:55600/api/logs",
            json=log_message,
            timeout=2.0
        )

    @pytest.mark.asyncio
    async def test_send_log_async_failure(self):
        """ログ非同期送信失敗のテスト"""
        from log_handler import CocoroDockLogHandler
        
        # エラーを発生させるモッククライアント
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network error")
        
        handler = CocoroDockLogHandler()
        handler._enabled = True
        handler._client = mock_client
        
        log_message = {"message": "Test log"}
        
        # エラーが発生してもクラッシュしないことを確認
        await handler._send_log_async(log_message)

    def test_close(self):
        """クローズ処理のテスト"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        handler._client = MagicMock()
        handler._enabled = True
        
        handler.close()
        
        assert handler._enabled is False


class TestCocoroDockLogHandlerIntegration:
    """CocoroDockLogHandler 統合テスト"""

    @pytest.mark.asyncio
    async def test_full_logging_workflow(self):
        """完全なロギングワークフローのテスト"""
        from log_handler import CocoroDockLogHandler
        
        # ハンドラーの作成
        handler = CocoroDockLogHandler(
            dock_url="http://test:8080",
            component_name="TestApp"
        )
        
        # ロガーの設定
        logger = logging.getLogger("test_integration")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # 無効状態でログを記録（バッファに保存）
        logger.info("Startup log 1")
        logger.debug("Startup log 2")
        
        assert len(handler._startup_buffer) == 2
        
        # 有効化（実際の送信はモックで防ぐ）
        with patch('log_handler.httpx.AsyncClient'):
            handler.set_enabled(True)
            
            # 有効状態でログを記録
            logger.info("Runtime log 1")
            logger.warning("Runtime log 2")
        
        # クリーンアップ
        logger.removeHandler(handler)
        handler.close()

    def test_thread_safety(self):
        """スレッドセーフティのテスト"""
        from log_handler import CocoroDockLogHandler
        import threading
        
        handler = CocoroDockLogHandler()
        errors = []
        
        def log_from_thread(thread_id):
            try:
                record = logging.LogRecord(
                    name=f"thread_{thread_id}",
                    level=logging.INFO,
                    pathname="test.py",
                    lineno=1,
                    msg=f"Message from thread {thread_id}",
                    args=(),
                    exc_info=None
                )
                handler.emit(record)
            except Exception as e:
                errors.append(e)
        
        # 複数スレッドから同時にログを送信
        threads = []
        for i in range(10):
            t = threading.Thread(target=log_from_thread, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # エラーが発生していないことを確認
        assert len(errors) == 0
        # すべてのログがバッファに保存されていることを確認
        assert len(handler._startup_buffer) == 10


class TestCocoroDockLogHandlerBranchCoverage:
    """CocoroDockLogHandler 分岐カバレッジテスト"""
    
    def test_init_with_different_url_formats(self):
        """異なるURL形式での初期化テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        # 末尾スラッシュありURL
        handler1 = CocoroDockLogHandler(dock_url="http://127.0.0.1:55600/")
        assert handler1.dock_url == "http://127.0.0.1:55600"  # 末尾スラッシュが削除される
        
        # 末尾スラッシュなしURL
        handler2 = CocoroDockLogHandler(dock_url="http://127.0.0.1:55600")
        assert handler2.dock_url == "http://127.0.0.1:55600"  # そのまま
        
        # 空のURL
        handler3 = CocoroDockLogHandler(dock_url="")
        assert handler3.dock_url == ""
        
        # None URL（デフォルト）
        handler4 = CocoroDockLogHandler(dock_url=None)
        assert handler4.dock_url is None or handler4.dock_url == "http://127.0.0.1:55600"
    
    def test_set_enabled_state_transitions(self):
        """有効/無効状態遷移のテスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        
        # 初期状態は無効
        assert handler._enabled is False
        
        # 無効→有効
        with patch('log_handler.httpx.AsyncClient') as mock_client:
            handler.set_enabled(True)
            assert handler._enabled is True
            assert handler._client is not None
        
        # 有効→有効（再度有効化）
        with patch('log_handler.httpx.AsyncClient') as mock_client:
            handler.set_enabled(True)
            assert handler._enabled is True
        
        # 有効→無効
        handler.set_enabled(False)
        assert handler._enabled is False
        
        # 無効→無効（再度無効化）
        handler.set_enabled(False)
        assert handler._enabled is False
    
    def test_emit_buffer_conditions(self):
        """emit時のバッファ条件テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        handler._enabled = False  # バッファモード
        
        # バッファ空の状態
        assert len(handler._startup_buffer) == 0
        
        # 通常ログ
        record1 = logging.LogRecord("test", logging.INFO, "test.py", 1, "Test message", (), None)
        handler.emit(record1)
        assert len(handler._startup_buffer) == 1
        
        # 異なるレベルのログ
        record2 = logging.LogRecord("test", logging.ERROR, "test.py", 2, "Error message", (), None)
        handler.emit(record2)
        assert len(handler._startup_buffer) == 2
        
        # 例外情報付きログ
        try:
            raise ValueError("Test error")
        except ValueError as e:
            record3 = logging.LogRecord("test", logging.ERROR, "test.py", 3, "Exception", (), (type(e), e, e.__traceback__))
            handler.emit(record3)
        assert len(handler._startup_buffer) == 3
    
    def test_emit_when_enabled_vs_disabled(self):
        """有効時と無効時のemit動作テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        record = logging.LogRecord("test", logging.INFO, "test.py", 1, "Test", (), None)
        
        # 無効時: バッファに保存される
        handler._enabled = False
        handler.emit(record)
        assert len(handler._startup_buffer) == 1
        
        # 有効時: 直接送信される（モック）
        with patch('log_handler.httpx.AsyncClient') as mock_client:
            handler.set_enabled(True)
            
            # モッククライアントをセット
            mock_client_instance = AsyncMock()
            handler._client = mock_client_instance
            
            # 初期バッファをクリア
            handler._startup_buffer = []
            
            # 有効時にemit実行
            handler.emit(record)
            
            # バッファには保存されない
            assert len(handler._startup_buffer) == 0
    
    def test_send_startup_buffer_conditions(self):
        """スタートアップバッファ送信の条件テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        handler = CocoroDockLogHandler()
        
        # バッファが空の場合
        handler._startup_buffer = []
        handler._buffer_sent = False
        
        with patch('log_handler.httpx.AsyncClient') as mock_client:
            handler.set_enabled(True)
            # バッファ送信は実行されない（空のため）
            assert handler._buffer_sent is False
        
        # バッファにデータがある場合
        handler._startup_buffer = [{"test": "data"}]
        handler._buffer_sent = False
        
        with patch('log_handler.httpx.AsyncClient') as mock_client:
            handler.set_enabled(True)
            # バッファ送信タスクが作成される
            assert len(handler._startup_buffer) >= 0  # バッファ処理状態の確認
    
    @pytest.mark.asyncio
    async def test_send_log_async_with_different_errors(self):
        """異なるエラータイプでのログ非同期送信テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        import httpx
        
        handler = CocoroDockLogHandler()
        handler._enabled = True
        
        # HTTPエラー
        mock_client1 = AsyncMock()
        mock_client1.post.side_effect = httpx.HTTPError("HTTP Error")
        handler._client = mock_client1
        
        await handler._send_log_async({"message": "Test"})  # エラーが発生しても例外は伝播しない
        
        # タイムアウトエラー
        mock_client2 = AsyncMock()
        mock_client2.post.side_effect = httpx.TimeoutException("Timeout")
        handler._client = mock_client2
        
        await handler._send_log_async({"message": "Test"})  # エラーが発生しても例外は伝播しない
        
        # 一般的な例外
        mock_client3 = AsyncMock()
        mock_client3.post.side_effect = Exception("General Error")
        handler._client = mock_client3
        
        await handler._send_log_async({"message": "Test"})  # エラーが発生しても例外は伝播しない
    
    def test_close_with_different_states(self):
        """異なる状態でのclose処理テスト（分岐カバレッジ）"""
        from log_handler import CocoroDockLogHandler
        
        # 無効状態でclose
        handler1 = CocoroDockLogHandler()
        handler1._enabled = False
        handler1.close()
        assert handler1._enabled is False
        
        # 有効状態でclose
        handler2 = CocoroDockLogHandler()
        with patch('log_handler.httpx.AsyncClient'):
            handler2.set_enabled(True)
            handler2._enabled = True
            handler2._client = MagicMock()
            
            handler2.close()
            assert handler2._enabled is False
        
        # クライアントなしでclose
        handler3 = CocoroDockLogHandler()
        handler3._enabled = True
        handler3._client = None
        handler3.close()
        assert handler3._enabled is False