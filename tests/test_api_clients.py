"""api_clients.py のユニットテスト"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
import httpx
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api_clients import CocoroDockClient, CocoroShellClient


class TestCocoroDockClient(unittest.IsolatedAsyncioTestCase):
    """CocoroDockClient のテストクラス"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.client = CocoroDockClient()

    async def asyncTearDown(self):
        """非同期クリーンアップ"""
        await self.client.close()

    def test_init_default(self):
        """デフォルト初期化のテスト"""
        client = CocoroDockClient()
        self.assertEqual(client.base_url, "http://127.0.0.1:55600")

    def test_init_custom_url(self):
        """カスタムURL初期化のテスト"""
        client = CocoroDockClient("http://localhost:8080", timeout=60.0)
        self.assertEqual(client.base_url, "http://localhost:8080")

    def test_init_strips_trailing_slash(self):
        """base_urlの末尾スラッシュ除去のテスト"""
        client = CocoroDockClient("http://localhost:55600/")
        self.assertEqual(client.base_url, "http://localhost:55600")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_message_success(self, mock_post):
        """チャットメッセージ送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # メッセージを送信
        result = await self.client.send_chat_message("user", "テストメッセージ")

        # 成功することを確認
        self.assertTrue(result)
        mock_post.assert_called_once()
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['role'], "user")
        self.assertEqual(payload['content'], "テストメッセージ")
        self.assertIn('timestamp', payload)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_message_connect_error(self, mock_post):
        """接続エラーの場合のテスト"""
        # 接続エラーを設定
        mock_post.side_effect = httpx.ConnectError("Connection failed")

        # メッセージを送信（失敗するはず）
        result = await self.client.send_chat_message("assistant", "レスポンス")

        # 失敗するが例外は発生しないことを確認
        self.assertFalse(result)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_message_http_error(self, mock_post):
        """HTTPエラーの場合のテスト"""
        # HTTPエラーを設定
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP Error", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        # メッセージを送信（失敗するはず）
        result = await self.client.send_chat_message("user", "エラーテスト")

        # 失敗することを確認
        self.assertFalse(result)

    @patch('api_clients.httpx.AsyncClient.get')
    async def test_get_config_success(self, mock_get):
        """設定取得成功のテスト"""
        # モックレスポンスを設定
        test_config = {"CharacterName": "TestChar", "LLMProvider": "openai"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = test_config
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 設定を取得
        config = await self.client.get_config()

        # 結果を確認
        self.assertEqual(config, test_config)
        mock_get.assert_called_once_with(f"{self.client.base_url}/api/config")

    @patch('api_clients.httpx.AsyncClient.get')
    async def test_get_config_failure(self, mock_get):
        """設定取得失敗のテスト"""
        # 接続エラーを設定
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        # 設定を取得（失敗するはず）
        config = await self.client.get_config()

        # Noneが返されることを確認
        self.assertIsNone(config)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_control_command_success(self, mock_post):
        """制御コマンド送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 制御コマンドを送信
        result = await self.client.send_control_command("shutdown")

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['command'], "shutdown")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_status_update_success(self, mock_post):
        """ステータス更新送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # ステータス更新を送信
        result = await self.client.send_status_update("処理中", "processing")

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['message'], "処理中")
        self.assertEqual(payload['type'], "processing")

    async def test_close(self):
        """クライアント終了のテスト"""
        # closeメソッドをモック
        self.client.client.aclose = AsyncMock()

        # クライアントを終了
        await self.client.close()

        # acloseが呼ばれることを確認
        self.client.client.aclose.assert_called_once()


class TestCocoroShellClient(unittest.IsolatedAsyncioTestCase):
    """CocoroShellClient のテストクラス"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.client = CocoroShellClient()

    async def asyncTearDown(self):
        """非同期クリーンアップ"""
        await self.client.close()

    def test_init_default(self):
        """デフォルト初期化のテスト"""
        client = CocoroShellClient()
        self.assertEqual(client.base_url, "http://127.0.0.1:55605")

    def test_init_custom_url(self):
        """カスタムURL初期化のテスト"""
        client = CocoroShellClient("http://localhost:8080")
        self.assertEqual(client.base_url, "http://localhost:8080")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_for_speech_success(self, mock_post):
        """音声合成付きチャットメッセージ送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # メッセージを送信
        result = await self.client.send_chat_for_speech("テストメッセージ", character_name="TestCharacter")

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['content'], "テストメッセージ")
        self.assertEqual(payload['character_name'], "TestCharacter")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_for_speech_with_voice_params(self, mock_post):
        """音声パラメータ付きチャットメッセージ送信のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 音声パラメータ付きでメッセージを送信
        voice_params = {"speaker_id": 1, "speed": 1.2}
        result = await self.client.send_chat_for_speech(
            "音声テスト", 
            voice_params=voice_params,
            animation="talk",
            character_name="TestCharacter"
        )

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['voice_params'], voice_params)
        self.assertEqual(payload['animation'], "talk")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_chat_for_speech_connect_error(self, mock_post):
        """接続エラーの場合のテスト"""
        # 接続エラーを設定
        mock_post.side_effect = httpx.ConnectError("Connection failed")

        # メッセージを送信（失敗するはず）
        result = await self.client.send_chat_for_speech("エラーテスト", character_name="TestCharacter")

        # 失敗するが例外は発生しないことを確認
        self.assertFalse(result)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_animation_success(self, mock_post):
        """アニメーション送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # アニメーションを送信
        result = await self.client.send_animation("wave")

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['animation_name'], "wave")

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_animation_failure(self, mock_post):
        """アニメーション送信失敗のテスト"""
        # HTTPエラーを設定
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "HTTP Error", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        # アニメーションを送信（失敗するはず）
        result = await self.client.send_animation("invalid")

        # 失敗することを確認
        self.assertFalse(result)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_send_control_command_success(self, mock_post):
        """制御コマンド送信成功のテスト"""
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 制御コマンドを送信
        result = await self.client.send_control_command("show")

        # 成功することを確認
        self.assertTrue(result)
        
        # 送信されたペイロードを確認
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['command'], "show")

    async def test_close(self):
        """クライアント終了のテスト"""
        # closeメソッドをモック
        self.client.client.aclose = AsyncMock()

        # クライアントを終了
        await self.client.close()

        # acloseが呼ばれることを確認
        self.client.client.aclose.assert_called_once()


class TestAPIClientsIntegration(unittest.IsolatedAsyncioTestCase):
    """API クライアントの統合テスト"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.dock_client = CocoroDockClient()
        self.shell_client = CocoroShellClient()

    async def asyncTearDown(self):
        """非同期クリーンアップ"""
        await self.dock_client.close()
        await self.shell_client.close()

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_concurrent_message_sending(self, mock_post):
        """並行メッセージ送信のテスト"""
        import asyncio
        # モックレスポンスを設定
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 複数のメッセージを並行して送信
        tasks = []
        for i in range(3):
            tasks.append(self.dock_client.send_chat_message("user", f"メッセージ{i}"))
            tasks.append(self.shell_client.send_chat_for_speech(f"レスポンス{i}", character_name="TestCharacter"))

        results = await asyncio.gather(*tasks)

        # すべて成功することを確認
        self.assertTrue(all(results))
        # 6回の呼び出しがあることを確認（Dock 3回 + Shell 3回）
        self.assertEqual(mock_post.call_count, 6)

    @patch('api_clients.httpx.AsyncClient.post')
    async def test_error_handling_robustness(self, mock_post):
        """エラーハンドリングの堅牢性テスト"""
        import asyncio
        # 一部のリクエストで例外を発生させる
        def side_effect(*args, **kwargs):
            if "error" in str(kwargs.get('json', {})):
                raise httpx.ConnectError("Simulated error")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_post.side_effect = side_effect

        # エラーを含む混合リクエスト
        results = await asyncio.gather(
            self.dock_client.send_chat_message("user", "正常メッセージ"),
            self.shell_client.send_chat_for_speech("エラーメッセージ", character_name="Error"),
            self.dock_client.send_chat_message("user", "正常メッセージ2"),
            return_exceptions=True
        )

        # エラーがあっても他の処理は継続されることを確認
        self.assertIsInstance(results[0], bool)
        self.assertIsInstance(results[1], bool)
        self.assertIsInstance(results[2], bool)

    async def test_client_configuration_consistency(self):
        """クライアント設定の一貫性テスト"""
        # カスタム設定でクライアントを作成
        custom_dock = CocoroDockClient("http://test:5000", timeout=45.0)
        custom_shell = CocoroShellClient("http://test:5001")

        # 設定が正しく反映されることを確認
        self.assertEqual(custom_dock.base_url, "http://test:5000")
        self.assertEqual(custom_shell.base_url, "http://test:5001")

        # クリーンアップ
        await custom_dock.close()
        await custom_shell.close()


if __name__ == '__main__':
    unittest.main()