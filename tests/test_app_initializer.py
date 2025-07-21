"""app_initializer.py のテスト"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest


from app_initializer import (
    extract_llm_config,
    extract_port_config,
    extract_stt_config,
    get_character_config,
    initialize_config,
    initialize_dock_log_handler,
    setup_debug_mode,
)


class TestInitializeConfig:
    """設定初期化のテスト"""

    @patch('app_initializer.load_config')
    @patch('app_initializer.validate_config')
    def test_initialize_config_default(self, mock_validate, mock_load):
        """デフォルト設定での初期化テスト"""
        mock_config = {"test": "config"}
        mock_load.return_value = mock_config
        mock_validate.return_value = []
        
        result = initialize_config()
        
        mock_load.assert_called_once_with(None)
        mock_validate.assert_called_once_with(mock_config)
        assert result == mock_config

    @patch('app_initializer.load_config')
    @patch('app_initializer.validate_config')
    def test_initialize_config_custom_dir(self, mock_validate, mock_load):
        """カスタムディレクトリでの初期化テスト"""
        mock_config = {"custom": "config"}
        mock_load.return_value = mock_config
        mock_validate.return_value = []
        custom_dir = "/custom/config/dir"
        
        result = initialize_config(custom_dir)
        
        mock_load.assert_called_once_with(custom_dir)
        mock_validate.assert_called_once_with(mock_config)
        assert result == mock_config

    @patch('app_initializer.load_config')
    @patch('app_initializer.validate_config')
    @patch('app_initializer.logger')
    def test_initialize_config_with_warnings(self, mock_logger, mock_validate, mock_load):
        """警告がある場合のテスト"""
        mock_config = {"test": "config"}
        mock_load.return_value = mock_config
        mock_validate.return_value = ["Warning 1", "Warning 2"]
        
        result = initialize_config()
        
        assert result == mock_config
        assert mock_logger.warning.call_count == 2


class TestInitializeDockLogHandler:
    """CocoroDock用ログハンドラー初期化のテスト"""

    @patch('app_initializer.logging.getLogger')
    def test_initialize_dock_log_handler_success(self, mock_get_logger):
        """正常なログハンドラー初期化のテスト"""
        config = {"cocoroDockPort": 55600}
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        with patch('log_handler.CocoroDockLogHandler') as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            
            result = initialize_dock_log_handler(config)
            
            mock_handler_class.assert_called_once_with(
                dock_url="http://127.0.0.1:55600", 
                component_name="CocoroCore"
            )
            assert result == mock_handler

    @patch('app_initializer.logging.getLogger')
    @patch('app_initializer.logger')
    def test_initialize_dock_log_handler_exception(self, mock_logger, mock_get_logger):
        """例外発生時のテスト"""
        config = {"cocoroDockPort": 55600}
        
        with patch('log_handler.CocoroDockLogHandler', side_effect=Exception("Import error")):
            result = initialize_dock_log_handler(config)
            
            assert result is None
            mock_logger.warning.assert_called_once()

    @patch('app_initializer.logging.getLogger')
    def test_initialize_dock_log_handler_default_port(self, mock_get_logger):
        """デフォルトポートでのテスト"""
        config = {}
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        with patch('log_handler.CocoroDockLogHandler') as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            
            result = initialize_dock_log_handler(config)
            
            mock_handler_class.assert_called_once_with(
                dock_url="http://127.0.0.1:55600", 
                component_name="CocoroCore"
            )


class TestSetupDebugMode:
    """デバッグモード設定のテスト"""

    @patch('app_initializer.logger')
    def test_setup_debug_mode_enabled(self, mock_logger):
        """デバッグモードが有効な場合のテスト"""
        config = {"debug": True}
        
        result = setup_debug_mode(config)
        
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
        assert result is True

    def test_setup_debug_mode_disabled(self):
        """デバッグモードが無効な場合のテスト"""
        config = {"debug": False}
        
        result = setup_debug_mode(config)
        
        assert result is False

    def test_setup_debug_mode_default(self):
        """デバッグモード設定がない場合のテスト"""
        config = {}
        
        result = setup_debug_mode(config)
        
        assert result is False


class TestGetCharacterConfig:
    """キャラクター設定取得のテスト"""

    def test_get_character_config_valid(self):
        """有効なキャラクター設定の取得テスト"""
        config = {
            "characterList": [
                {"name": "Character1", "model": "gpt-4"},
                {"name": "Character2", "model": "claude-3"},
            ],
            "currentCharacterIndex": 1
        }
        
        result = get_character_config(config)
        
        assert result == {"name": "Character2", "model": "claude-3"}

    def test_get_character_config_no_list(self):
        """キャラクターリストがない場合のテスト"""
        config = {"currentCharacterIndex": 0}
        
        with pytest.raises(ValueError, match="有効なキャラクター設定が見つかりません"):
            get_character_config(config)

    def test_get_character_config_empty_list(self):
        """空のキャラクターリストの場合のテスト"""
        config = {
            "characterList": [],
            "currentCharacterIndex": 0
        }
        
        with pytest.raises(ValueError, match="有効なキャラクター設定が見つかりません"):
            get_character_config(config)

    def test_get_character_config_invalid_index(self):
        """無効なインデックスの場合のテスト"""
        config = {
            "characterList": [{"name": "Character1"}],
            "currentCharacterIndex": 5
        }
        
        with pytest.raises(ValueError, match="有効なキャラクター設定が見つかりません"):
            get_character_config(config)

    def test_get_character_config_default_index(self):
        """デフォルトインデックスの場合のテスト"""
        config = {
            "characterList": [
                {"name": "Character1"},
                {"name": "Character2"},
            ]
        }
        
        result = get_character_config(config)
        
        assert result == {"name": "Character1"}


class TestExtractLlmConfig:
    """LLM設定抽出のテスト"""

    @patch('time_utils.create_time_guidelines')
    @patch('app_initializer.logger')
    def test_extract_llm_config_character_settings(self, mock_logger, mock_time_guidelines):
        """キャラクター設定からのLLM設定抽出テスト"""
        mock_time_guidelines.return_value = "\n\n時間ガイドライン"
        
        config = {}
        current_char = {
            "apiKey": "char_key",
            "llmModel": "char_model", 
            "systemPrompt": "char_prompt",
            "userId": "char_user"
        }
        current_index = 0
        
        api_key, model, prompt, user_id = extract_llm_config(config, current_char, current_index)
        
        assert api_key == "char_key"
        assert model == "char_model"
        assert "char_prompt" in prompt
        assert "時間ガイドライン" in prompt
        assert user_id == "char_user"

    @patch('time_utils.create_time_guidelines')
    @patch('app_initializer.logger')
    def test_extract_llm_config_environment_variable(self, mock_logger, mock_time_guidelines):
        """環境変数からのAPI Key取得テスト"""
        mock_time_guidelines.return_value = ""
        
        with patch.dict(os.environ, {'LLM_API_KEY_0': 'env_key'}):
            config = {}
            current_char = {
                "apiKey": "char_key",
                "llmModel": "char_model"
            }
            current_index = 0
            
            api_key, model, prompt, user_id = extract_llm_config(config, current_char, current_index)
            
            assert api_key == "env_key"  # 環境変数が優先される

    @patch('time_utils.create_time_guidelines')
    @patch('app_initializer.logger')
    def test_extract_llm_config_defaults(self, mock_logger, mock_time_guidelines):
        """デフォルト設定のテスト"""
        mock_time_guidelines.return_value = ""
        
        config = {}
        current_char = {}
        current_index = 0
        
        api_key, model, prompt, user_id = extract_llm_config(config, current_char, current_index)
        
        assert api_key is None
        assert model is None
        assert "あなたは親切なアシスタントです。" in prompt
        assert user_id == "default_user"


class TestExtractPortConfig:
    """ポート設定抽出のテスト"""

    def test_extract_port_config_custom(self):
        """カスタムポートの取得テスト"""
        config = {"cocoroCorePort": 8080}
        
        result = extract_port_config(config)
        
        assert result == 8080

    def test_extract_port_config_default(self):
        """デフォルトポートの取得テスト"""
        config = {}
        
        result = extract_port_config(config)
        
        assert result == 55601


class TestExtractSttConfig:
    """STT設定抽出のテスト"""

    def test_extract_stt_config_character_settings(self):
        """キャラクター設定からのSTT設定抽出テスト"""
        current_char = {
            "isUseSTT": True,
            "sttEngine": "openai",
            "sttWakeWord": "hello",
            "sttApiKey": "char_key",
            "sttLanguage": "en"
        }
        config = {
            "microphoneSettings": {
                "autoAdjustment": True,
                "inputThreshold": -30.0
            }
        }
        
        result = extract_stt_config(current_char, config)
        is_use_stt, engine, wake_word, api_key, language, vad_auto, vad_threshold = result
        
        assert is_use_stt is True
        assert engine == "openai"
        assert wake_word == "hello"
        assert api_key == "char_key"
        assert language == "en"
        assert vad_auto is True
        assert vad_threshold == -30.0

    def test_extract_stt_config_global_fallback(self):
        """グローバル設定へのフォールバックテスト"""
        current_char = {}
        config = {
            "microphoneSettings": {
                "autoAdjustment": False,
                "inputThreshold": -35.0
            }
        }
        
        result = extract_stt_config(current_char, config)
        is_use_stt, engine, wake_word, api_key, language, vad_auto, vad_threshold = result
        
        assert is_use_stt is False  # デフォルト
        assert engine == "amivoice"  # デフォルト
        assert wake_word == ""
        assert api_key == ""
        assert language == "ja"
        assert vad_auto is False
        assert vad_threshold == -35.0

    def test_extract_stt_config_defaults(self):
        """デフォルト設定のテスト"""
        current_char = {}
        config = {}
        
        result = extract_stt_config(current_char, config)
        is_use_stt, engine, wake_word, api_key, language, vad_auto, vad_threshold = result
        
        assert is_use_stt is False
        assert engine == "amivoice"
        assert wake_word == ""
        assert api_key == ""
        assert language == "ja"
        assert vad_auto is True
        assert vad_threshold == -45.0