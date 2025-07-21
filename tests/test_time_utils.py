"""time_utils.py のテスト"""


from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from time_utils import create_time_guidelines, generate_current_time_info


class TestGenerateCurrentTimeInfo:
    """現在時刻情報生成のテスト"""

    @patch('time_utils.datetime')
    def test_generate_current_time_info_weekday(self, mock_datetime):
        """平日の時刻情報生成テスト"""
        # 2024年1月15日（月曜日）10:30:45をモック
        mock_now = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone(timedelta(hours=9)))
        mock_datetime.now.return_value = mock_now
        
        result = generate_current_time_info()
        
        assert "2024年1月15日" in result
        assert "月" in result
        assert "10時30分" in result
        assert "朝" in result

    @patch('time_utils.datetime')
    def test_generate_current_time_info_weekend(self, mock_datetime):
        """週末の時刻情報生成テスト"""
        # 2024年1月13日（土曜日）15:45:00をモック
        mock_now = datetime(2024, 1, 13, 15, 45, 0, tzinfo=timezone(timedelta(hours=9)))
        mock_datetime.now.return_value = mock_now
        
        result = generate_current_time_info()
        
        assert "2024年1月13日" in result
        assert "土" in result
        assert "15時45分" in result
        assert "昼" in result

    @patch('time_utils.datetime')
    def test_generate_current_time_info_midnight(self, mock_datetime):
        """深夜の時刻情報生成テスト"""
        # 2024年1月1日 0:15:30をモック
        mock_now = datetime(2024, 1, 1, 0, 15, 30, tzinfo=timezone(timedelta(hours=9)))
        mock_datetime.now.return_value = mock_now
        
        result = generate_current_time_info()
        
        assert "2024年1月1日" in result
        assert "0時15分" in result


class TestCreateTimeGuidelines:
    """時間ガイドライン作成のテスト"""

    @patch('time_utils.generate_current_time_info')
    def test_create_time_guidelines(self, mock_generate_time):
        """時間ガイドライン作成テスト"""
        mock_generate_time.return_value = "2024年1月15日（月曜日）10時30分（午前）"
        
        result = create_time_guidelines()
        
        assert "時間感覚ガイドライン" in result

    def test_create_time_guidelines_content(self):
        """時間ガイドラインの内容テスト"""
        result = create_time_guidelines()
        
        # 重要なキーワードが含まれていることを確認
        important_keywords = [
            "時間感覚ガイドライン",
            "挨拶",
            "時間帯",
            "時間の経過",
            "現在時刻"
        ]
        
        for keyword in important_keywords:
            assert keyword in result, f"キーワード '{keyword}' がガイドラインに含まれていません"




class TestTimeUtilsIntegration:
    """時間ユーティリティ統合テスト"""

    def test_all_functions_return_strings(self):
        """すべての関数が文字列を返すことを確認"""
        # すべての関数が文字列を返すことを確認
        result_current = generate_current_time_info()
        assert isinstance(result_current, str)
        assert len(result_current) > 0
        
        result_guidelines = create_time_guidelines()
        assert isinstance(result_guidelines, str)
        assert len(result_guidelines) > 0

    def test_functions_work_correctly(self):
        """関数が正しく動作することを確認"""
        # 現在時刻情報が適切な形式で返されることを確認
        result_current = generate_current_time_info()
        assert "年" in result_current
        assert "月" in result_current
        assert "日" in result_current
        assert "時" in result_current
        assert "分" in result_current

    @patch('time_utils.datetime')
    def test_consistency_across_calls(self, mock_datetime):
        """複数回呼び出しても一貫した結果が得られることを確認"""
        mock_now = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone(timedelta(hours=9)))
        mock_datetime.now.return_value = mock_now
        
        # 複数回呼び出し
        result1 = generate_current_time_info()
        result2 = generate_current_time_info()
        result3 = generate_current_time_info()
        
        # 同じ結果が得られることを確認
        assert result1 == result2 == result3