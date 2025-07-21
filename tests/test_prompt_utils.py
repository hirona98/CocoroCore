"""prompt_utils.py のテスト"""


from unittest.mock import MagicMock, patch

import pytest

from prompt_utils import add_system_prompts


class TestAddSystemPrompts:
    """システムプロンプト追加のテスト"""

    def test_add_system_prompts_basic(self):
        """基本的なシステムプロンプト追加テスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "既存のプロンプト"
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # system_promptが更新されていることを確認
        assert "既存のプロンプト" in mock_llm.system_prompt
        # 新しい内容が追加されていることを確認
        assert len(mock_llm.system_prompt) > len("既存のプロンプト")

    def test_add_system_prompts_with_empty_prompt(self):
        """空のプロンプトへの追加テスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = ""
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # プロンプトが設定されていることを確認
        assert len(mock_llm.system_prompt) > 0

    def test_add_system_prompts_logger_usage(self):
        """ロガーの使用テスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "テストプロンプト"
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # ロガーが使用されていることを確認
        mock_logger.info.assert_called()

    def test_add_system_prompts_content_verification(self):
        """追加される内容の検証テスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "基本プロンプト"
        mock_logger = MagicMock()
        
        original_prompt = mock_llm.system_prompt
        add_system_prompts(mock_llm, mock_logger)
        
        # 元のプロンプトが保持されていることを確認
        assert original_prompt in mock_llm.system_prompt
        
        # システムプロンプトに関連するキーワードが含まれていることを確認
        expected_keywords = [
            "システム",
            "ガイドライン",
            "プロンプト",
            "追加"
        ]
        
        # 少なくともいくつかのキーワードが含まれていることを確認
        found_keywords = sum(1 for keyword in expected_keywords 
                           if keyword in mock_llm.system_prompt)
        assert found_keywords > 0, "期待されるキーワードが含まれていません"

    def test_add_system_prompts_multiple_calls(self):
        """複数回呼び出しテスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "初期プロンプト"
        mock_logger = MagicMock()
        
        # 最初の呼び出し
        add_system_prompts(mock_llm, mock_logger)
        first_result = mock_llm.system_prompt
        
        # 2回目の呼び出し
        add_system_prompts(mock_llm, mock_logger)
        second_result = mock_llm.system_prompt
        
        # 2回目の呼び出しでも適切に処理されることを確認
        assert len(second_result) >= len(first_result)

    def test_add_system_prompts_with_none_logger(self):
        """ロガーがNoneの場合のテスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "テストプロンプト"
        
        # ロガーがNoneの場合、AttributeErrorが発生することを確認
        with pytest.raises(AttributeError):
            add_system_prompts(mock_llm, None)

    def test_add_system_prompts_llm_object_structure(self):
        """LLMオブジェクトの構造テスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "テスト"
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # system_prompt属性がアクセスされていることを確認
        assert hasattr(mock_llm, 'system_prompt')
        
        # system_promptが文字列であることを確認
        assert isinstance(mock_llm.system_prompt, str)


class TestPromptUtilsIntegration:
    """prompt_utils 統合テスト"""

    def test_module_imports_successfully(self):
        """モジュールが正常にインポートできることを確認"""
        try:
            from prompt_utils import add_system_prompts
            assert callable(add_system_prompts)
            success = True
        except ImportError:
            success = False
        
        assert success, "prompt_utils モジュールのインポートに失敗"

    def test_function_signature(self):
        """関数のシグネチャテスト"""
        import inspect

        from prompt_utils import add_system_prompts

        # 関数のシグネチャを取得
        sig = inspect.signature(add_system_prompts)
        params = list(sig.parameters.keys())
        
        # 期待されるパラメータが存在することを確認
        assert 'llm' in params, "llm パラメータが存在しません"
        assert 'logger' in params, "logger パラメータが存在しません"

    def test_with_real_logger_mock(self):
        """実際のロガーモックでのテスト"""
        from prompt_utils import add_system_prompts
        
        mock_llm = MagicMock()
        mock_llm.system_prompt = "リアルテスト"
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # プロンプトが更新されていることを確認
        assert "リアルテスト" in mock_llm.system_prompt
        assert len(mock_llm.system_prompt) > len("リアルテスト")

    def test_prompt_formatting(self):
        """プロンプトフォーマットのテスト"""
        mock_llm = MagicMock()
        mock_llm.system_prompt = "基本内容"
        mock_logger = MagicMock()
        
        add_system_prompts(mock_llm, mock_logger)
        
        # プロンプトが適切にフォーマットされていることを確認
        result = mock_llm.system_prompt
        
        # 基本的な構造チェック
        assert isinstance(result, str)
        assert len(result.strip()) > 0
        assert "基本内容" in result

    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        mock_logger = MagicMock()
        
        # 不正なLLMオブジェクトでもクラッシュしないことを確認
        invalid_llm = None
        
        try:
            add_system_prompts(invalid_llm, mock_logger)
            # エラーが発生する可能性があるが、クラッシュしない
            success = True
        except AttributeError:
            # system_prompt属性がないためのエラーは予想される
            success = True
        except Exception as e:
            # その他の予期しないエラー
            success = False
            pytest.fail(f"予期しないエラーが発生: {e}")
        
        assert success