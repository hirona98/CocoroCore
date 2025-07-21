"""llm_manager.py のユニットテスト"""
import asyncio
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# aiavatar依存関係をモック
sys.modules['aiavatar'] = MagicMock()
sys.modules['aiavatar.sts'] = MagicMock()
sys.modules['aiavatar.sts.llm'] = MagicMock()
sys.modules['aiavatar.sts.llm.litellm'] = MagicMock()
sys.modules['aiavatar.sts.llm.context_manager'] = MagicMock()
sys.modules['aiavatar.sts.llm.context_manager.base'] = MagicMock()

from llm_manager import LLMStatusManager, LLMWithSharedContext, create_llm_service


class TestLLMStatusManager(unittest.IsolatedAsyncioTestCase):
    """LLMStatusManager クラスのテストクラス"""

    async def asyncSetUp(self):
        """テストセットアップ"""
        self.mock_dock_client = AsyncMock()
        self.manager = LLMStatusManager(self.mock_dock_client)

    def test_init(self):
        """初期化のテスト"""
        manager = LLMStatusManager(self.mock_dock_client)
        self.assertEqual(manager.dock_client, self.mock_dock_client)
        self.assertEqual(manager.active_requests, {})

    def test_init_without_dock_client(self):
        """dock_clientなしでの初期化テスト"""
        manager = LLMStatusManager(None)
        self.assertIsNone(manager.dock_client)
        self.assertEqual(manager.active_requests, {})

    async def test_start_periodic_status(self):
        """定期的なステータス送信開始のテスト"""
        request_id = "test_request_123"
        
        # ステータス送信を開始
        await self.manager.start_periodic_status(request_id)
        
        # タスクが作成され、保存されることを確認
        self.assertIn(request_id, self.manager.active_requests)
        self.assertIsInstance(self.manager.active_requests[request_id], asyncio.Task)
        
        # 少し待ってステータス送信を確認
        await asyncio.sleep(1.5)
        
        # send_status_updateが呼ばれることを確認
        self.mock_dock_client.send_status_update.assert_called()
        
        # タスクをクリーンアップ
        self.manager.stop_periodic_status(request_id)

    async def test_start_periodic_status_without_dock_client(self):
        """dock_clientがない場合のステータス送信テスト"""
        manager = LLMStatusManager(None)
        request_id = "test_request_456"
        
        # ステータス送信を開始（例外が発生しないことを確認）
        await manager.start_periodic_status(request_id)
        
        # タスクが作成されることを確認
        self.assertIn(request_id, manager.active_requests)
        
        # 少し待ってからクリーンアップ
        await asyncio.sleep(0.1)
        manager.stop_periodic_status(request_id)

    def test_stop_periodic_status(self):
        """定期的なステータス送信停止のテスト"""
        request_id = "test_request_789"
        
        # モックタスクを作成
        mock_task = MagicMock()
        self.manager.active_requests[request_id] = mock_task
        
        # ステータス送信を停止
        self.manager.stop_periodic_status(request_id)
        
        # タスクがキャンセルされ、辞書から削除されることを確認
        mock_task.cancel.assert_called_once()
        self.assertNotIn(request_id, self.manager.active_requests)

    def test_stop_periodic_status_nonexistent(self):
        """存在しないリクエストIDの停止テスト"""
        # 存在しないリクエストIDで停止を試行（例外が発生しないことを確認）
        self.manager.stop_periodic_status("nonexistent_id")

    async def test_multiple_requests(self):
        """複数リクエストの管理テスト"""
        request_ids = ["req1", "req2", "req3"]
        
        # 複数のステータス送信を開始
        for request_id in request_ids:
            await self.manager.start_periodic_status(request_id)
        
        # すべてのタスクが管理されることを確認
        self.assertEqual(len(self.manager.active_requests), 3)
        for request_id in request_ids:
            self.assertIn(request_id, self.manager.active_requests)
        
        # 一部を停止
        self.manager.stop_periodic_status("req2")
        self.assertEqual(len(self.manager.active_requests), 2)
        self.assertNotIn("req2", self.manager.active_requests)
        
        # 残りをクリーンアップ
        for request_id in ["req1", "req3"]:
            self.manager.stop_periodic_status(request_id)


class TestLLMWithSharedContext(unittest.IsolatedAsyncioTestCase):
    """LLMWithSharedContext クラスのテストクラス"""

    def setUp(self):
        """テストセットアップ"""
        self.mock_base_llm = MagicMock()
        self.mock_context_provider = MagicMock()
        self.llm_wrapper = LLMWithSharedContext(self.mock_base_llm, self.mock_context_provider)

    def test_init(self):
        """初期化のテスト"""
        self.assertEqual(self.llm_wrapper.base_llm, self.mock_base_llm)
        self.assertEqual(self.llm_wrapper.context_provider, self.mock_context_provider)

    def test_init_without_context_provider(self):
        """コンテキストプロバイダーなしでの初期化テスト"""
        llm_wrapper = LLMWithSharedContext(self.mock_base_llm)
        self.assertEqual(llm_wrapper.base_llm, self.mock_base_llm)
        self.assertIsNone(llm_wrapper.context_provider)

    def test_getattr_delegation(self):
        """属性アクセスの委譲テスト"""
        # base_llmの属性にアクセス
        self.mock_base_llm.some_attribute = "test_value"
        self.assertEqual(self.llm_wrapper.some_attribute, "test_value")

    def test_setattr_base_llm_attributes(self):
        """base_llm属性の設定テスト"""
        new_base_llm = MagicMock()
        self.llm_wrapper.base_llm = new_base_llm
        self.assertEqual(self.llm_wrapper.base_llm, new_base_llm)

    def test_setattr_other_attributes(self):
        """その他の属性の設定テスト"""
        # base_llmをモックとして再設定
        self.mock_base_llm = MagicMock()
        self.llm_wrapper.base_llm = self.mock_base_llm
        
        self.llm_wrapper.custom_attribute = "custom_value"
        # 実際にsetattr機能が動作することを確認
        self.assertTrue(hasattr(self.mock_base_llm, "custom_attribute"))

    async def test_get_response_with_shared_context(self):
        """共有コンテキストIDでのレスポンス取得テスト"""
        # モック設定
        self.mock_context_provider.return_value = "shared_context_123"
        self.mock_base_llm.get_response = AsyncMock(return_value="test_response")
        
        messages = [{"role": "user", "content": "test"}]
        result = await self.llm_wrapper.get_response(messages)
        
        # 共有コンテキストIDが使用されることを確認
        self.mock_base_llm.get_response.assert_called_once_with(
            messages, context_id="shared_context_123"
        )
        self.assertEqual(result, "test_response")

    async def test_get_response_with_explicit_context(self):
        """明示的なコンテキストIDでのレスポンス取得テスト"""
        # モック設定
        self.mock_context_provider.return_value = "shared_context_123"
        self.mock_base_llm.get_response = AsyncMock(return_value="test_response")
        
        messages = [{"role": "user", "content": "test"}]
        explicit_context = "explicit_context_456"
        
        result = await self.llm_wrapper.get_response(messages, context_id=explicit_context)
        
        # 明示的なコンテキストIDが優先されることを確認
        self.mock_base_llm.get_response.assert_called_once_with(
            messages, context_id=explicit_context
        )

    async def test_get_response_no_context_provider(self):
        """コンテキストプロバイダーなしでのレスポンス取得テスト"""
        llm_wrapper = LLMWithSharedContext(self.mock_base_llm)
        self.mock_base_llm.get_response = AsyncMock(return_value="test_response")
        
        messages = [{"role": "user", "content": "test"}]
        result = await llm_wrapper.get_response(messages)
        
        # context_id=Noneで呼ばれることを確認
        self.mock_base_llm.get_response.assert_called_once_with(
            messages, context_id=None
        )

    async def test_get_response_empty_shared_context(self):
        """空の共有コンテキストIDの場合のテスト"""
        self.mock_context_provider.return_value = ""
        self.mock_base_llm.get_response = AsyncMock(return_value="test_response")
        
        messages = [{"role": "user", "content": "test"}]
        result = await self.llm_wrapper.get_response(messages)
        
        # 空の場合はcontext_id=Noneで呼ばれることを確認
        self.mock_base_llm.get_response.assert_called_once_with(
            messages, context_id=None
        )

    async def test_get_response_stream_with_shared_context(self):
        """共有コンテキストIDでのストリームレスポンス取得テスト"""
        # モック設定
        self.mock_context_provider.return_value = "shared_context_stream"
        
        async def mock_stream():
            yield "chunk1"
            yield "chunk2"
        
        # AsyncGeneratorをモック
        mock_generator = mock_stream()
        self.mock_base_llm.get_response_stream.return_value = mock_generator
        
        messages = [{"role": "user", "content": "test"}]
        chunks = []
        async for chunk in self.llm_wrapper.get_response_stream(messages):
            chunks.append(chunk)
        
        # 共有コンテキストIDが使用されることを確認
        self.mock_base_llm.get_response_stream.assert_called_once_with(
            messages, context_id="shared_context_stream"
        )
        # チャンクが正しく取得されることを確認
        self.assertEqual(chunks, ["chunk1", "chunk2"])

    async def test_get_response_with_kwargs(self):
        """追加引数付きでのレスポンス取得テスト"""
        self.mock_context_provider.return_value = "context_with_kwargs"
        self.mock_base_llm.get_response = AsyncMock(return_value="test_response")
        
        messages = [{"role": "user", "content": "test"}]
        result = await self.llm_wrapper.get_response(
            messages, temperature=0.5, max_tokens=100
        )
        
        # 追加引数も渡されることを確認
        self.mock_base_llm.get_response.assert_called_once_with(
            messages, context_id="context_with_kwargs", temperature=0.5, max_tokens=100
        )


class TestCreateLLMService(unittest.TestCase):
    """create_llm_service 関数のテストクラス"""

    @patch('llm_manager.LiteLLMService')
    @patch('llm_manager.SQLiteContextManager')
    @patch('llm_manager.get_config_directory')
    def test_create_llm_service_basic(self, mock_get_config_directory, mock_sqlite_context_manager, mock_litellm_service):
        """基本的なLLMサービス作成テスト"""
        # モック設定
        mock_get_config_directory.return_value = "/test/config"
        mock_context_manager = MagicMock()
        mock_sqlite_context_manager.return_value = mock_context_manager
        mock_base_llm = MagicMock()
        mock_litellm_service.return_value = mock_base_llm
        
        # サービス作成
        result = create_llm_service(
            api_key="test_api_key",
            model="gpt-3.5-turbo",
            system_prompt="You are a helpful assistant."
        )
        
        # SQLiteContextManagerが正しいパスで呼ばれることを確認
        mock_sqlite_context_manager.assert_called_once_with(db_path="/test/config\\context.db")
        
        # LiteLLMServiceが正しい引数で呼ばれることを確認
        mock_litellm_service.assert_called_once_with(
            api_key="test_api_key",
            model="gpt-3.5-turbo",
            temperature=1.0,
            system_prompt="You are a helpful assistant.",
            context_manager=mock_context_manager
        )
        
        # 戻り値がLLMWithSharedContextであることを確認
        self.assertIsInstance(result, LLMWithSharedContext)
        self.assertEqual(result.base_llm, mock_base_llm)

    @patch('llm_manager.LiteLLMService')
    @patch('llm_manager.SQLiteContextManager')
    @patch('llm_manager.get_config_directory')
    def test_create_llm_service_with_context_provider(self, mock_get_config_directory, mock_sqlite_context_manager, mock_litellm_service):
        """コンテキストプロバイダー付きでのLLMサービス作成テスト"""
        mock_get_config_directory.return_value = "/test/config"
        mock_context_manager = MagicMock()
        mock_sqlite_context_manager.return_value = mock_context_manager
        mock_base_llm = MagicMock()
        mock_litellm_service.return_value = mock_base_llm
        mock_context_provider = MagicMock()
        
        result = create_llm_service(
            api_key="test_api_key",
            model="gpt-4",
            system_prompt="System prompt",
            context_provider=mock_context_provider,
            temperature=0.7
        )
        
        # 正しい引数でLiteLLMServiceが作成されることを確認
        mock_litellm_service.assert_called_once_with(
            api_key="test_api_key",
            model="gpt-4",
            temperature=0.7,
            system_prompt="System prompt",
            context_manager=mock_context_manager
        )
        
        # コンテキストプロバイダーが設定されることを確認
        self.assertEqual(result.context_provider, mock_context_provider)

    def test_create_llm_service_no_api_key(self):
        """APIキーなしでのLLMサービス作成テスト"""
        with self.assertRaises(ValueError) as context:
            create_llm_service(
                api_key="",
                model="gpt-3.5-turbo",
                system_prompt="System prompt"
            )
        
        self.assertIn("APIキーが設定されていません", str(context.exception))

    def test_create_llm_service_none_api_key(self):
        """None APIキーでのLLMサービス作成テスト"""
        with self.assertRaises(ValueError) as context:
            create_llm_service(
                api_key=None,
                model="gpt-3.5-turbo",
                system_prompt="System prompt"
            )
        
        self.assertIn("APIキーが設定されていません", str(context.exception))

    @patch('llm_manager.LiteLLMService')
    @patch('llm_manager.SQLiteContextManager')
    @patch('llm_manager.get_config_directory')
    def test_create_llm_service_default_temperature(self, mock_get_config_directory, mock_sqlite_context_manager, mock_litellm_service):
        """デフォルト温度設定でのLLMサービス作成テスト"""
        mock_get_config_directory.return_value = "/test/config"
        mock_context_manager = MagicMock()
        mock_sqlite_context_manager.return_value = mock_context_manager
        mock_base_llm = MagicMock()
        mock_litellm_service.return_value = mock_base_llm
        
        result = create_llm_service(
            api_key="test_api_key",
            model="gpt-3.5-turbo",
            system_prompt="System prompt"
            # temperatureは指定しない（デフォルト値1.0を使用）
        )
        
        # デフォルト温度1.0で呼ばれることを確認
        mock_litellm_service.assert_called_once_with(
            api_key="test_api_key",
            model="gpt-3.5-turbo",
            temperature=1.0,
            system_prompt="System prompt",
            context_manager=mock_context_manager
        )


class TestLLMManagerIntegration(unittest.IsolatedAsyncioTestCase):
    """llm_manager の統合テストクラス"""

    @patch('llm_manager.LiteLLMService')
    @patch('llm_manager.SQLiteContextManager')
    @patch('llm_manager.get_config_directory')
    async def test_integration_status_manager_with_llm_service(self, mock_get_config_directory, mock_sqlite_context_manager, mock_litellm_service):
        """ステータスマネージャーとLLMサービスの統合テスト"""
        # LLMサービス作成
        mock_get_config_directory.return_value = "/test/config"
        mock_context_manager = MagicMock()
        mock_sqlite_context_manager.return_value = mock_context_manager
        mock_base_llm = MagicMock()
        mock_litellm_service.return_value = mock_base_llm
        
        llm_service = create_llm_service(
            api_key="test_key",
            model="gpt-3.5-turbo",
            system_prompt="Test prompt"
        )
        
        # ステータスマネージャー作成
        mock_dock_client = AsyncMock()
        status_manager = LLMStatusManager(mock_dock_client)
        
        # 統合動作テスト
        request_id = "integration_test"
        await status_manager.start_periodic_status(request_id)
        
        # LLMサービスが正常に作成されることを確認
        self.assertIsInstance(llm_service, LLMWithSharedContext)
        
        # ステータス管理も正常に動作することを確認
        self.assertIn(request_id, status_manager.active_requests)
        
        # クリーンアップ
        status_manager.stop_periodic_status(request_id)


if __name__ == '__main__':
    unittest.main()