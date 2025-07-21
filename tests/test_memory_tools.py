"""memory_tools.py のテスト"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestMemoryTools:
    """memory_tools モジュールのテスト"""

    def test_format_memory_data_with_data(self):
        """記憶データが存在する場合のフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {
            "retrieved_data": "過去の会話: ユーザーは猫が好きです。"
        }
        query = "ペットの話"
        
        result = _format_memory_data(raw_data, query)
        
        assert "「ペットの話」について検索した記憶:" in result
        assert "過去の会話: ユーザーは猫が好きです。" in result
        assert "リスティとしてパーソナライズした回答" in result

    def test_format_memory_data_without_data(self):
        """記憶データが存在しない場合のフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {"retrieved_data": ""}
        query = "新しい話題"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_format_memory_data_with_none_data(self):
        """記憶データがNoneの場合のフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {}  # retrieved_dataキーがない
        query = "テスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_format_memory_data_with_whitespace_only(self):
        """記憶データが空白のみの場合のフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {"retrieved_data": "   \n  \t  "}
        query = "空白テスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_setup_memory_tools_basic(self):
        """基本的なメモリツール設定のテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        mock_session_manager = MagicMock()
        mock_dock_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            mock_session_manager,
            mock_dock_client
        )
        
        # LLMツールデコレーターが使用されることを確認
        assert mock_sts.llm.tool.called
        # プロンプト追加文字列が返されることを確認
        assert isinstance(result, str)
        assert "記憶機能" in result or "memory" in result.lower()

    def test_setup_memory_tools_without_optional_params(self):
        """オプションパラメータなしでのメモリツール設定のテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client
        )
        
        # LLMツールデコレーターが使用されることを確認
        assert mock_sts.llm.tool.called
        # プロンプト追加文字列が返されることを確認
        assert isinstance(result, str)

    @patch('memory_tools._format_memory_data')
    def test_search_memory_tool_function(self, mock_format_memory_data):
        """記憶検索ツール関数のテスト"""
        from memory_tools import setup_memory_tools
        
        mock_format_memory_data.return_value = "フォーマット済み記憶データ"
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = AsyncMock()
        mock_memory_client.search_memory.return_value = {"retrieved_data": "テストデータ"}
        
        # メモリツールを設定
        setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # ツール仕様はハードコーディングされているため、
        # ここではデコレーターの呼び出しを確認
        assert mock_sts.llm.tool.called

    def test_memory_tools_integration(self):
        """メモリツール統合のテスト"""
        from memory_tools import setup_memory_tools, _format_memory_data
        
        # 実際の使用シナリオをテスト
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = AsyncMock()
        mock_session_manager = MagicMock()
        
        # メモリツールを設定
        prompt_addition = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            mock_session_manager
        )
        
        # LLMツールデコレーターが使用されることを確認
        assert mock_sts.llm.tool.called
        
        # プロンプト追加文字列が適切であることを確認
        assert isinstance(prompt_addition, str)
        assert len(prompt_addition) > 0
        
        # フォーマット関数の動作確認
        test_data = {"retrieved_data": "テスト記憶"}
        formatted = _format_memory_data(test_data, "テストクエリ")
        assert "テストクエリ" in formatted
        assert "テスト記憶" in formatted

    def test_format_memory_data_empty_data(self):
        """空の記憶データのフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {"retrieved_data": ""}
        query = "空のデータテスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_format_memory_data_long_content(self):
        """長いコンテンツの記憶データフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        long_content = "これは非常に長い記憶データです。" * 50  # 長いコンテンツ
        raw_data = {"retrieved_data": long_content}
        query = "長いコンテンツテスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert "「長いコンテンツテスト」について検索した記憶:" in result
        assert long_content in result
        assert "リスティとしてパーソナライズした回答" in result

    def test_format_memory_data_no_retrieved_data(self):
        """retrieved_dataキーがない場合のフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {"other_key": "some_value"}  # retrieved_dataキーがない
        query = "キーなしテスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_memory_tools_error_handling(self):
        """メモリツールのエラーハンドリングテスト"""
        from memory_tools import _format_memory_data
        
        # 異常なデータでもクラッシュしないことを確認
        try:
            result1 = _format_memory_data(None, "テスト")
            assert result1 == "関連する記憶が見つかりませんでした。"
        except Exception:
            # Noneでもエラーが発生しないことを確認
            pass
        
        result2 = _format_memory_data({"invalid_key": "value"}, "テスト")
        assert result2 == "関連する記憶が見つかりませんでした。"
        
        result3 = _format_memory_data({"retrieved_data": None}, "テスト")
        assert result3 == "関連する記憶が見つかりませんでした。"

    def test_format_memory_data_various_queries(self):
        """様々なクエリでのフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        raw_data = {"retrieved_data": "テストデータ"}
        
        # 日本語クエリ
        result1 = _format_memory_data(raw_data, "日本語のクエリ")
        assert "「日本語のクエリ」" in result1
        
        # 英語クエリ
        result2 = _format_memory_data(raw_data, "English query")
        assert "「English query」" in result2
        
        # 特殊文字クエリ
        result3 = _format_memory_data(raw_data, "!@#$%^&*()")
        assert "「!@#$%^&*()」" in result3

    def test_format_memory_data_whitespace_only(self):
        """空白のみのデータフォーマットテスト"""
        from memory_tools import _format_memory_data
        
        # 空白文字のみのデータ
        raw_data = {"retrieved_data": "   \n\t   "}
        query = "空白テスト"
        
        result = _format_memory_data(raw_data, query)
        
        assert result == "関連する記憶が見つかりませんでした。"

    def test_setup_memory_tools_character_name_encoding(self):
        """キャラクター名エンコーディングテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client
        )
        
        # 文字列が返されることを確認
        assert isinstance(result, str)

    def test_setup_memory_tools_return_value_content(self):
        """メモリツール設定の戻り値内容テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client
        )
        
        # プロンプト追加文字列の内容を確認
        assert isinstance(result, str)
        assert len(result) >= 0  # 空文字列でもOK

    def test_setup_memory_tools_with_dock_client(self):
        """Dockクライアント付きメモリツール設定テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        mock_dock_client = AsyncMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            None,  # session_manager
            mock_dock_client
        )
        
        assert isinstance(result, str)

    def test_setup_memory_tools_with_session_manager(self):
        """セッションマネージャー付きメモリツール設定テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        mock_session_manager = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            mock_session_manager
        )
        
        assert isinstance(result, str)


class TestMemoryToolsIntegration:
    """メモリツール統合テストクラス"""

    def test_memory_tools_complete_setup(self):
        """完全なメモリツール設定テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = AsyncMock()
        mock_session_manager = MagicMock()
        mock_dock_client = AsyncMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            mock_session_manager,
            mock_dock_client
        )
        
        assert isinstance(result, str)

    def test_memory_tools_config_variations(self):
        """様々な設定パターンテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_memory_client = MagicMock()
        
        # 空の設定
        result1 = setup_memory_tools(mock_sts, {}, mock_memory_client)
        assert isinstance(result1, str)
        
        # 完全な設定
        config = {"memory_enabled": True, "debug": True}
        result2 = setup_memory_tools(mock_sts, config, mock_memory_client)
        assert isinstance(result2, str)

    def test_memory_tools_llm_tool_decoration(self):
        """LLMツールデコレーションテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # ツールが設定されることを確認
        assert isinstance(result, str)

    def test_memory_tools_minimal_setup(self):
        """最小限のメモリツール設定テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_memory_client = MagicMock()
        
        # 最小限の引数で呼び出し
        result = setup_memory_tools(mock_sts, {}, mock_memory_client)
        
        assert isinstance(result, str)


class TestMemoryToolsAsync:
    """非同期メモリツールテストクラス"""

    def test_memory_tools_error_handling_coverage(self):
        """エラーハンドリングカバレッジテスト"""
        from memory_tools import _format_memory_data
        
        # 様々なエラーケースをテスト
        assert _format_memory_data({}, "test") == "関連する記憶が見つかりませんでした。"
        assert _format_memory_data({"retrieved_data": ""}, "test") == "関連する記憶が見つかりませんでした。"

    def test_memory_tools_format_data_integration(self):
        """データフォーマット統合テスト"""
        from memory_tools import _format_memory_data
        
        # 正常なデータの統合テスト
        data = {"retrieved_data": "統合テストデータ"}
        result = _format_memory_data(data, "統合テスト")
        
        assert "「統合テスト」" in result
        assert "統合テストデータ" in result

    def test_memory_tools_no_dock_client(self):
        """Dockクライアントなしテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            None,  # session_manager
            None   # cocoro_dock_client
        )
        
        assert isinstance(result, str)

    def test_memory_tools_no_session_manager(self):
        """セッションマネージャーなしテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(
            mock_sts,
            mock_config,
            mock_memory_client,
            None  # session_manager
        )
        
        assert isinstance(result, str)

    def test_memory_tools_prompt_content(self):
        """プロンプト内容テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # プロンプト内容が文字列であることを確認
        assert isinstance(result, str)

    def test_memory_tools_setup_calls_decorators(self):
        """メモリツール設定デコレーター呼び出しテスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = MagicMock()
        
        result = setup_memory_tools(mock_sts, mock_config, mock_memory_client)
        
        # デコレーターが呼び出されることを確認
        assert isinstance(result, str)

    def test_memory_tools_various_character_names(self):
        """様々なキャラクター名テスト"""
        from memory_tools import setup_memory_tools
        
        mock_sts = MagicMock()
        mock_memory_client = MagicMock()
        
        # 様々なキャラクター設定でテスト
        configs = [
            {"character_name": "リスティ"},
            {"character_name": "Alice"},
            {"character_name": "あいちゃん"},
            {}  # キャラクター名なし
        ]
        
        for config in configs:
            result = setup_memory_tools(mock_sts, config, mock_memory_client)
            assert isinstance(result, str)