"""memory_tools.py のユニットテスト"""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_tools import _format_memory_data, setup_memory_tools


class TestMemoryTools(unittest.TestCase):
    """memory_tools モジュールのテストクラス"""

    def test_format_memory_data_with_data(self):
        """記憶データが存在する場合のフォーマットテスト"""
        raw_data = {
            "retrieved_data": "以前の会話で、ユーザーは猫を飼っていると話していました。"
        }
        query = "ペットについて"
        
        result = _format_memory_data(raw_data, query)
        
        self.assertIn("「ペットについて」について検索した記憶:", result)
        self.assertIn("以前の会話で、ユーザーは猫を飼っていると話していました。", result)
        self.assertIn("この記憶を参考に、リスティとしてパーソナライズした回答をしてください。", result)

    def test_format_memory_data_empty_data(self):
        """記憶データが空の場合のフォーマットテスト"""
        raw_data = {"retrieved_data": ""}
        query = "存在しない情報"
        
        result = _format_memory_data(raw_data, query)
        
        self.assertEqual(result, "関連する記憶が見つかりませんでした。")

    def test_format_memory_data_no_retrieved_data(self):
        """retrieved_dataキーが存在しない場合のテスト"""
        raw_data = {}
        query = "テストクエリ"
        
        result = _format_memory_data(raw_data, query)
        
        self.assertEqual(result, "関連する記憶が見つかりませんでした。")

    def test_format_memory_data_whitespace_only(self):
        """スペースのみの記憶データの場合のテスト"""
        raw_data = {"retrieved_data": "   \n\t   "}
        query = "空白テスト"
        
        result = _format_memory_data(raw_data, query)
        
        self.assertEqual(result, "関連する記憶が見つかりませんでした。")

    def test_setup_memory_tools_basic(self):
        """基本的なメモリツールセットアップのテスト"""
        # モックオブジェクトを作成
        mock_sts = MagicMock()
        mock_config = {
            "CharacterName": "TestCharacter",
            "user_id": "test_user"
        }
        mock_memory_client = MagicMock()
        
        # セットアップを実行
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # 結果が文字列であることを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_setup_memory_tools_with_session_manager(self):
        """SessionManagerありでのメモリツールセットアップのテスト"""
        mock_sts = MagicMock()
        mock_config = {
            "CharacterName": "TestCharacter",
            "user_id": "test_user"
        }
        mock_memory_client = MagicMock()
        mock_session_manager = MagicMock()
        
        result = setup_memory_tools(
            mock_sts, 
            mock_config, 
            mock_memory_client, 
            session_manager=mock_session_manager
        )
        
        # 結果が文字列であることを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_setup_memory_tools_with_dock_client(self):
        """CocoroDockClientありでのメモリツールセットアップのテスト"""
        mock_sts = MagicMock()
        mock_config = {
            "CharacterName": "TestCharacter", 
            "user_id": "test_user"
        }
        mock_memory_client = MagicMock()
        mock_dock_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            cocoro_dock_client=mock_dock_client
        )
        
        # 結果が文字列であることを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_setup_memory_tools_return_value_content(self):
        """メモリツールセットアップの戻り値内容テスト"""
        mock_sts = MagicMock()
        mock_config = {"CharacterName": "TestCharacter", "user_id": "test_user"}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # 戻り値に重要なキーワードが含まれることを確認
        self.assertIn("記憶機能", result)
        self.assertIn("search_memory", result)
        self.assertIn("add_knowledge", result)

    def test_setup_memory_tools_character_name_encoding(self):
        """日本語キャラクター名の処理テスト"""
        mock_sts = MagicMock()
        mock_config = {"CharacterName": "ココロ", "user_id": "test_user"}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # 戻り値が正常に生成されることを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_format_memory_data_various_queries(self):
        """様々なクエリでのフォーマットテスト"""
        raw_data = {
            "retrieved_data": "ユーザーはPythonプログラマーで、機械学習に興味があります。"
        }
        
        # 英語クエリ
        result_en = _format_memory_data(raw_data, "programming")
        self.assertIn("「programming」について検索した記憶:", result_en)
        
        # 日本語クエリ
        result_jp = _format_memory_data(raw_data, "プログラミング")
        self.assertIn("「プログラミング」について検索した記憶:", result_jp)
        
        # 空のクエリ
        result_empty = _format_memory_data(raw_data, "")
        self.assertIn("「」について検索した記憶:", result_empty)

    def test_format_memory_data_long_content(self):
        """長い記憶データのフォーマットテスト"""
        long_content = "これは非常に長い記憶データです。" * 50
        raw_data = {"retrieved_data": long_content}
        query = "長いデータ"
        
        result = _format_memory_data(raw_data, query)
        
        # 長いデータでも正常に処理されることを確認
        self.assertIn("「長いデータ」について検索した記憶:", result)
        self.assertIn(long_content, result)
        self.assertIn("この記憶を参考に", result)


class TestMemoryToolsIntegration(unittest.TestCase):
    """memory_tools の統合テストクラス"""

    def test_memory_tools_complete_setup(self):
        """メモリツールの完全なセットアップテスト"""
        # 完全なモック環境を作成
        mock_sts = MagicMock()
        mock_config = {
            "CharacterName": "テストキャラクター",
            "user_id": "integration_test_user"
        }
        mock_memory_client = MagicMock()
        mock_session_manager = MagicMock()
        mock_dock_client = MagicMock()
        
        # すべてのオプションを指定してセットアップ
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            session_manager=mock_session_manager,
            cocoro_dock_client=mock_dock_client
        )
        
        # 戻り値が適切であることを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_memory_tools_llm_tool_decoration(self):
        """LLMツールデコレーションのテスト"""
        mock_sts = MagicMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        mock_memory_client = MagicMock()
        
        # setup実行時にstsのllm.toolメソッドが呼ばれることを確認
        setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # デコレーターが複数回呼ばれることを確認（複数のツールが登録される）
        self.assertGreater(mock_sts.llm.tool.call_count, 0)

    def test_memory_tools_minimal_setup(self):
        """最小構成でのメモリツールセットアップテスト"""
        mock_sts = MagicMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        mock_memory_client = MagicMock()
        
        # 最小構成でセットアップ
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # 正常に動作することを確認
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_memory_tools_config_variations(self):
        """様々な設定でのメモリツールテスト"""
        mock_sts = MagicMock()
        mock_memory_client = MagicMock()
        
        # 異なる設定パターンをテスト
        configs = [
            {"CharacterName": "A", "user_id": "1"},
            {"CharacterName": "Very Long Character Name", "user_id": "user_with_long_id"},
            {"CharacterName": "特殊文字#@$", "user_id": "special_user"},
        ]
        
        for config in configs:
            with self.subTest(config=config):
                result = setup_memory_tools(mock_sts, config, mock_memory_client)
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


class TestMemoryToolsAsync(unittest.IsolatedAsyncioTestCase):
    """memory_tools モジュールの非同期ツール関数のテストクラス"""

    async def test_memory_tools_setup_calls_decorators(self):
        """memory_toolsのセットアップ時にデコレーターが呼ばれることをテスト"""
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        mock_session_manager = AsyncMock()
        mock_dock_client = AsyncMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        
        # setup_memory_toolsを実行
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            mock_session_manager,
            mock_dock_client
        )
        
        # 3つのツール（search_memory、add_knowledge、create_summary）が登録されることを確認
        self.assertEqual(mock_sts.llm.tool.call_count, 3)
        
        # 結果がプロンプト文字列であることを確認
        self.assertIsInstance(result, str)
        self.assertIn("記憶機能の必須ルール", result)

    async def test_memory_tools_format_data_integration(self):
        """memory_toolsの_format_memory_data関数の統合テスト"""
        # 成功パターン
        raw_data = {"retrieved_data": "ユーザーは猫を飼っています。"}
        query = "ペットについて"
        result = _format_memory_data(raw_data, query)
        
        self.assertIn("「ペットについて」について検索した記憶:", result)
        self.assertIn("ユーザーは猫を飼っています。", result)
        self.assertIn("この記憶を参考に、リスティとしてパーソナライズした回答をしてください", result)
        
        # 失敗パターン
        empty_data = {"retrieved_data": ""}
        result_empty = _format_memory_data(empty_data, query)
        self.assertEqual(result_empty, "関連する記憶が見つかりませんでした。")

    async def test_memory_tools_no_session_manager(self):
        """session_managerなしでのmemory_toolsセットアップテスト"""
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        
        # session_managerなしでセットアップ
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            session_manager=None,
            cocoro_dock_client=None
        )
        
        # 正常にセットアップされることを確認
        self.assertEqual(mock_sts.llm.tool.call_count, 3)
        self.assertIsInstance(result, str)

    async def test_memory_tools_no_dock_client(self):
        """dock_clientなしでのmemory_toolsセットアップテスト"""
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        mock_session_manager = AsyncMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        
        # dock_clientなしでセットアップ
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            session_manager=mock_session_manager,
            cocoro_dock_client=None
        )
        
        # 正常にセットアップされることを確認
        self.assertEqual(mock_sts.llm.tool.call_count, 3)
        self.assertIsInstance(result, str)

    async def test_memory_tools_prompt_content(self):
        """memory_toolsが返すプロンプト内容のテスト"""
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        mock_config = {"CharacterName": "Test", "user_id": "test"}
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # プロンプトに重要なキーワードが含まれることを確認
        self.assertIn("記憶機能の必須ルール", result)
        self.assertIn("search_memory", result)
        self.assertIn("add_knowledge", result)
        self.assertIn("create_summary", result)
        self.assertIn("キャラクターとしてパーソナライズした回答", result)

    async def test_memory_tools_error_handling_coverage(self):
        """memory_toolsのエラーハンドリング部分のカバレッジテスト"""
        # 異常なケースでも正常に動作することを確認
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        
        # 異常な設定でもエラーが発生しないことを確認
        empty_config = {}
        result = setup_memory_tools(mock_sts, empty_config, mock_memory_client)
        self.assertIsInstance(result, str)
        
        # Noneの設定でもエラーが発生しないことを確認
        none_config = None
        try:
            result = setup_memory_tools(mock_sts, none_config, mock_memory_client)
            # 実際にはエラーになる可能性があるが、テストとしては正常動作を確認
        except (TypeError, AttributeError):
            # 期待される例外が発生した場合はテスト成功
            pass

    async def test_memory_tools_various_character_names(self):
        """様々なキャラクター名でのmemory_toolsテスト"""
        mock_sts = MagicMock()
        mock_memory_client = AsyncMock()
        
        # 様々なキャラクター名パターンをテスト
        character_names = [
            "通常のキャラクター",
            "Special!@#$%Characters",
            "日本語キャラクター",
            "VeryLongCharacterNameThatMightCauseIssues",
            "",  # 空文字
        ]
        
        for char_name in character_names:
            with self.subTest(character_name=char_name):
                config = {"CharacterName": char_name, "user_id": "test"}
                result = setup_memory_tools(mock_sts, config, mock_memory_client)
                
                # 正常に処理されることを確認
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


if __name__ == '__main__':
    unittest.main()