"""pytest設定ファイル"""
import pytest
import sys
import os

# srcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def sample_config():
    """テスト用設定データ"""
    return {
        "CharacterName": "TestCharacter",
        "LLMProvider": "openai",
        "apiUrl": "http://localhost:55601",
        "ports": {
            "CocoroCore": 55601,
            "ChatMemory": 55602,
            "CocoroDock": 55600,
            "CocoroShell": 55605
        },
        "systemPrompt": "テスト用システムプロンプト"
    }


@pytest.fixture
def sample_request():
    """テスト用リクエストオブジェクト"""
    from unittest.mock import MagicMock
    
    request = MagicMock()
    request.text = "テストメッセージ"
    request.session_id = "test_session"
    request.user_id = "test_user"
    request.metadata = {}
    return request


@pytest.fixture
def sample_response():
    """テスト用レスポンスオブジェクト"""
    from unittest.mock import MagicMock
    
    response = MagicMock()
    response.text = "テストレスポンス"
    return response