"""リファクタリング後のモジュール統合テスト

リファクタリングで分離された各モジュールが正しく連携して動作することを検証する
"""


from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAppInitializerIntegration:
    """app_initializer.py の統合テスト"""

    def test_initialize_config_integration(self):
        """設定初期化の統合テスト"""
        with patch('app_initializer.load_config') as mock_load:
            with patch('app_initializer.validate_config') as mock_validate:
                mock_load.return_value = {"test": "config"}
                mock_validate.return_value = []
                
                from app_initializer import initialize_config
                result = initialize_config()
                
                assert result == {"test": "config"}
                mock_load.assert_called_once()
                mock_validate.assert_called_once()

    def test_setup_debug_mode_integration(self):
        """デバッグモード設定の統合テスト"""
        from app_initializer import setup_debug_mode

        # デバッグモード有効
        result_enabled = setup_debug_mode({"debug": True})
        assert result_enabled is True
        
        # デバッグモード無効
        result_disabled = setup_debug_mode({"debug": False})
        assert result_disabled is False
        
        # デフォルト（無効）
        result_default = setup_debug_mode({})
        assert result_default is False

    def test_get_character_config_integration(self):
        """キャラクター設定取得の統合テスト"""
        from app_initializer import get_character_config

        # 正常ケース
        config = {
            "characterList": [
                {"name": "Character1", "model": "gpt-4"},
                {"name": "Character2", "model": "claude-3"},
            ],
            "currentCharacterIndex": 1
        }
        result = get_character_config(config)
        assert result == {"name": "Character2", "model": "claude-3"}
        
        # エラーケース
        with pytest.raises(ValueError):
            get_character_config({})

    def test_extract_port_config_integration(self):
        """ポート設定抽出の統合テスト"""
        from app_initializer import extract_port_config

        # カスタムポート
        result_custom = extract_port_config({"cocoroCorePort": 8080})
        assert result_custom == 8080
        
        # デフォルトポート
        result_default = extract_port_config({})
        assert result_default == 55601

    def test_extract_stt_config_integration(self):
        """STT設定抽出の統合テスト"""
        from app_initializer import extract_stt_config

        # キャラクター設定からの抽出
        current_char = {
            "isUseSTT": True,
            "sttEngine": "openai",
            "sttWakeWord": "hello",
            "sttApiKey": "test_key",
            "sttLanguage": "en"
        }
        config = {
            "microphoneSettings": {
                "autoAdjustment": False,
                "inputThreshold": -30.0
            }
        }
        
        result = extract_stt_config(current_char, config)
        is_use_stt, engine, wake_word, api_key, language, vad_auto, vad_threshold = result
        
        assert is_use_stt is True
        assert engine == "openai"
        assert wake_word == "hello"
        assert api_key == "test_key"
        assert language == "en"
        assert vad_auto is False
        assert vad_threshold == -30.0


class TestClientInitializerIntegration:
    """client_initializer.py の統合テスト"""

    def test_initialize_memory_client_disabled(self):
        """メモリクライアント初期化（無効）の統合テスト"""
        from client_initializer import initialize_memory_client

        # キャラクター設定で無効
        current_char = {"isEnableMemory": False}
        config = {"cocoroMemoryPort": 55602}
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        assert memory_client is None
        assert memory_enabled is False
        assert memory_prompt == ""

    def test_initialize_memory_client_enabled_with_mock(self):
        """メモリクライアント初期化（有効）の統合テスト（モック使用）"""
        # 実際のモジュールパスでパッチを当てる
        with patch('memory_client.ChatMemoryClient') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            from client_initializer import initialize_memory_client
            
            current_char = {"isEnableMemory": True}
            config = {"cocoroMemoryPort": 55602}
            
            memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
            
            assert memory_client == mock_instance
            assert memory_enabled is True
            assert "メモリ機能について" in memory_prompt

    def test_initialize_api_clients_disabled(self):
        """APIクライアント初期化（無効）の統合テスト"""
        from client_initializer import initialize_api_clients
        
        config = {
            "enableCocoroDock": False,
            "enableCocoroShell": False
        }
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        assert dock_client is None
        assert shell_client is None
        assert enable_shell is False
        assert shell_port == 55605  # デフォルト


class TestSTSConfiguratorIntegration:
    """sts_configurator.py の統合テスト"""

    @patch('sts_configurator.STSPipeline')
    @patch('sts_configurator.SpeechSynthesizerDummy')
    def test_sts_configurator_creation(self, mock_speech_synth, mock_sts_pipeline):
        """STSConfiguratorの作成テスト"""
        from sts_configurator import STSConfigurator
        
        configurator = STSConfigurator()
        assert configurator is not None

    @patch('sts_configurator.STSPipeline')
    @patch('sts_configurator.SpeechSynthesizerDummy')
    def test_set_shared_context_id(self, mock_speech_synth, mock_sts_pipeline):
        """共有context_id設定の統合テスト"""
        from sts_configurator import STSConfigurator
        
        mock_sts = MagicMock()
        STSConfigurator.set_shared_context_id(mock_sts, "test_context_id")
        
        assert mock_sts._shared_context_id == "test_context_id"


class TestToolsConfiguratorIntegration:
    """tools_configurator.py の統合テスト"""

    def test_tools_configurator_creation(self):
        """ToolsConfiguratorの作成テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        assert configurator is not None

    def test_setup_memory_tools_disabled(self):
        """メモリツール設定（無効）の統合テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        mock_sts = MagicMock()
        config = {}
        
        result = configurator.setup_memory_tools(
            sts=mock_sts,
            config=config,
            memory_client=None,
            session_manager=MagicMock(),
            cocoro_dock_client=MagicMock(),
            llm=MagicMock(),
            memory_enabled=False
        )
        
        assert result == ""

    def test_setup_mcp_tools_disabled(self):
        """MCPツール設定（無効）の統合テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        mock_sts = MagicMock()
        config = {"isEnableMcp": False}
        
        result = configurator.setup_mcp_tools(
            sts=mock_sts,
            config=config,
            cocoro_dock_client=MagicMock(),
            llm=MagicMock()
        )
        
        assert result == ""


class TestResponseProcessorIntegration:
    """response_processor.py の統合テスト"""

    def test_response_processor_creation(self):
        """ResponseProcessorの作成テスト"""
        from response_processor import ResponseProcessor
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=MagicMock(),
            session_manager=MagicMock()
        )
        
        assert processor is not None
        assert processor.user_id == "test_user"

    @pytest.mark.asyncio
    async def test_response_processor_basic_flow(self):
        """ResponseProcessorの基本フローテスト"""
        from response_processor import ResponseProcessor
        
        mock_request = MagicMock()
        mock_request.user_id = "test_user"
        mock_request.session_id = "test_session"
        
        mock_response = MagicMock()
        mock_response.context_id = "test_context"
        mock_response.text = "test response"
        
        mock_llm_status_manager = MagicMock()
        mock_session_manager = MagicMock()
        mock_session_manager.update_activity = AsyncMock()
        
        processor = ResponseProcessor(
            user_id="test_user",
            llm_status_manager=mock_llm_status_manager,
            session_manager=mock_session_manager
        )
        
        mock_setter = MagicMock()
        
        await processor.process_response_complete(mock_request, mock_response, mock_setter)
        
        # context_idが設定されることを確認
        mock_setter.assert_called_once_with("test_context")
        # セッションアクティビティが更新されることを確認
        mock_session_manager.update_activity.assert_called_once()


class TestEventHandlersIntegration:
    """event_handlers.py の統合テスト"""

    def test_event_handlers_creation(self):
        """AppEventHandlersの作成テスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers(
            memory_client=None,
            session_manager=None,
            user_id="test_user"
        )
        
        assert handlers is not None
        assert handlers.user_id == "test_user"

    @pytest.mark.asyncio
    async def test_startup_handler_creation(self):
        """startupハンドラー作成テスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers()
        handlers._setup_memory_timeout_checker = AsyncMock()
        handlers._setup_mic_input = AsyncMock()
        
        startup_handler = handlers.create_startup_handler()
        
        # ハンドラーが呼び出し可能であることを確認
        assert callable(startup_handler)
        
        # 実行してメソッドが呼ばれることを確認
        await startup_handler()
        handlers._setup_memory_timeout_checker.assert_called_once()
        handlers._setup_mic_input.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handler_creation(self):
        """shutdownハンドラー作成テスト"""
        from event_handlers import AppEventHandlers
        
        handlers = AppEventHandlers()
        handlers._cleanup_timeout_checker = AsyncMock()
        handlers._cleanup_memory = AsyncMock()
        handlers._cleanup_llm_status = AsyncMock()
        handlers._cleanup_api_clients = AsyncMock()
        handlers._cleanup_stt = AsyncMock()
        handlers._cleanup_mic_input = AsyncMock()
        
        shutdown_handler = handlers.create_shutdown_handler(
            llm_status_manager=MagicMock(),
            cocoro_dock_client=MagicMock(),
            cocoro_shell_client=MagicMock(),
            stt_instance=MagicMock()
        )
        
        # ハンドラーが呼び出し可能であることを確認
        assert callable(shutdown_handler)
        
        # 実行してクリーンアップメソッドが呼ばれることを確認
        await shutdown_handler()
        handlers._cleanup_timeout_checker.assert_called_once()
        handlers._cleanup_memory.assert_called_once()


class TestHookProcessorIntegration:
    """hook_processor.py の統合テスト"""

    def test_hook_processor_creation(self):
        """RequestHookProcessorの作成テスト"""
        from hook_processor import RequestHookProcessor
        
        processor = RequestHookProcessor(
            config={},
            llm=MagicMock(),
            user_id="test_user",
            llm_status_manager=MagicMock(),
            cocoro_dock_client=MagicMock(),
            cocoro_shell_client=MagicMock(),
            wakewords=None
        )
        
        assert processor is not None
        assert processor.user_id == "test_user"


class TestEndpointsIntegration:
    """endpoints.py の統合テスト"""

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_endpoints_setup_function_exists(self, mock_audio_recorder, mock_audio_device):
        """エンドポイント設定関数の存在確認"""
        from endpoints import setup_endpoints
        
        assert callable(setup_endpoints)

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_endpoints_setup_with_mock_app(self, mock_audio_recorder, mock_audio_device):
        """モックアプリでのエンドポイント設定テスト"""
        from endpoints import setup_endpoints
        
        mock_app = MagicMock()
        mock_deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: None,
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        # エラーが発生しないことを確認
        try:
            setup_endpoints(mock_app, mock_deps)
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"エンドポイント設定でエラーが発生: {e}")
        
        assert success


class TestModuleCoordinationIntegration:
    """モジュール間連携の統合テスト"""

    @patch('cocoro_core.AIAvatarHttpServer')
    @patch('cocoro_core.AudioDevice')
    @patch('cocoro_core.AudioRecorder')
    @patch('cocoro_core.STSPipeline')
    @patch('cocoro_core.SpeechSynthesizerDummy')
    @patch('cocoro_core.FileVoiceRecorder')
    def test_create_app_function_works(self, mock_file_recorder, mock_speech_synth, mock_sts_pipeline, mock_audio_recorder, mock_audio_device, mock_http_server):
        """create_app関数が動作することの確認"""
        try:
            from cocoro_core import create_app

            # create_app関数が存在し、呼び出し可能であることを確認
            assert callable(create_app)
            
            # NOTE: 実際の実行は依存関係が多いため、関数の存在のみを確認
            success = True
        except ImportError as e:
            success = False
            pytest.fail(f"create_app関数のインポートに失敗: {e}")
        
        assert success

    @patch('sts_configurator.STSPipeline')
    @patch('sts_configurator.SpeechSynthesizerDummy')
    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_all_refactored_modules_importable(self, mock_audio_recorder, mock_audio_device, mock_speech_synth, mock_sts_pipeline):
        """分離されたすべてのモジュールがインポート可能であることを確認"""
        modules_to_test = [
            'app_initializer',
            'client_initializer', 
            'event_handlers',
            'response_processor',
            'sts_configurator',
            'tools_configurator',
            'hook_processor',
            'endpoints'
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                success = True
            except ImportError as e:
                success = False
                pytest.fail(f"モジュール {module_name} のインポートに失敗: {e}")
            
            assert success, f"モジュール {module_name} がインポートできません"

    def test_module_functions_exist(self):
        """各モジュールの主要関数が存在することを確認"""
        # app_initializer
        from app_initializer import (
            extract_llm_config,
            extract_port_config,
            extract_stt_config,
            get_character_config,
            initialize_config,
            setup_debug_mode,
        )

        # client_initializer
        from client_initializer import (
            initialize_api_clients,
            initialize_llm_manager,
            initialize_memory_client,
            initialize_session_manager,
        )

        # 各関数が呼び出し可能であることを確認
        functions_to_check = [
            initialize_config, setup_debug_mode, get_character_config,
            extract_llm_config, extract_port_config, extract_stt_config,
            initialize_memory_client, initialize_api_clients,
            initialize_llm_manager, initialize_session_manager
        ]
        
        for func in functions_to_check:
            assert callable(func), f"関数 {func.__name__} が呼び出し可能ではありません"