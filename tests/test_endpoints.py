"""endpoints.py のテスト"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestSetupEndpoints:
    """setup_endpoints 関数のテスト"""

    @patch('endpoints.process_mic_input')
    def test_setup_endpoints_health_check(self, mock_process_mic):
        """ヘルスチェックエンドポイントのテスト"""
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": False},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": True,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["character"] == "TestCharacter"
        assert data["memory_enabled"] is True

    @patch('endpoints.process_mic_input')
    @patch('mcp_tools.get_mcp_status')
    def test_setup_endpoints_health_check_with_mcp(self, mock_mcp_status, mock_process_mic):
        """MCPが有効な場合のヘルスチェックエンドポイントのテスト"""
        mock_mcp_status.return_value = {"status": "active"}
        
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": True},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["mcp_status"] == {"status": "active"}

    @patch('endpoints.process_mic_input')
    def test_setup_endpoints_start_mic_input(self, mock_process_mic):
        """マイク入力開始エンドポイントのテスト"""
        # AsyncMockを使用してイベントループの問題を回避
        mock_process_mic.return_value = AsyncMock(return_value=None)
        
        app = FastAPI()
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        
        # STT制御コマンド（有効化）
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch('endpoints.process_mic_input')
    def test_setup_endpoints_stop_mic_input(self, mock_process_mic):
        """マイク入力停止エンドポイントのテスト"""
        app = FastAPI()
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        
        # STT制御コマンド（無効化）
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": False},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @patch('endpoints.process_mic_input')
    def test_setup_endpoints_shutdown(self, mock_process_mic):
        """シャットダウンエンドポイントのテスト"""
        app = FastAPI()
        mock_shutdown_handler = MagicMock()
        mock_shutdown_handler.shutdown = AsyncMock()
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": mock_shutdown_handler,
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        
        # シャットダウン制御コマンド
        response = client.post("/api/control", json={
            "command": "shutdown",
            "params": {"grace_period_seconds": 30},
            "reason": "test shutdown"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestEndpointsIntegration:
    """エンドポイント統合テスト"""

    @patch('endpoints.process_mic_input')
    def test_multiple_endpoints_available(self, mock_process_mic):
        """複数のエンドポイントが利用可能であることを確認"""
        app = FastAPI()
        deps = {
            "config": {},
            "current_char": {"name": "TestChar"},
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
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        
        # ヘルスチェック
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # STT制御（開始）
        start_response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "integration test"
        })
        assert start_response.status_code == 200
        
        # STT制御（停止）
        stop_response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": False},
            "reason": "integration test"
        })
        assert stop_response.status_code == 200

    @patch('endpoints.process_mic_input')
    def test_dependencies_injection(self, mock_process_mic):
        """依存関係の注入が正しく動作することを確認"""
        app = FastAPI()
        
        # より詳細な設定
        session_manager = MagicMock()
        session_manager.get_context_id.return_value = "test_context_123"
        
        deps = {
            "config": {"debug": True, "isEnableMcp": False},
            "current_char": {"name": "DetailedTestChar", "model": "gpt-4"},
            "memory_enabled": True,
            "llm_model": "gpt-4",
            "session_manager": session_manager,
            "dock_log_handler": MagicMock(),
            "stt_api_key": "sk-test123",
            "vad_instance": MagicMock(),
            "user_id": "detailed_user",
            "get_shared_context_id": lambda: "shared_ctx_456",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["character"] == "DetailedTestChar"
        assert data["memory_enabled"] is True


class TestEndpointsExtended:
    """エンドポイント拡張テストクラス"""
    
    @patch('endpoints.process_mic_input')
    @patch('mcp_tools.get_mcp_tool_registration_log')
    def test_mcp_debug_logs_enabled(self, mock_get_logs, mock_process_mic):
        """MCPデバッグログ取得（有効）のテスト"""
        mock_get_logs.return_value = ["Log entry 1", "Log entry 2"]
        
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": True},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/api/mcp/tool-registration-log")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["logs"]) == 2
    
    @patch('endpoints.process_mic_input')
    def test_mcp_debug_logs_disabled(self, mock_process_mic):
        """MCPデバッグログ取得（無効）のテスト"""
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": False},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/api/mcp/tool-registration-log")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "MCPは無効になっています"
        assert data["logs"] == []
    
    @patch('endpoints.process_mic_input')
    @patch('mcp_tools.get_mcp_tool_registration_log')
    def test_mcp_debug_logs_error(self, mock_get_logs, mock_process_mic):
        """MCPデバッグログ取得エラーのテスト"""
        mock_get_logs.side_effect = Exception("Log fetch error")
        
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": True},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.get("/api/mcp/tool-registration-log")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Log fetch error" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_api_key_missing(self, mock_process_mic):
        """APIキーなしでのSTT制御テスト"""
        app = FastAPI()
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = None
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": None,  # APIキーなし
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "API key or VAD missing" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_already_enabled(self, mock_process_mic):
        """すでに有効化されているSTTの制御テスト"""
        app = FastAPI()
        
        # 実行中のタスクをモック
        mock_task = MagicMock()
        mock_task.done.return_value = False
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = mock_task
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "already enabled" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_already_disabled(self, mock_process_mic):
        """すでに無効化されているSTTの制御テスト"""
        app = FastAPI()
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = None
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        from endpoints import setup_endpoints
        setup_endpoints(app, deps)
        
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": False},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "already disabled" in data["message"]


class TestEndpointsBranchCoverage:
    """endpoints.py 分岐カバレッジテスト"""
    
    @patch('endpoints.process_mic_input')
    def test_health_check_memory_enabled_branches(self, mock_process_mic):
        """ヘルスチェックでmemory_enabled分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        # memory_enabled=True の分岐
        app1 = FastAPI()
        deps1 = {
            "config": {"isEnableMcp": False},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": True,  # True分岐
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app1, deps1)
        client1 = TestClient(app1)
        response1 = client1.get("/health")
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["memory_enabled"] is True
        
        # memory_enabled=False の分岐
        app2 = FastAPI()
        deps2 = {
            "config": {"isEnableMcp": False},
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,  # False分岐
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app2, deps2)
        client2 = TestClient(app2)
        response2 = client2.get("/health")
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["memory_enabled"] is False
    
    @patch('endpoints.process_mic_input') 
    @patch('mcp_tools.get_mcp_status')
    def test_health_check_mcp_status_branches(self, mock_mcp_status, mock_process_mic):
        """ヘルスチェックでMCPステータス分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        # MCP有効でget_mcp_status成功の分岐
        mock_mcp_status.return_value = {"status": "active", "servers": 3}
        
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": True},  # MCP有効
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["mcp_status"] == {"status": "active", "servers": 3}
    
    @patch('endpoints.process_mic_input')
    @patch('mcp_tools.get_mcp_status')
    def test_health_check_mcp_error_branch(self, mock_mcp_status, mock_process_mic):
        """ヘルスチェックでMCPエラー分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        # MCP有効でget_mcp_statusエラーの分岐
        mock_mcp_status.side_effect = Exception("MCP connection failed")
        
        app = FastAPI()
        deps = {
            "config": {"isEnableMcp": True},  # MCP有効
            "current_char": {"name": "TestCharacter"},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["mcp_status"] == {"status": "error", "message": "MCP connection failed"}
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_vad_missing_branch(self, mock_process_mic):
        """VADなしでのSTT制御分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        app = FastAPI()
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = None
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",  # APIキーはある
            "vad_instance": None,  # VADなし
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "API key or VAD missing" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_task_done_branch(self, mock_process_mic):
        """完了済みタスクでのSTT制御分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        app = FastAPI()
        
        # 完了済みタスクをモック
        mock_task = MagicMock()
        mock_task.done.return_value = True  # 完了済み
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = mock_task
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": True},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # 完了済みタスクは実行中とみなされない
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_task_cancel_branch(self, mock_process_mic):
        """タスクキャンセル分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        app = FastAPI()
        
        # キャンセル可能なタスクをモック
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = True
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = mock_task
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": False},  # 無効化（キャンセル）
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # キャンセルが成功
        mock_task.cancel.assert_called_once()
    
    @patch('endpoints.process_mic_input')
    def test_stt_control_task_cancel_failure_branch(self, mock_process_mic):
        """タスクキャンセル失敗分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        app = FastAPI()
        
        # キャンセル失敗するタスクをモック
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = False  # キャンセル失敗
        
        mock_deps_container = MagicMock()
        mock_deps_container.mic_input_task = mock_task
        
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": mock_deps_container,
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "sttControl",
            "params": {"enabled": False},  # 無効化（キャンセル）
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to cancel" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_control_api_unknown_command_branch(self, mock_process_mic):
        """不明コマンド分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        app = FastAPI()
        deps = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": MagicMock(),
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app, deps)
        client = TestClient(app)
        response = client.post("/api/control", json={
            "command": "unknownCommand",  # 不明なコマンド
            "params": {},
            "reason": "test"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Unknown command" in data["message"]
    
    @patch('endpoints.process_mic_input')
    def test_shutdown_command_branches(self, mock_process_mic):
        """シャットダウンコマンド分岐のテスト（分岐カバレッジ）"""
        from endpoints import setup_endpoints
        
        # 正常なシャットダウン
        app1 = FastAPI()
        mock_shutdown_handler1 = MagicMock()
        mock_shutdown_handler1.shutdown = AsyncMock(return_value=True)
        
        deps1 = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": mock_shutdown_handler1,
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app1, deps1)
        client1 = TestClient(app1)
        response1 = client1.post("/api/control", json={
            "command": "shutdown",
            "params": {"grace_period_seconds": 10},
            "reason": "normal shutdown test"
        })
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"
        
        # シャットダウンエラー
        app2 = FastAPI()
        mock_shutdown_handler2 = MagicMock()
        mock_shutdown_handler2.shutdown = AsyncMock(side_effect=Exception("Shutdown failed"))
        
        deps2 = {
            "config": {},
            "current_char": {},
            "memory_enabled": False,
            "llm_model": "test_model",
            "session_manager": MagicMock(),
            "dock_log_handler": None,
            "stt_api_key": "test_key",
            "vad_instance": MagicMock(),
            "user_id": "test_user",
            "get_shared_context_id": lambda: "test_context",
            "cocoro_dock_client": MagicMock(),
            "shutdown_handler": mock_shutdown_handler2,
            "deps_container": MagicMock(),
        }
        
        setup_endpoints(app2, deps2)
        client2 = TestClient(app2)
        response2 = client2.post("/api/control", json={
            "command": "shutdown",
            "params": {"grace_period_seconds": 5},
            "reason": "error shutdown test"
        })
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "error"
        assert "Shutdown failed" in data2["message"]