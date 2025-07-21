"""memory_client.py のユニットテスト"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from memory_client import ChatMemoryClient


class TestChatMemoryClient(unittest.IsolatedAsyncioTestCase):
    """ChatMemoryClient のテストクラス"""

    async def asyncSetUp(self):
        """各テストの前処理"""
        self.base_url = "http://localhost:55602"
        self.client = ChatMemoryClient(self.base_url)

    async def asyncTearDown(self):
        """各テストの後処理"""
        await self.client.close()

    def test_init(self):
        """初期化のテスト"""
        client = ChatMemoryClient("http://localhost:55602", timeout=15.0)
        self.assertEqual(client.base_url, "http://localhost:55602")
        self.assertEqual(client.timeout, 15.0)
        self.assertEqual(len(client._message_queue), 0)

    def test_init_strips_trailing_slash(self):
        """base_urlの末尾スラッシュ除去のテスト"""
        client = ChatMemoryClient("http://localhost:55602/")
        self.assertEqual(client.base_url, "http://localhost:55602")

    async def test_enqueue_messages_basic(self):
        """基本的なメッセージエンキューのテスト"""
        # モックリクエスト/レスポンスを作成
        request = MagicMock()
        request.text = "こんにちは"
        request.session_id = "test_session"
        request.user_id = "test_user"
        request.metadata = {}

        response = MagicMock()
        response.text = "こんにちは！元気ですか？"

        # メッセージをエンキュー
        await self.client.enqueue_messages(request, response)

        # キューに追加されたことを確認
        self.assertEqual(len(self.client._message_queue), 2)
        
        # ユーザーメッセージを確認
        user_msg = self.client._message_queue[0]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "こんにちは")
        self.assertEqual(user_msg["metadata"]["session_id"], "test_session")
        self.assertEqual(user_msg["metadata"]["user_id"], "test_user")

        # アシスタントメッセージを確認
        assistant_msg = self.client._message_queue[1]
        self.assertEqual(assistant_msg["role"], "assistant")
        self.assertEqual(assistant_msg["content"], "こんにちは！元気ですか？")

    async def test_enqueue_messages_empty_content(self):
        """空のメッセージをスキップするテスト"""
        # 空のリクエスト
        request = MagicMock()
        request.text = ""
        request.session_id = "test_session"
        request.user_id = "test_user"
        request.metadata = {}

        response = MagicMock()
        response.text = "レスポンス"

        # メッセージをエンキュー（スキップされるはず）
        await self.client.enqueue_messages(request, response)

        # キューが空であることを確認
        self.assertEqual(len(self.client._message_queue), 0)

    async def test_enqueue_messages_with_image_metadata(self):
        """画像メタデータ付きメッセージのテスト"""
        request = MagicMock()
        request.text = "この画像について説明して"
        request.session_id = "test_session"
        request.user_id = "test_user"
        request.metadata = {
            "image_description": "美しい夕日の写真",
            "image_category": "風景",
            "image_mood": "穏やか",
            "image_time": "夕方"
        }

        response = MagicMock()
        response.text = "美しい夕日の写真ですね"

        # メッセージをエンキュー
        await self.client.enqueue_messages(request, response)

        # システムメッセージが追加されていることを確認
        self.assertEqual(len(self.client._message_queue), 3)
        
        # システムメッセージを確認
        system_msg = self.client._message_queue[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("美しい夕日の写真", system_msg["content"])
        self.assertIn("分類: 風景/穏やか/夕方", system_msg["content"])

    async def test_enqueue_messages_with_notification_metadata(self):
        """通知メタデータ付きメッセージのテスト"""
        request = MagicMock()
        request.text = "通知が来ました"
        request.session_id = "test_session"
        request.user_id = "test_user"
        request.metadata = {
            "notification_app": "TestApp",
            "notification_title": "テスト通知",
            "notification_body": "これはテスト通知です"
        }

        response = MagicMock()
        response.text = "通知を確認しました"

        # メッセージをエンキュー
        await self.client.enqueue_messages(request, response)

        # 通知メタデータが含まれていることを確認
        user_msg = self.client._message_queue[0]
        self.assertEqual(user_msg["metadata"]["notification_app"], "TestApp")
        self.assertEqual(user_msg["metadata"]["notification_title"], "テスト通知")

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_save_history_success(self, mock_post):
        """履歴保存成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # テストメッセージをキューに追加
        self.client._message_queue = [
            {"role": "user", "content": "テストメッセージ", "metadata": {"session_id": "test"}}
        ]

        # 履歴を保存
        await self.client.save_history("test_user", "test_session")

        # 成功することを確認
        mock_post.assert_called_once()
        
        # キューがクリアされることを確認
        self.assertEqual(len(self.client._message_queue), 0)

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_save_history_failure(self, mock_post):
        """履歴保存失敗のテスト"""
        # 例外を発生させる
        mock_post.side_effect = Exception("Connection error")

        # テストメッセージをキューに追加
        original_messages = [
            {"role": "user", "content": "テストメッセージ", "metadata": {"session_id": "test"}}
        ]
        self.client._message_queue = original_messages.copy()

        # 履歴を保存（失敗するはず）
        await self.client.save_history("test_user", "test_session")

        # メッセージがキューに戻されることを確認
        self.assertEqual(len(self.client._message_queue), 1)

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_search_success(self, mock_post):
        """記憶検索成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "retrieved_data": "テスト記憶データ"
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 記憶を検索
        result = await self.client.search("test_user", "テストクエリ")

        # 結果を確認
        self.assertIsNotNone(result)
        self.assertEqual(result["retrieved_data"], "テスト記憶データ")

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_search_failure(self, mock_post):
        """記憶検索失敗のテスト"""
        # 例外を発生させる
        mock_post.side_effect = Exception("Search error")

        # 記憶を検索（失敗するはず）
        result = await self.client.search("test_user", "テストクエリ")

        # Noneが返されることを確認
        self.assertIsNone(result)

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_add_knowledge_success(self, mock_post):
        """ナレッジ追加成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # ナレッジを追加（例外が発生しないことを確認）
        await self.client.add_knowledge("test_user", "新しい知識")

        # APIが呼ばれることを確認
        mock_post.assert_called_once()

    @patch('memory_client.httpx.AsyncClient.post')
    async def test_create_summary_success(self, mock_post):
        """要約生成成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 要約を生成（例外が発生しないことを確認）
        await self.client.create_summary("test_user", "test_session")

        # APIが呼ばれることを確認
        mock_post.assert_called_once()

    async def test_close(self):
        """クライアント終了のテスト"""
        # closeメソッドをモック
        self.client.client.aclose = AsyncMock()

        # クライアントを終了
        await self.client.close()

        # acloseが呼ばれることを確認
        self.client.client.aclose.assert_called_once()


class TestChatMemoryClientIntegration(unittest.IsolatedAsyncioTestCase):
    """ChatMemoryClient の非同期統合テストクラス"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.client = ChatMemoryClient("http://localhost:55602")

    async def asyncTearDown(self):
        """非同期クリーンアップ"""
        await self.client.close()

    async def test_concurrent_enqueue(self):
        """並行メッセージエンキューのテスト"""
        import asyncio
        
        # 複数のメッセージを並行してエンキュー
        tasks = []
        for i in range(5):
            request = MagicMock()
            request.text = f"メッセージ{i}"
            request.session_id = "test_session"
            request.user_id = "test_user"
            request.metadata = {}

            response = MagicMock()
            response.text = f"レスポンス{i}"

            task = asyncio.create_task(self.client.enqueue_messages(request, response))
            tasks.append(task)

        # すべてのタスクを完了
        await asyncio.gather(*tasks)

        # 正しい数のメッセージがキューに追加されることを確認
        self.assertEqual(len(self.client._message_queue), 10)  # 5 * 2 (user + assistant)

    async def test_message_queue_management(self):
        """メッセージキュー管理のテスト"""
        # メッセージを追加
        request = MagicMock()
        request.text = "テストメッセージ"
        request.session_id = "test_session"
        request.user_id = "test_user"
        request.metadata = {}

        response = MagicMock()
        response.text = "テストレスポンス"

        await self.client.enqueue_messages(request, response)
        
        # キューにメッセージが追加されることを確認
        self.assertEqual(len(self.client._message_queue), 2)
        
        # キューを手動でクリア
        async with self.client._queue_lock:
            self.client._message_queue.clear()
        
        # キューが空になることを確認
        self.assertEqual(len(self.client._message_queue), 0)


if __name__ == '__main__':
    unittest.main()