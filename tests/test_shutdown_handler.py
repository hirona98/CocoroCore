"""shutdown_handler.py のユニットテスト"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shutdown_handler import ShutdownHandler, shutdown_handler


class TestShutdownHandler(unittest.IsolatedAsyncioTestCase):
    """ShutdownHandler のテストクラス"""

    async def asyncSetUp(self):
        """非同期セットアップ"""
        self.handler = ShutdownHandler()

    def test_init(self):
        """初期化のテスト"""
        handler = ShutdownHandler()
        self.assertFalse(handler.shutdown_event.is_set())
        self.assertEqual(handler.grace_period, 30)
        self.assertEqual(len(handler._shutdown_tasks), 0)

    def test_request_shutdown_default_grace_period(self):
        """デフォルト猶予期間でのシャットダウンリクエストテスト"""
        self.handler.request_shutdown()
        
        self.assertTrue(self.handler.shutdown_event.is_set())
        self.assertEqual(self.handler.grace_period, 30)

    def test_request_shutdown_custom_grace_period(self):
        """カスタム猶予期間でのシャットダウンリクエストテスト"""
        self.handler.request_shutdown(grace_period=10)
        
        self.assertTrue(self.handler.shutdown_event.is_set())
        self.assertEqual(self.handler.grace_period, 10)

    def test_request_shutdown_zero_grace_period(self):
        """猶予期間0でのシャットダウンリクエストテスト"""
        self.handler.request_shutdown(grace_period=0)
        
        self.assertTrue(self.handler.shutdown_event.is_set())
        self.assertEqual(self.handler.grace_period, 0)

    async def test_wait_for_shutdown(self):
        """シャットダウン待機のテスト"""
        # バックグラウンドでシャットダウンをリクエスト
        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            self.handler.request_shutdown()
        
        # 同時実行
        task = asyncio.create_task(trigger_shutdown())
        await self.handler.wait_for_shutdown()
        await task
        
        # シャットダウンイベントが設定されていることを確認
        self.assertTrue(self.handler.shutdown_event.is_set())

    def test_register_cleanup_task_with_name(self):
        """名前付きクリーンアップタスク登録のテスト"""
        async def dummy_cleanup():
            pass
        
        self.handler.register_cleanup_task(dummy_cleanup, "テストクリーンアップ")
        
        self.assertEqual(len(self.handler._shutdown_tasks), 1)
        task_func, task_name = self.handler._shutdown_tasks[0]
        self.assertEqual(task_func, dummy_cleanup)
        self.assertEqual(task_name, "テストクリーンアップ")

    def test_register_cleanup_task_without_name(self):
        """名前なしクリーンアップタスク登録のテスト"""
        async def another_cleanup():
            pass
        
        self.handler.register_cleanup_task(another_cleanup)
        
        self.assertEqual(len(self.handler._shutdown_tasks), 1)
        task_func, task_name = self.handler._shutdown_tasks[0]
        self.assertEqual(task_func, another_cleanup)
        self.assertEqual(task_name, "")

    def test_register_multiple_cleanup_tasks(self):
        """複数クリーンアップタスク登録のテスト"""
        async def task1():
            pass
        
        async def task2():
            pass
        
        self.handler.register_cleanup_task(task1, "タスク1")
        self.handler.register_cleanup_task(task2, "タスク2")
        
        self.assertEqual(len(self.handler._shutdown_tasks), 2)

    @patch('shutdown_handler.asyncio.sleep')
    async def test_execute_shutdown_with_grace_period(self, mock_sleep):
        """猶予期間ありでのシャットダウン実行テスト"""
        # 短い猶予期間を設定
        self.handler.grace_period = 3
        
        # クリーンアップタスクを登録
        cleanup_called = False
        
        async def test_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
        
        self.handler.register_cleanup_task(test_cleanup, "テストクリーンアップ")
        
        # シャットダウン実行
        await self.handler.execute_shutdown()
        
        # sleepが呼ばれたことを確認
        mock_sleep.assert_called()
        
        # クリーンアップタスクが実行されたことを確認
        self.assertTrue(cleanup_called)

    @patch('shutdown_handler.asyncio.sleep')
    async def test_execute_shutdown_zero_grace_period(self, mock_sleep):
        """猶予期間0でのシャットダウン実行テスト"""
        self.handler.grace_period = 0
        
        cleanup_called = False
        
        async def test_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
        
        self.handler.register_cleanup_task(test_cleanup)
        
        # シャットダウン実行
        await self.handler.execute_shutdown()
        
        # 猶予期間がないのでsleepは呼ばれない
        mock_sleep.assert_not_called()
        
        # クリーンアップタスクは実行される
        self.assertTrue(cleanup_called)

    @patch('shutdown_handler.asyncio.sleep')
    async def test_execute_shutdown_with_failing_cleanup(self, mock_sleep):
        """クリーンアップタスクが失敗する場合のテスト"""
        self.handler.grace_period = 0
        
        success_called = False
        
        async def failing_cleanup():
            raise Exception("クリーンアップエラー")
        
        async def success_cleanup():
            nonlocal success_called
            success_called = True
        
        # 失敗するタスクと成功するタスクを登録
        self.handler.register_cleanup_task(failing_cleanup, "失敗タスク")
        self.handler.register_cleanup_task(success_cleanup, "成功タスク")
        
        # シャットダウン実行（例外が発生しないことを確認）
        await self.handler.execute_shutdown()
        
        # 成功するタスクは実行されることを確認
        self.assertTrue(success_called)

    @patch('shutdown_handler.asyncio.sleep')
    async def test_execute_shutdown_multiple_tasks(self, mock_sleep):
        """複数クリーンアップタスクの実行順序テスト"""
        self.handler.grace_period = 0
        
        execution_order = []
        
        async def task1():
            execution_order.append("task1")
        
        async def task2():
            execution_order.append("task2")
        
        async def task3():
            execution_order.append("task3")
        
        # タスクを順番に登録
        self.handler.register_cleanup_task(task1, "タスク1")
        self.handler.register_cleanup_task(task2, "タスク2")
        self.handler.register_cleanup_task(task3, "タスク3")
        
        # シャットダウン実行
        await self.handler.execute_shutdown()
        
        # 登録順に実行されることを確認
        self.assertEqual(execution_order, ["task1", "task2", "task3"])

    @patch('shutdown_handler.logger')
    async def test_execute_shutdown_logging(self, mock_logger):
        """シャットダウン時のログ出力テスト"""
        self.handler.grace_period = 0
        
        async def test_cleanup():
            pass
        
        self.handler.register_cleanup_task(test_cleanup, "ログテスト")
        
        # シャットダウン実行
        await self.handler.execute_shutdown()
        
        # 適切なログが出力されることを確認
        mock_logger.info.assert_any_call("シャットダウン処理を開始します")
        mock_logger.info.assert_any_call("クリーンアップタスクを実行: ログテスト")
        mock_logger.info.assert_any_call("シャットダウン処理が完了しました")

    @patch('shutdown_handler.logger')
    async def test_execute_shutdown_error_logging(self, mock_logger):
        """クリーンアップエラー時のログ出力テスト"""
        self.handler.grace_period = 0
        
        async def failing_cleanup():
            raise ValueError("テストエラー")
        
        self.handler.register_cleanup_task(failing_cleanup, "エラータスク")
        
        # シャットダウン実行
        await self.handler.execute_shutdown()
        
        # エラーログが出力されることを確認
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        self.assertIn("クリーンアップタスクでエラー", error_call)
        self.assertIn("エラータスク", error_call)

    @patch('shutdown_handler.asyncio.sleep')
    async def test_execute_shutdown_grace_period_countdown(self, mock_sleep):
        """猶予期間カウントダウンのテスト"""
        self.handler.grace_period = 12  # 12秒に設定
        
        await self.handler.execute_shutdown()
        
        # sleepが適切に呼ばれることを確認
        # 12秒: 5秒スリープ → 7秒: 5秒スリープ → 2秒: 2秒スリープ
        expected_calls = [unittest.mock.call(5), unittest.mock.call(5), unittest.mock.call(2)]
        mock_sleep.assert_has_calls(expected_calls)


class TestGlobalShutdownHandler(unittest.TestCase):
    """グローバルshutdown_handlerのテスト"""

    def test_global_instance_exists(self):
        """グローバルインスタンスが存在することのテスト"""
        self.assertIsInstance(shutdown_handler, ShutdownHandler)

    def test_global_instance_initial_state(self):
        """グローバルインスタンスの初期状態テスト"""
        # 新しいインスタンスと比較（グローバルインスタンスが変更されている可能性があるため）
        fresh_handler = ShutdownHandler()
        
        # 基本的な初期化が正しく行われていることを確認
        self.assertEqual(type(shutdown_handler), type(fresh_handler))
        self.assertIsInstance(shutdown_handler.shutdown_event, asyncio.Event)
        self.assertIsInstance(shutdown_handler._shutdown_tasks, list)


class TestShutdownHandlerIntegration(unittest.IsolatedAsyncioTestCase):
    """ShutdownHandler の統合テストクラス"""

    async def test_full_shutdown_cycle(self):
        """完全なシャットダウンサイクルのテスト"""
        handler = ShutdownHandler()
        handler.grace_period = 1  # 短い猶予期間
        
        cleanup_results = []
        
        async def database_cleanup():
            cleanup_results.append("database")
            await asyncio.sleep(0.1)
        
        async def cache_cleanup():
            cleanup_results.append("cache")
            await asyncio.sleep(0.1)
        
        async def network_cleanup():
            cleanup_results.append("network")
        
        # クリーンアップタスクを登録
        handler.register_cleanup_task(database_cleanup, "データベース")
        handler.register_cleanup_task(cache_cleanup, "キャッシュ")
        handler.register_cleanup_task(network_cleanup, "ネットワーク")
        
        # シャットダウンサイクルを実行
        handler.request_shutdown(grace_period=0)  # 即座に実行
        await handler.execute_shutdown()
        
        # すべてのクリーンアップが実行されたことを確認
        self.assertEqual(cleanup_results, ["database", "cache", "network"])

    async def test_concurrent_shutdown_requests(self):
        """並行シャットダウンリクエストのテスト"""
        handler = ShutdownHandler()
        
        # 複数の並行リクエスト
        handler.request_shutdown(grace_period=5)
        handler.request_shutdown(grace_period=3)  # より短い猶予期間で上書き
        handler.request_shutdown(grace_period=10)  # より長い猶予期間で上書き
        
        # 最後の設定が有効であることを確認
        self.assertEqual(handler.grace_period, 10)
        self.assertTrue(handler.shutdown_event.is_set())


if __name__ == '__main__':
    unittest.main()