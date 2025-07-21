"""client_initializer.py のテスト"""

from unittest.mock import MagicMock, patch

import pytest


from client_initializer import (
    initialize_api_clients,
    initialize_llm_manager,
    initialize_memory_client,
    initialize_session_manager,
)


class TestInitializeMemoryClient:
    """メモリクライアント初期化のテスト"""

    @patch('memory_client.ChatMemoryClient')
    def test_initialize_memory_client_enabled(self, mock_memory_class):
        """メモリ機能が有効な場合のテスト"""
        current_char = {"isEnableMemory": True}
        config = {"cocoroMemoryPort": 55602}
        mock_client = MagicMock()
        mock_memory_class.return_value = mock_client
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        mock_memory_class.assert_called_once_with(base_url="http://127.0.0.1:55602")
        assert memory_client == mock_client
        assert memory_enabled is True
        assert "メモリ機能について" in memory_prompt

    def test_initialize_memory_client_disabled_character(self):
        """キャラクター設定でメモリが無効な場合のテスト"""
        current_char = {"isEnableMemory": False}
        config = {"cocoroMemoryPort": 55602}
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        assert memory_client is None
        assert memory_enabled is False
        assert memory_prompt == ""

    def test_initialize_memory_client_disabled_global(self):
        """グローバル設定でメモリが無効な場合のテスト"""
        current_char = {}
        config = {
            "isEnableMemory": False,
            "cocoroMemoryPort": 55602
        }
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        assert memory_client is None
        assert memory_enabled is False
        assert memory_prompt == ""

    @patch('memory_client.ChatMemoryClient')
    def test_initialize_memory_client_default_port(self, mock_memory_class):
        """デフォルトポートでのテスト"""
        current_char = {"isEnableMemory": True}
        config = {}
        mock_client = MagicMock()
        mock_memory_class.return_value = mock_client
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        mock_memory_class.assert_called_once_with(base_url="http://127.0.0.1:55602")
        assert memory_client == mock_client
        assert memory_enabled is True
        assert "メモリ機能について" in memory_prompt

    @patch('memory_client.ChatMemoryClient')
    @patch('client_initializer.logger')
    def test_initialize_memory_client_exception_handling(self, mock_logger, mock_memory_class):
        """例外処理のテスト"""
        current_char = {"isEnableMemory": True}
        config = {"cocoroMemoryPort": 55602}
        mock_memory_class.side_effect = Exception("Connection failed")
        
        memory_client, memory_enabled, memory_prompt = initialize_memory_client(current_char, config)
        
        assert memory_client is None
        assert memory_enabled is False
        assert memory_prompt == ""
        mock_logger.error.assert_called_once()


class TestInitializeApiClients:
    """APIクライアント初期化のテスト"""

    @patch('api_clients.CocoroShellClient')
    @patch('api_clients.CocoroDockClient')
    def test_initialize_api_clients_all_enabled(self, mock_dock_class, mock_shell_class):
        """すべてのクライアントが有効な場合のテスト"""
        config = {
            "enableCocoroDock": True,
            "enableCocoroShell": True,
            "cocoroDockPort": 55600,
            "cocoroShellPort": 55605
        }
        mock_dock_client = MagicMock()
        mock_shell_client = MagicMock()
        mock_dock_class.return_value = mock_dock_client
        mock_shell_class.return_value = mock_shell_client
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        mock_dock_class.assert_called_once_with("http://127.0.0.1:55600")
        mock_shell_class.assert_called_once_with("http://127.0.0.1:55605")
        assert dock_client == mock_dock_client
        assert shell_client == mock_shell_client
        assert enable_shell is True
        assert shell_port == 55605

    @patch('api_clients.CocoroShellClient')
    @patch('api_clients.CocoroDockClient')
    def test_initialize_api_clients_dock_disabled(self, mock_dock_class, mock_shell_class):
        """CocoroDockが無効な場合のテスト"""
        config = {
            "enableCocoroDock": False,
            "enableCocoroShell": True,
            "cocoroShellPort": 55605
        }
        mock_shell_client = MagicMock()
        mock_shell_class.return_value = mock_shell_client
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        mock_dock_class.assert_not_called()
        mock_shell_class.assert_called_once_with("http://127.0.0.1:55605")
        assert dock_client is None
        assert shell_client == mock_shell_client
        assert enable_shell is True
        assert shell_port == 55605

    @patch('api_clients.CocoroShellClient')
    @patch('api_clients.CocoroDockClient')
    def test_initialize_api_clients_shell_disabled(self, mock_dock_class, mock_shell_class):
        """CocoroShellが無効な場合のテスト"""
        config = {
            "enableCocoroDock": True,
            "enableCocoroShell": False,
            "cocoroDockPort": 55600
        }
        mock_dock_client = MagicMock()
        mock_dock_class.return_value = mock_dock_client
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        mock_dock_class.assert_called_once_with("http://127.0.0.1:55600")
        mock_shell_class.assert_not_called()
        assert dock_client == mock_dock_client
        assert shell_client is None
        assert enable_shell is False
        assert shell_port == 55605  # デフォルト値

    @patch('api_clients.CocoroShellClient')
    @patch('api_clients.CocoroDockClient')
    def test_initialize_api_clients_default_ports(self, mock_dock_class, mock_shell_class):
        """デフォルトポートでのテスト"""
        config = {
            "enableCocoroDock": True,
            "enableCocoroShell": True
        }
        mock_dock_client = MagicMock()
        mock_shell_client = MagicMock()
        mock_dock_class.return_value = mock_dock_client
        mock_shell_class.return_value = mock_shell_client
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        mock_dock_class.assert_called_once_with("http://127.0.0.1:55600")
        mock_shell_class.assert_called_once_with("http://127.0.0.1:55605")
        assert dock_client == mock_dock_client
        assert shell_client == mock_shell_client
        assert enable_shell is True
        assert shell_port == 55605

    @patch('api_clients.CocoroDockClient')
    @patch('client_initializer.logger')
    def test_initialize_api_clients_dock_exception(self, mock_logger, mock_dock_class):
        """CocoroDockクライアント作成時の例外処理テスト"""
        config = {
            "enableCocoroDock": True,
            "enableCocoroShell": False
        }
        mock_dock_class.side_effect = Exception("Connection failed")
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        assert dock_client is None
        assert shell_client is None
        assert enable_shell is False
        assert shell_port == 55605
        mock_logger.error.assert_called_once()

    @patch('api_clients.CocoroShellClient')
    @patch('client_initializer.logger')
    def test_initialize_api_clients_shell_exception(self, mock_logger, mock_shell_class):
        """CocoroShellクライアント作成時の例外処理テスト"""
        config = {
            "enableCocoroDock": False,
            "enableCocoroShell": True
        }
        mock_shell_class.side_effect = Exception("Connection failed")
        
        dock_client, shell_client, enable_shell, shell_port = initialize_api_clients(config)
        
        assert dock_client is None
        assert shell_client is None
        assert enable_shell is True
        assert shell_port == 55605
        mock_logger.error.assert_called_once()


class TestInitializeLlmManager:
    """LLMマネージャー初期化のテスト"""

    @patch('llm_manager.LLMStatusManager')
    def test_initialize_llm_manager_with_client(self, mock_manager_class):
        """CocoroDockクライアントありでの初期化テスト"""
        cocoro_dock_client = MagicMock()
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        result = initialize_llm_manager(cocoro_dock_client)
        
        mock_manager_class.assert_called_once_with(cocoro_dock_client)
        assert result == mock_manager

    @patch('llm_manager.LLMStatusManager')
    def test_initialize_llm_manager_without_client(self, mock_manager_class):
        """CocoroDockクライアントなしでの初期化テスト"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        result = initialize_llm_manager(None)
        
        mock_manager_class.assert_called_once_with(None)
        assert result == mock_manager


class TestInitializeSessionManager:
    """セッションマネージャー初期化のテスト"""

    @patch('session_manager.SessionManager')
    def test_initialize_session_manager(self, mock_manager_class):
        """セッションマネージャー初期化テスト"""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        
        result = initialize_session_manager()
        
        mock_manager_class.assert_called_once()
        assert result == mock_manager