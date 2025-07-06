"""Claude Desktop MCP設定のインポート機能"""

import json
import os
import platform
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ClaudeMCPImporter:
    """Claude DesktopのMCP設定をインポートするクラス"""
    
    def __init__(self):
        self.claude_config_path = self._get_claude_config_path()
        
    def _get_claude_config_path(self) -> Optional[str]:
        """OSに応じたClaude Desktop設定ファイルのパスを取得"""
        system = platform.system()
        
        if system == "Windows":
            # Windows: %APPDATA%\Claude\claude_desktop_config.json
            appdata = os.environ.get("APPDATA")
            if appdata:
                return os.path.join(appdata, "Claude", "claude_desktop_config.json")
        
        elif system in ["Darwin", "Linux"]:
            # macOS/Linux: ~/.claude/claude_desktop_config.json
            home = os.path.expanduser("~")
            return os.path.join(home, ".claude", "claude_desktop_config.json")
        
        logger.warning(f"未対応のOS: {system}")
        return None
    
    def load_claude_mcp_config(self) -> Dict:
        """Claude DesktopのMCP設定を読み込み"""
        if not self.claude_config_path:
            logger.warning("Claude Desktop設定ファイルのパスが特定できません")
            return {}
        
        if not os.path.exists(self.claude_config_path):
            logger.info(f"Claude Desktop設定ファイルが見つかりません: {self.claude_config_path}")
            return {}
        
        try:
            with open(self.claude_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            mcp_servers = config.get("mcpServers", {})
            logger.info(f"Claude Desktopから{len(mcp_servers)}個のMCPサーバー設定を読み込みました")
            return mcp_servers
            
        except json.JSONDecodeError as e:
            logger.error(f"Claude Desktop設定ファイルのJSONエラー: {e}")
            return {}
        except Exception as e:
            logger.error(f"Claude Desktop設定ファイルの読み込みエラー: {e}")
            return {}
    
    def convert_to_cocoro_format(self, claude_servers: Dict) -> Dict:
        """Claude Desktop形式をCocoroAI形式に変換"""
        cocoro_servers = {}
        
        for server_name, server_config in claude_servers.items():
            # Claude Desktop形式からCocoroAI形式に変換
            cocoro_config = {
                "enabled": True,  # Claude Desktopで設定済み = 有効とみなす
                "name": server_name.replace("-", " ").title(),
                "description": f"Claude Desktopからインポート: {server_name}",
                "transport": "stdio",  # Claude Desktopは主にstdioを使用
                "command": server_config.get("command", ""),
                "args": server_config.get("args", []),
                "env": server_config.get("env", {}),
                "source": "claude_desktop",  # インポート元を記録
                "categories": ["imported", "claude-desktop"]
            }
            
            # serverの型チェック
            if isinstance(server_config.get("command"), str) and server_config.get("command"):
                cocoro_servers[f"claude_{server_name}"] = cocoro_config
            else:
                logger.warning(f"無効なMCPサーバー設定をスキップ: {server_name}")
        
        return cocoro_servers
    
    def merge_with_local_config(self, cocoro_config_path: str) -> Dict:
        """Claude Desktop設定とローカル設定をマージ"""
        # Claude Desktop設定を読み込み
        claude_servers = self.load_claude_mcp_config()
        converted_servers = self.convert_to_cocoro_format(claude_servers)
        
        # ローカル設定を読み込み
        local_servers = {}
        if os.path.exists(cocoro_config_path):
            try:
                with open(cocoro_config_path, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
                    local_servers = local_config.get("servers", {})
                logger.info(f"ローカル設定から{len(local_servers)}個のMCPサーバー設定を読み込みました")
            except json.JSONDecodeError as e:
                logger.error(f"ローカル設定ファイルのJSONエラー: {e}")
            except Exception as e:
                logger.error(f"ローカル設定の読み込みエラー: {e}")
        
        # マージ（ローカル設定が優先）
        merged_servers = {}
        merged_servers.update(converted_servers)  # Claude Desktop設定
        merged_servers.update(local_servers)      # ローカル設定で上書き
        
        logger.info(f"MCP設定マージ完了: Claude Desktop={len(converted_servers)}個, "
                   f"ローカル={len(local_servers)}個, 合計={len(merged_servers)}個")
        
        return {
            "version": "1.0",
            "auto_reload": True,
            "claude_desktop_sync": True,
            "servers": merged_servers
        }


def get_merged_mcp_config(cocoro_config_dir: str) -> Dict:
    """Claude DesktopとCocoroAIの設定をマージして取得"""
    importer = ClaudeMCPImporter()
    cocoro_config_path = os.path.join(cocoro_config_dir, "mcp_servers.json")
    
    return importer.merge_with_local_config(cocoro_config_path)