"""session_manager.py のユニットテスト"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from session_manager import SessionManager


class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    """SessionManager のテストクラス"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.session_manager = SessionManager(timeout_seconds=300, max_sessions=5)

    def test_init(self):
        """初期化のテスト"""
        manager = SessionManager(timeout_seconds=600, max_sessions=100)
        self.assertEqual(manager.timeout_seconds, 600)
        self.assertEqual(manager.max_sessions, 100)
        self.assertEqual(len(manager.sessions), 0)

    def test_default_init(self):
        """デフォルト引数での初期化のテスト"""
        manager = SessionManager()
        self.assertEqual(manager.timeout_seconds, 300)
        self.assertEqual(manager.max_sessions, 1000)

    async def test_update_activity_basic(self):
        """基本的なアクティビティ更新のテスト"""
        user_id = "test_user"
        session_id = "test_session"
        
        # アクティビティを更新
        await self.session_manager.update_activity(user_id, session_id)
        
        # セッションが追加されることを確認
        session_key = f"{user_id}:{session_id}"
        self.assertIn(session_key, self.session_manager.sessions)

    async def test_update_activity_multiple_users(self):
        """複数ユーザーのアクティビティ更新のテスト"""
        # 異なるユーザーのセッションを作成
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        await self.session_manager.update_activity("user1", "session3")
        
        # 3つのセッションが作成されることを確認
        self.assertEqual(len(self.session_manager.sessions), 3)
        self.assertIn("user1:session1", self.session_manager.sessions)
        self.assertIn("user2:session2", self.session_manager.sessions)
        self.assertIn("user1:session3", self.session_manager.sessions)

    async def test_update_activity_same_session(self):
        """同じセッションの再更新のテスト"""
        user_id = "test_user"
        session_id = "test_session"
        
        # 最初の更新
        await self.session_manager.update_activity(user_id, session_id)
        first_time = self.session_manager.sessions[f"{user_id}:{session_id}"]
        
        # 少し待ってから再更新
        await asyncio.sleep(0.01)
        await self.session_manager.update_activity(user_id, session_id)
        second_time = self.session_manager.sessions[f"{user_id}:{session_id}"]
        
        # 時間が更新されることを確認
        self.assertGreater(second_time, first_time)
        self.assertEqual(len(self.session_manager.sessions), 1)

    async def test_max_sessions_limit(self):
        """最大セッション数制限のテスト"""
        # 最大セッション数まで追加
        for i in range(5):
            await self.session_manager.update_activity(f"user{i}", f"session{i}")
        
        self.assertEqual(len(self.session_manager.sessions), 5)
        
        # さらにセッションを追加（古いものが削除されるはず）
        await self.session_manager.update_activity("new_user", "new_session")
        
        # セッション数が最大数を超えないことを確認
        self.assertEqual(len(self.session_manager.sessions), 5)
        self.assertIn("new_user:new_session", self.session_manager.sessions)

    async def test_get_timed_out_sessions_no_timeout(self):
        """タイムアウトなしの場合のテスト"""
        # 新しいセッションを作成
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        
        # タイムアウトしたセッションを取得
        timed_out = await self.session_manager.get_timed_out_sessions()
        
        # タイムアウトしたセッションがないことを確認
        self.assertEqual(len(timed_out), 0)
        self.assertEqual(len(self.session_manager.sessions), 2)

    async def test_get_timed_out_sessions_with_timeout(self):
        """タイムアウトありの場合のテスト"""
        # 短いタイムアウト時間でセッションマネージャーを作成
        short_timeout_manager = SessionManager(timeout_seconds=1)
        
        # セッションを作成
        await short_timeout_manager.update_activity("user1", "session1")
        await short_timeout_manager.update_activity("user2", "session2")
        
        # 過去の時間にセッションを設定（タイムアウトをシミュレート）
        past_time = datetime.now() - timedelta(seconds=2)
        short_timeout_manager.sessions["user1:session1"] = past_time
        
        # タイムアウトしたセッションを取得
        timed_out = await short_timeout_manager.get_timed_out_sessions()
        
        # タイムアウトしたセッションが取得されることを確認
        self.assertIn("user1:session1", timed_out)
        self.assertEqual(len(timed_out), 1)
        
        # タイムアウトしたセッションが削除されることを確認
        self.assertNotIn("user1:session1", short_timeout_manager.sessions)
        self.assertIn("user2:session2", short_timeout_manager.sessions)

    async def test_get_active_session_count(self):
        """アクティブセッション数取得のテスト"""
        # 初期状態
        count = self.session_manager.get_active_session_count()
        self.assertEqual(count, 0)
        
        # セッションを追加
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        
        count = self.session_manager.get_active_session_count()
        self.assertEqual(count, 2)

    async def test_remove_session(self):
        """セッション削除のテスト"""
        # セッションを作成
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        
        # セッションが存在することを確認
        self.assertEqual(len(self.session_manager.sessions), 2)
        
        # セッションを削除
        await self.session_manager.remove_session("user1", "session1")
        
        # セッションが削除されることを確認
        self.assertEqual(len(self.session_manager.sessions), 1)
        self.assertNotIn("user1:session1", self.session_manager.sessions)
        self.assertIn("user2:session2", self.session_manager.sessions)

    async def test_remove_nonexistent_session(self):
        """存在しないセッションの削除テスト"""
        # 初期状態
        self.assertEqual(len(self.session_manager.sessions), 0)
        
        # 存在しないセッションを削除（例外が発生しないことを確認）
        await self.session_manager.remove_session("nonexistent_user", "nonexistent_session")
        
        # 状態が変わらないことを確認
        self.assertEqual(len(self.session_manager.sessions), 0)

    async def test_get_all_sessions(self):
        """全セッション取得のテスト"""
        # 初期状態
        all_sessions = await self.session_manager.get_all_sessions()
        self.assertEqual(len(all_sessions), 0)
        
        # セッションを追加
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        
        # 全セッションを取得
        all_sessions = await self.session_manager.get_all_sessions()
        self.assertEqual(len(all_sessions), 2)
        self.assertIn("user1:session1", all_sessions)
        self.assertIn("user2:session2", all_sessions)

    async def test_concurrent_access(self):
        """並行アクセスのテスト"""
        # 複数の並行タスクでセッションを更新
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                self.session_manager.update_activity(f"user{i}", f"session{i}")
            )
            tasks.append(task)
        
        # すべてのタスクを完了
        await asyncio.gather(*tasks)
        
        # 最大セッション数（5）に制限されることを確認
        self.assertEqual(len(self.session_manager.sessions), 5)

    @patch('session_manager.datetime')
    async def test_cleanup_old_sessions_with_mock_time(self, mock_datetime):
        """モック時間を使ったセッションクリーンアップのテスト"""
        # 現在時間をモック
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = base_time
        
        # セッションを作成
        await self.session_manager.update_activity("user1", "session1")
        
        # 時間を進める（タイムアウト後）
        future_time = base_time + timedelta(seconds=400)
        mock_datetime.now.return_value = future_time
        
        # タイムアウトしたセッションを取得
        timed_out = await self.session_manager.get_timed_out_sessions()
        
        # セッションがタイムアウトすることを確認
        self.assertIn("user1:session1", timed_out)
        self.assertEqual(len(self.session_manager.sessions), 0)

    async def test_session_timeout_edge_case(self):
        """セッションタイムアウトの境界値テスト"""
        # タイムアウト時間ちょうどでセッションマネージャーを作成
        exact_timeout_manager = SessionManager(timeout_seconds=1)
        
        # セッションを作成
        await exact_timeout_manager.update_activity("user1", "session1")
        
        # タイムアウト時間を少し超えた時間に設定（境界値＋マージン）
        past_time = datetime.now() - timedelta(seconds=1.1)
        exact_timeout_manager.sessions["user1:session1"] = past_time
        
        # タイムアウトしたセッションを取得
        timed_out = await exact_timeout_manager.get_timed_out_sessions()
        
        # タイムアウトすることを確認
        self.assertIn("user1:session1", timed_out)

    async def test_session_key_format(self):
        """セッションキーのフォーマットテスト"""
        user_id = "test@example.com"
        session_id = "session-123-abc"
        
        # 特殊文字を含むIDでセッションを作成
        await self.session_manager.update_activity(user_id, session_id)
        
        # 期待されるセッションキーが生成されることを確認
        expected_key = f"{user_id}:{session_id}"
        self.assertIn(expected_key, self.session_manager.sessions)

    async def test_large_number_of_sessions(self):
        """大量セッションの処理テスト"""
        # 制限を超える数のセッションを作成
        for i in range(20):
            await self.session_manager.update_activity(f"user{i:03d}", f"session{i:03d}")
        
        # 最大数に制限されることを確認
        self.assertEqual(len(self.session_manager.sessions), 5)
        
        # 最新のセッションが保持されることを確認
        self.assertIn("user019:session019", self.session_manager.sessions)


class TestCreateTimeoutChecker(unittest.IsolatedAsyncioTestCase):
    """create_timeout_checker 関数のテストクラス"""

    async def asyncSetUp(self):
        """テストセットアップ"""
        self.session_manager = SessionManager(timeout_seconds=1, max_sessions=5)
        self.mock_memory_client = AsyncMock()

    async def test_create_timeout_checker_basic(self):
        """基本的なタイムアウトチェッカーのテスト"""
        from session_manager import create_timeout_checker
        
        # タイムアウトしたセッションを作成
        await self.session_manager.update_activity("user1", "session1")
        past_time = datetime.now() - timedelta(seconds=2)
        self.session_manager.sessions["user1:session1"] = past_time
        
        # タイムアウトチェッカーを短時間実行
        async def run_checker_briefly():
            try:
                await asyncio.wait_for(
                    create_timeout_checker(self.session_manager, self.mock_memory_client, check_interval=0.1),
                    timeout=0.3
                )
            except asyncio.TimeoutError:
                pass  # 期待される動作
        
        await run_checker_briefly()
        
        # create_summaryが呼ばれることを確認
        self.mock_memory_client.create_summary.assert_called()

    async def test_timeout_checker_session_cleanup(self):
        """タイムアウトチェッカーのセッションクリーンアップテスト"""
        from session_manager import create_timeout_checker
        
        # 複数のセッション（一部タイムアウト）を作成
        await self.session_manager.update_activity("user1", "session1")
        await self.session_manager.update_activity("user2", "session2")
        
        # user1のセッションをタイムアウトさせる
        past_time = datetime.now() - timedelta(seconds=2)
        self.session_manager.sessions["user1:session1"] = past_time
        
        # チェッカーを短時間実行
        async def run_checker_with_cleanup():
            try:
                await asyncio.wait_for(
                    create_timeout_checker(self.session_manager, self.mock_memory_client, check_interval=0.1),
                    timeout=0.25
                )
            except asyncio.TimeoutError:
                pass
        
        await run_checker_with_cleanup()
        
        # タイムアウトしたセッションが削除されることを確認
        self.assertNotIn("user1:session1", self.session_manager.sessions)
        # アクティブなセッションは残ることを確認
        self.assertIn("user2:session2", self.session_manager.sessions)

    async def test_timeout_checker_error_handling(self):
        """タイムアウトチェッカーのエラーハンドリングテスト"""
        from session_manager import create_timeout_checker
        
        # memory_clientでエラーを発生させる
        self.mock_memory_client.create_summary.side_effect = Exception("Test error")
        
        # タイムアウトしたセッションを作成
        await self.session_manager.update_activity("user1", "session1")
        past_time = datetime.now() - timedelta(seconds=2)
        self.session_manager.sessions["user1:session1"] = past_time
        
        # エラーが発生してもチェッカーが継続することを確認
        async def run_checker_with_error():
            try:
                await asyncio.wait_for(
                    create_timeout_checker(self.session_manager, self.mock_memory_client, check_interval=0.1),
                    timeout=0.3
                )
            except asyncio.TimeoutError:
                pass
        
        # 例外が発生しないことを確認
        await run_checker_with_error()

    async def test_timeout_checker_cancellation(self):
        """タイムアウトチェッカーのキャンセルテスト"""
        from session_manager import create_timeout_checker
        
        # チェッカーを開始
        checker_task = asyncio.create_task(
            create_timeout_checker(self.session_manager, self.mock_memory_client, check_interval=1)
        )
        
        # 少し待ってからキャンセル
        await asyncio.sleep(0.1)
        checker_task.cancel()
        
        # CancelledErrorが発生することを確認
        with self.assertRaises(asyncio.CancelledError):
            await checker_task


if __name__ == '__main__':
    unittest.main()