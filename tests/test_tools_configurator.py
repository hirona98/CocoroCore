"""tools_configurator.py のテスト"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestToolsConfigurator:
    """ToolsConfigurator クラスのテスト"""

    def test_init(self):
        """初期化のテスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        # 初期化で特に状態を持たないことを確認
        assert configurator is not None

    @patch('memory_tools.setup_memory_tools')
    def test_setup_memory_tools_enabled(self, mock_setup_memory):
        """メモリツール設定（有効）のテスト"""
        from tools_configurator import ToolsConfigurator
        
        mock_setup_memory.return_value = "Memory tools configured"
        
        configurator = ToolsConfigurator()
        mock_sts = MagicMock()
        mock_config = {"memory_enabled": True}
        mock_memory_client = AsyncMock()
        mock_session_manager = MagicMock()
        mock_dock_client = AsyncMock()
        mock_llm = MagicMock()
        
        result = configurator.setup_memory_tools(
            sts=mock_sts,
            config=mock_config,
            memory_client=mock_memory_client,
            session_manager=mock_session_manager,
            cocoro_dock_client=mock_dock_client,
            llm=mock_llm,
            memory_enabled=True
        )
        
        # setup_memory_toolsが呼ばれることを確認
        mock_setup_memory.assert_called_once()
        assert result == "Memory tools configured"

    def test_setup_memory_tools_disabled(self):
        """メモリツール設定（無効）のテスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        result = configurator.setup_memory_tools(
            sts=MagicMock(),
            config={},
            memory_client=None,
            session_manager=MagicMock(),
            cocoro_dock_client=None,
            llm=MagicMock(),
            memory_enabled=False
        )
        
        # メモリ無効時は空文字列が返される
        assert result == ""

    @patch('mcp_tools.setup_mcp_tools')
    def test_setup_mcp_tools_enabled(self, mock_setup_mcp):
        """MCPツール設定（有効）のテスト"""
        from tools_configurator import ToolsConfigurator
        
        mock_setup_mcp.return_value = "MCP tools configured"
        
        configurator = ToolsConfigurator()
        mock_sts = MagicMock()
        mock_config = {"isEnableMcp": True, "mcp_servers": []}
        mock_llm = MagicMock()
        
        result = configurator.setup_mcp_tools(
            sts=mock_sts,
            config=mock_config,
            cocoro_dock_client=None,
            llm=mock_llm
        )
        
        # setup_mcp_toolsが呼ばれることを確認
        mock_setup_mcp.assert_called_once()
        assert result == "MCP tools configured"

    def test_setup_mcp_tools_disabled(self):
        """MCPツール設定（無効）のテスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        result = configurator.setup_mcp_tools(
            sts=MagicMock(),
            config={},
            cocoro_dock_client=None,
            llm=MagicMock()
        )
        
        # MCP無効時は空文字列が返される
        assert result == ""

    @patch('memory_tools.setup_memory_tools')
    @patch('mcp_tools.setup_mcp_tools')
    def test_setup_all_tools(self, mock_setup_mcp, mock_setup_memory):
        """全ツール設定のテスト"""
        from tools_configurator import ToolsConfigurator
        
        mock_setup_memory.return_value = "Memory configured"
        mock_setup_mcp.return_value = "MCP configured"
        
        configurator = ToolsConfigurator()
        
        # setup_all_toolsメソッドは存在しないため、個別に呼び出し
        memory_result = configurator.setup_memory_tools(
            sts=MagicMock(),
            config={"memory_enabled": True},
            memory_client=AsyncMock(),
            session_manager=MagicMock(),
            cocoro_dock_client=AsyncMock(),
            llm=MagicMock(),
            memory_enabled=True
        )
        
        mcp_result = configurator.setup_mcp_tools(
            sts=MagicMock(),
            config={"isEnableMcp": True},
            cocoro_dock_client=AsyncMock(),
            llm=MagicMock()
        )
        
        result = memory_result + mcp_result
        
        # 両方のツールが設定されることを確認
        mock_setup_memory.assert_called_once()
        mock_setup_mcp.assert_called_once()
        assert isinstance(result, str)

    def test_tools_configurator_error_handling(self):
        """エラーハンドリングのテスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        # メモリクライアントがNoneでもエラーにならないことを確認
        result = configurator.setup_memory_tools(
            sts=MagicMock(),
            config={},
            memory_client=None,
            session_manager=MagicMock(),
            cocoro_dock_client=None,
            llm=MagicMock(),
            memory_enabled=False
        )
        
        assert result == ""

    def test_memory_tools_with_exception(self):
        """メモリツール設定時の例外処理テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        # 無効な設定でも例外が発生しないことを確認
        with patch('memory_tools.setup_memory_tools') as mock_setup:
            mock_setup.side_effect = ImportError("Module not found")
            
            result = configurator.setup_memory_tools(
                sts=MagicMock(),
                config={},
                memory_client=AsyncMock(),
                session_manager=MagicMock(),
                cocoro_dock_client=AsyncMock(),
                llm=MagicMock(),
                memory_enabled=True
            )
            
            # エラー時は空文字列が返される
            assert result == ""

    def test_mcp_tools_with_exception(self):
        """MCPツール設定時の例外処理テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        # 無効な設定でも例外が発生しないことを確認
        with patch('mcp_tools.setup_mcp_tools') as mock_setup:
            mock_setup.side_effect = ImportError("Module not found")
            
            result = configurator.setup_mcp_tools(
                sts=MagicMock(),
                config={"isEnableMcp": True},
                cocoro_dock_client=None,
                llm=MagicMock()
            )
            
            # エラー時は空文字列が返される
            assert result == ""

    def test_tools_configurator_integration(self):
        """ToolsConfigurator統合テスト"""
        from tools_configurator import ToolsConfigurator
        
        configurator = ToolsConfigurator()
        
        # 基本的な使用パターンをテスト
        mock_sts = MagicMock()
        config = {
            "memory_enabled": True,
            "mcp_enabled": False,
            "mcp_servers": []
        }
        
        # メモリツールのみ設定
        memory_result = configurator.setup_memory_tools(
            sts=mock_sts,
            config=config,
            memory_client=AsyncMock(),
            session_manager=MagicMock(),
            cocoro_dock_client=AsyncMock(),
            llm=MagicMock(),
            memory_enabled=True
        )
        
        # MCPツールは無効
        mcp_result = configurator.setup_mcp_tools(
            sts=mock_sts,
            config=config,
            cocoro_dock_client=None,
            llm=MagicMock()
        )
        
        # メモリツールは設定され、MCPツールは空
        assert isinstance(memory_result, str)
        assert mcp_result == ""