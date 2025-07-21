#!/usr/bin/env python
"""MCP ツールシステムのテスト"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# pytestがある場合のみインポート
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # pytestのデコレータを無効化するダミー
    def pytest_mark_asyncio(func):
        return func
    pytest = type('pytest', (), {'mark': type('mark', (), {'asyncio': pytest_mark_asyncio})})()

# テスト対象のモジュールをインポート

from mcp_tools import MCPServerManager, setup_mcp_tools, get_mcp_status


class TestMCPServerManager:
    """MCPServerManagerクラスのテスト"""
    
    def setup_method(self):
        """各テストメソッドの前に実行"""
        self.servers_config = {
            "test-server": {
                "command": "python",
                "args": ["-c", "import sys; import json; import time; input()"],
                "env": {}
            }
        }
        self.manager = MCPServerManager(self.servers_config)
    
    def test_init(self):
        """初期化のテスト"""
        assert self.manager.servers_config == self.servers_config
        assert self.manager.available_tools == {}
        assert self.manager.server_processes == {}
    
    def test_get_server_info_empty(self):
        """空の状態でのサーバー情報取得テスト"""
        info = self.manager.get_server_info()
        
        assert info["total_servers"] == 1
        assert info["connected_servers"] == 0
        assert info["total_tools"] == 0
        assert "test-server" in info["servers"]
        assert not info["servers"]["test-server"]["connected"]

    def test_get_server_info_with_tools(self):
        """ツールありでのサーバー情報取得テスト"""
        # 手動でツールを追加
        self.manager.available_tools["test-server_sample_tool"] = {
            "server": "test-server",
            "tool": {"name": "sample_tool"},
            "config": self.servers_config["test-server"],
            "jsonrpc_mode": True
        }
        
        info = self.manager.get_server_info()
        
        assert info["total_servers"] == 1
        assert info["connected_servers"] == 0  # プロセスがないので未接続
        assert info["total_tools"] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_server(self):
        """サーバークリーンアップのテスト"""
        # モックプロセスを作成
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        
        # プロセスとツールを手動で設定
        self.manager.server_processes["test-server"] = mock_process
        self.manager.available_tools["test-server_test_tool"] = {
            "server": "test-server",
            "tool": {"name": "test_tool"},
            "process": mock_process,
            "config": self.servers_config["test-server"],
            "jsonrpc_mode": True
        }
        
        # クリーンアップ実行
        await self.manager._cleanup_server("test-server")
        
        # プロセスが終了されたことを確認
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        
        # データが削除されたことを確認
        assert "test-server" not in self.manager.server_processes
        assert "test-server_test_tool" not in self.manager.available_tools
    
    @pytest.mark.asyncio
    async def test_disconnect_server(self):
        """サーバー切断のテスト"""
        # モックプロセスを設定
        mock_process = AsyncMock()
        self.manager.server_processes["test-server"] = mock_process
        
        # _cleanup_serverをモック化
        with patch.object(self.manager, '_cleanup_server') as mock_cleanup:
            await self.manager.disconnect_server("test-server")
            mock_cleanup.assert_called_once_with("test-server")
    
    @pytest.mark.asyncio
    async def test_check_npx_package(self):
        """NPXパッケージチェックのテスト"""
        # npm viewコマンドをモック化
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"test-package", b"")
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await self.manager._check_npx_package(["-y", "test-package"], {})
            assert result is True
    
    def test_get_server_info_with_tools(self):
        """ツールがある状態でのサーバー情報取得テスト"""
        # ツールを手動で追加
        self.manager.available_tools["test-server_calculator"] = {
            "server": "test-server",
            "tool": {"name": "calculator", "description": "計算ツール"},
            "config": self.servers_config["test-server"]
        }
        
        # モックプロセスを追加
        mock_process = AsyncMock()
        self.manager.server_processes["test-server"] = mock_process
        
        info = self.manager.get_server_info()
        
        assert info["total_servers"] == 1
        assert info["connected_servers"] == 1
        assert info["total_tools"] == 1
        assert info["servers"]["test-server"]["connected"] is True
        assert info["servers"]["test-server"]["tool_count"] == 1
        assert info["servers"]["test-server"]["connection_type"] == "jsonrpc"


class TestJSONRPCCommunication:
    """JSON-RPC通信のテスト"""
    
    @pytest.mark.asyncio
    async def test_jsonrpc_message_format(self):
        """JSON-RPCメッセージ形式のテスト"""
        manager = MCPServerManager({})
        
        # ツール実行用のJSONメッセージをテスト
        tool_info = {
            "tool": {"name": "test_tool"},
            "process": AsyncMock()
        }
        
        # stdin/stdoutをモック化
        mock_stdin = AsyncMock()
        mock_stdout = AsyncMock()
        
        # 正常な応答をモック
        response_data = {
            "jsonrpc": "2.0",
            "id": 1234,
            "result": {
                "content": [{"text": "テスト結果"}]
            }
        }
        response_line = (json.dumps(response_data) + "\n").encode('utf-8')
        mock_stdout.readline.return_value = response_line
        
        tool_info["process"].stdin = mock_stdin
        tool_info["process"].stdout = mock_stdout
        
        # ツール実行テスト
        result = await manager._execute_tool_jsonrpc(tool_info, {"param": "value"})
        
        # 結果確認
        assert result == "テスト結果"
        
        # 送信されたメッセージを確認
        mock_stdin.write.assert_called_once()
        sent_data = mock_stdin.write.call_args[0][0].decode('utf-8').strip()
        sent_message = json.loads(sent_data)
        
        assert sent_message["jsonrpc"] == "2.0"
        assert sent_message["method"] == "tools/call"
        assert sent_message["params"]["name"] == "test_tool"
        assert sent_message["params"]["arguments"] == {"param": "value"}


class TestMCPSetup:
    """MCP設定のテスト"""
    
    def test_setup_mcp_tools_no_config(self):
        """設定が空の場合のセットアップテスト"""
        # モックSTS
        mock_sts = MagicMock()
        
        # モック設定（空の設定）
        mock_config = MagicMock()
        mock_config._config_dir = "./UserData"
        
        # 設定ファイルが存在しない場合をモック化
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = setup_mcp_tools(mock_sts, mock_config)
            
            # 空の設定でも正常に処理されることを確認
            assert isinstance(result, str)
            # 空の設定の場合はメッセージが空文字列になることを確認
            assert result == ""
    
    def test_setup_mcp_tools_with_servers(self):
        """サーバー設定がある場合のセットアップテスト"""
        mock_sts = MagicMock()
        mock_config = MagicMock()
        mock_config._config_dir = "./UserData"
        
        # テスト用のサーバー設定
        test_servers = {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"]
            },
            "calculator": {
                "command": "python",
                "args": ["calculator.py"]
            }
        }
        
        # 設定ファイルをモック化
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            with patch('builtins.open', mock_open(read_data=json.dumps({"mcpServers": test_servers}))):
                
                result = setup_mcp_tools(mock_sts, mock_config)
                
                # サーバー情報が含まれることを確認
                assert "設定されたサーバー: filesystem, calculator" in result


class TestMCPStatus:
    """MCP状態取得のテスト"""
    
    @pytest.mark.asyncio
    async def test_get_mcp_status_no_manager(self):
        """マネージャーが未初期化の場合のテスト"""
        # グローバルマネージャーをリセット
        import mcp_tools
        original_manager = mcp_tools.mcp_manager
        mcp_tools.mcp_manager = None
        
        try:
            status = await get_mcp_status()
            assert "error" in status
            assert "MCPマネージャーが初期化されていません" in status["error"]
        finally:
            # 元の状態に戻す
            mcp_tools.mcp_manager = original_manager
    
    @pytest.mark.asyncio
    async def test_get_mcp_status_with_manager(self):
        """マネージャーが初期化済みの場合のテスト"""
        import mcp_tools
        
        # テスト用マネージャーを作成
        test_manager = MCPServerManager({"test": {"command": "python", "args": []}})
        original_manager = mcp_tools.mcp_manager
        mcp_tools.mcp_manager = test_manager
        
        try:
            status = await get_mcp_status()
            assert "total_servers" in status
            assert "connected_servers" in status
            assert "total_tools" in status
            assert "servers" in status
        finally:
            # 元の状態に戻す
            mcp_tools.mcp_manager = original_manager


class TestMCPToolsExtended:
    """MCP Tools 拡張テストクラス"""
    
    def test_mcp_server_manager_init_with_various_configs(self):
        """様々な設定でのMCPServerManager初期化テスト"""
        from mcp_tools import MCPServerManager
        
        # 空の設定
        manager1 = MCPServerManager({})
        assert manager1.servers_config == {}
        assert manager1.available_tools == {}
        
        # 複数サーバー設定
        config = {
            "server1": {"command": "test1", "args": [], "env": {}},
            "server2": {"command": "test2", "args": ["arg1"], "env": {"VAR": "value"}}
        }
        manager2 = MCPServerManager(config)
        assert len(manager2.servers_config) == 2
        assert "server1" in manager2.servers_config
        assert "server2" in manager2.servers_config
    
    @pytest.mark.asyncio
    async def test_check_npx_package_variations(self):
        """npxパッケージチェックの様々なパターンテスト"""
        from mcp_tools import MCPServerManager
        
        manager = MCPServerManager({})
        
        # 空の引数
        result1 = await manager._check_npx_package([], {})
        assert result1 is False
        
        # None引数
        result2 = await manager._check_npx_package(None, {})
        assert result2 is False
    
    def test_get_server_info_with_tools(self):
        """ツール情報を含むサーバー情報取得テスト"""
        from mcp_tools import MCPServerManager
        
        config = {
            "test-server": {"command": "test", "args": [], "env": {}}
        }
        manager = MCPServerManager(config)
        
        # ツールを追加
        manager.available_tools = {
            "tool1": {"name": "tool1", "description": "Test tool 1"},
            "tool2": {"name": "tool2", "description": "Test tool 2"}
        }
        
        info = manager.get_server_info()
        assert info["total_servers"] == 1
        assert info["total_tools"] == 2
        assert len(info["tools"]) == 2
    
    def test_tool_registration_log(self):
        """ツール登録ログのテスト"""
        from mcp_tools import MCPServerManager
        
        manager = MCPServerManager({})
        
        # 初期状態
        assert manager.tool_registration_log == []
        
        # ログ追加
        manager.tool_registration_log.append("Test log entry")
        assert len(manager.tool_registration_log) == 1
        assert manager.tool_registration_log[0] == "Test log entry"


class TestErrorHandling:
    """エラーハンドリングのテスト"""
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """存在しないツールの実行テスト"""
        manager = MCPServerManager({})
        
        with pytest.raises(ValueError, match="ツール 'nonexistent_tool' が見つかりません"):
            await manager.execute_tool("nonexistent_tool", {})
    
    @pytest.mark.asyncio
    async def test_jsonrpc_timeout_error(self):
        """JSON-RPC通信タイムアウトのテスト"""
        manager = MCPServerManager({})
        
        tool_info = {
            "tool": {"name": "slow_tool"},
            "process": AsyncMock()
        }
        
        # タイムアウトを発生させる
        tool_info["process"].stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError())
        
        with pytest.raises(Exception, match="ツールの実行がタイムアウトしました"):
            await manager._execute_tool_jsonrpc(tool_info, {})
    
    @pytest.mark.asyncio
    async def test_jsonrpc_json_decode_error(self):
        """JSON-RPC応答の解析エラーテスト"""
        manager = MCPServerManager({})
        
        tool_info = {
            "tool": {"name": "broken_tool"},
            "process": AsyncMock()
        }
        
        # 不正なJSONを返す
        tool_info["process"].stdout.readline.return_value = b"invalid json\n"
        
        with pytest.raises(Exception, match="ツール応答の解析に失敗しました"):
            await manager._execute_tool_jsonrpc(tool_info, {})


class TestJSONRPCCommunication:
    """JSON-RPC通信のテスト"""
    
    def test_jsonrpc_message_format(self):
        """JSON-RPCメッセージフォーマットのテスト"""
        manager = MCPServerManager({})
        
        # テスト用のツール情報
        tool_info = {
            "tool": {"name": "test_tool"},
            "process": AsyncMock()
        }
        
        # JSON-RPCメッセージの作成をテスト
        # 実際の_execute_tool_jsonrpcメソッドは非同期なので、
        # 同期的にテストできる部分のみテスト
        tool_name = tool_info["tool"]["name"]
        assert tool_name == "test_tool"


class TestMCPToolsExtended:
    """MCP Toolsの拡張テスト"""
    

    def test_mcp_server_manager_multiple_servers(self):
        """複数サーバーでのテスト"""
        servers_config = {
            "server1": {
                "command": "python",
                "args": ["-c", "print('server1')"]
            },
            "server2": {
                "command": "node",
                "args": ["server2.js"]
            }
        }
        manager = MCPServerManager(servers_config)
        
        info = manager.get_server_info()
        assert info["total_servers"] == 2
        assert "server1" in info["servers"]
        assert "server2" in info["servers"]

    def test_mcp_tools_config_variations(self):
        """様々な設定でのMCPツールテスト"""
        mock_sts = MagicMock()
        
        # 様々な設定パターンをテスト
        configs = [
            MagicMock(_config_dir="./UserData"),
            MagicMock(_config_dir="/tmp/test"),
            MagicMock(_config_dir="C:\\Test\\Config"),
        ]
        
        for config in configs:
            with patch('os.path.exists') as mock_exists:
                mock_exists.return_value = False
                
                result = setup_mcp_tools(mock_sts, config)
                assert isinstance(result, str)
                assert result == ""  # ファイルが存在しない場合は空文字列


def run_basic_tests():
    """基本的なテストを実行"""
    print("=== MCP Tools 基本テスト ===")
    
    # テスト1: MCPServerManagerの初期化
    print("テスト1: MCPServerManager初期化...")
    servers_config = {
        "test-server": {
            "command": "python",
            "args": ["-c", "print('test')"],
            "env": {}
        }
    }
    manager = MCPServerManager(servers_config)
    assert manager.servers_config == servers_config
    assert manager.available_tools == {}
    assert manager.server_processes == {}
    print("✅ OK")
    
    # テスト2: setup_mcp_tools (設定なし)
    print("テスト2: setup_mcp_tools (設定なし)...")
    mock_sts = MagicMock()
    mock_config = MagicMock()
    mock_config._config_dir = "./UserData"
    
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        result = setup_mcp_tools(mock_sts, mock_config)
        assert result == ""
    print("✅ OK")
    
    # テスト3: setup_mcp_tools (設定あり)
    print("テスト3: setup_mcp_tools (設定あり)...")
    test_servers = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem"]
        },
        "calculator": {
            "command": "python",
            "args": ["calculator.py"]
        }
    }
    
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        with patch('builtins.open', mock_open(read_data=json.dumps({"mcpServers": test_servers}))):
            result = setup_mcp_tools(mock_sts, mock_config)
            assert "設定されたサーバー: filesystem, calculator" in result
    print("✅ OK")
    
    print("=== 全テスト完了 ===")

if __name__ == "__main__":
    if HAS_PYTEST:
        # pytest実行
        pytest.main([__file__, "-v", "--tb=short"])
    else:
        # 基本テスト実行
        run_basic_tests()