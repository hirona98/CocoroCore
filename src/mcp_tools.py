"""MCPサーバーと統合するLLMツール（JSON-RPC直接通信版）"""

import asyncio
import json
import logging
import os
import signal
from typing import Dict, List, Optional, Any
from claude_mcp_importer import get_merged_mcp_config

logger = logging.getLogger(__name__)
# デバッグログを有効化
logger.setLevel(logging.DEBUG)


class MCPServerManager:
    """MCPサーバーの管理とライフサイクル制御（JSON-RPC直接通信版）"""
    
    def __init__(self, servers_config: Dict):
        self.servers_config = servers_config
        self.available_tools: Dict[str, Any] = {}
        self.server_processes = {}
        
    async def connect_server(self, server_name: str, server_config: dict):
        """MCPサーバーに接続（JSON-RPC方式のみ）"""
        if not server_config.get("enabled", True):
            logger.info(f"MCPサーバー '{server_name}' は無効化されています")
            return
        
        logger.info(f"MCPサーバー '{server_name}' に接続中（JSON-RPC方式）...")
        
        try:
            await self._connect_server_jsonrpc(server_name, server_config)
            logger.info(f"MCPサーバー '{server_name}' 接続成功")
        except Exception as e:
            logger.error(f"MCPサーバー '{server_name}' の接続に失敗: {e}")
            logger.warning(f"MCPサーバー '{server_name}' の接続をスキップします")
    
    async def _check_npx_package(self, args: list, env: dict) -> bool:
        """npxパッケージが利用可能かチェック"""
        if not args:
            return False
        
        # 最初の引数がパッケージ名の場合がほとんど
        # npx -y @modelcontextprotocol/server-filesystem のような形式
        package_name = None
        
        # -y オプションがある場合は次の引数がパッケージ名
        if "-y" in args:
            try:
                y_index = args.index("-y")
                if y_index + 1 < len(args):
                    package_name = args[y_index + 1]
            except ValueError:
                pass
        
        # -y オプションがない場合は最初の引数がパッケージ名
        if not package_name and args:
            package_name = args[0]
        
        if not package_name:
            logger.warning("NPXパッケージ名を特定できません")
            return True  # 特定できない場合は通す
        
        try:
            # パッケージの存在確認（npm view コマンドを使用）
            import subprocess
            import os
            
            # Windows環境では空の環境変数辞書を渡すとエラーになるため、
            # 現在の環境変数をベースにして追加の環境変数をマージ
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
            
            result = await asyncio.create_subprocess_exec(
                "npm", "view", package_name, "name",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10.0)
            
            if result.returncode == 0:
                logger.info(f"✅ NPXパッケージが利用可能: {package_name}")
                return True
            else:
                logger.error(f"❌ NPXパッケージが見つかりません: {package_name}")
                logger.debug(f"npm view エラー: {stderr.decode('utf-8', errors='ignore')}")
                return False
        
        except asyncio.TimeoutError:
            logger.warning(f"NPXパッケージ確認がタイムアウト: {package_name}")
            return False
        except Exception as e:
            logger.error(f"NPXパッケージ確認エラー: {e}")
            return False
    
    async def _connect_server_jsonrpc(self, server_name: str, server_config: dict):
        """JSON-RPC方式でMCPサーバーに接続（anyio問題を完全回避）"""
        
        logger.info(f"MCPサーバー '{server_name}' にJSON-RPC方式で接続中...")
        
        command = server_config.get("command", "")
        args = server_config.get("args", [])
        env_vars = server_config.get("env", {})
        
        if not command:
            raise ValueError(f"MCPサーバー '{server_name}' のコマンドが設定されていません")
        
        # 環境変数の処理
        processed_env = os.environ.copy()
        for key, value in env_vars.items():
            if isinstance(value, str) and value.startswith("env:"):
                env_var_name = value[4:]
                env_value = os.environ.get(env_var_name)
                if env_value:
                    processed_env[key] = env_value
            else:
                processed_env[key] = value
        
        # コマンドの存在確認
        import shutil
        if not shutil.which(command):
            raise ValueError(f"コマンドが見つかりません: {command}")
        
        # npxの場合はパッケージ確認
        if command == "npx" and args:
            package_check = await self._check_npx_package(args, processed_env)
            if not package_check:
                raise ValueError(f"NPXパッケージが利用できません: {' '.join(args)}")
        
        # プロセスを直接起動
        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=processed_env
        )
        
        logger.debug(f"MCPサーバープロセス起動成功 PID: {process.pid}")
        
        try:
            # 1. 初期化メッセージ送信
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "CocoroCore", "version": "1.0.0"}
                }
            }
            
            message_json = json.dumps(init_message) + "\n"
            process.stdin.write(message_json.encode('utf-8'))
            await process.stdin.drain()
            
            # 初期化応答待機
            response_line = await asyncio.wait_for(
                process.stdout.readline(), 
                timeout=10.0
            )
            
            if not response_line:
                raise Exception("初期化応答がありません")
            
            init_response = json.loads(response_line.decode('utf-8').strip())
            logger.info(f"MCPサーバー '{server_name}' 初期化成功")
            logger.debug(f"初期化応答: {init_response}")
            
            # 2. tools/list リクエスト送信
            tools_message = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            message_json = json.dumps(tools_message) + "\n"
            process.stdin.write(message_json.encode('utf-8'))
            await process.stdin.drain()
            
            # ツールリスト応答待機
            tools_response_line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=10.0
            )
            
            if not tools_response_line:
                logger.warning(f"MCPサーバー '{server_name}' からツールリスト応答なし")
                return
            
            tools_response = json.loads(tools_response_line.decode('utf-8').strip())
            logger.debug(f"ツールリスト応答: {tools_response}")
            
            # 3. ツール登録
            if 'result' in tools_response and 'tools' in tools_response['result']:
                tools = tools_response['result']['tools']
                logger.info(f"MCPサーバー '{server_name}' から {len(tools)} 個のツールを取得")
                
                for tool in tools:
                    tool_key = f"{server_name}_{tool['name']}"
                    self.available_tools[tool_key] = {
                        "server": server_name,
                        "tool": tool,
                        "process": process,
                        "config": server_config,
                        "jsonrpc_mode": True
                    }
                    logger.info(f"ツール登録（JSON-RPC）: {tool_key} - {tool.get('description', '')}")
                
                # プロセスを保存
                self.server_processes[server_name] = process
                logger.info(f"MCPサーバー '{server_name}' 接続完了（JSON-RPC方式）")
                
            else:
                logger.warning(f"MCPサーバー '{server_name}' からツールリストを取得できませんでした")
                logger.debug(f"応答内容: {tools_response}")
                
        except asyncio.TimeoutError:
            logger.error(f"MCPサーバー '{server_name}' の通信がタイムアウトしました")
            process.terminate()
            await process.wait()
            raise
        except Exception as e:
            logger.error(f"MCPサーバー '{server_name}' のJSON-RPC接続でエラー: {e}")
            process.terminate()
            await process.wait()
            raise
    
    
    async def _execute_tool_jsonrpc(self, tool_info: dict, arguments: dict):
        """JSON-RPC方式でのツール実行（直接JSON-RPC通信）"""
        import time
        
        tool = tool_info["tool"]
        process = tool_info["process"]
        
        # tools/call リクエスト作成（動的なIDを使用）
        request_id = int(time.time() * 1000) % 10000  # タイムスタンプベースのID
        call_message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool["name"],
                "arguments": arguments
            }
        }
        
        logger.debug(f"ツール実行リクエスト: {call_message}")
        
        try:
            # リクエスト送信
            message_json = json.dumps(call_message) + "\n"
            process.stdin.write(message_json.encode('utf-8'))
            await process.stdin.drain()
            
            # 応答待機
            response_line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=30.0  # ツール実行は時間がかかる可能性
            )
            
            if not response_line:
                raise Exception("ツール実行応答がありません")
            
            response = json.loads(response_line.decode('utf-8').strip())
            logger.debug(f"ツール実行応答: {response}")
            
            # エラーチェック
            if "error" in response:
                error_info = response["error"]
                raise Exception(f"MCPツールエラー: {error_info.get('message', 'Unknown error')}")
            
            # 結果の処理
            if "result" in response:
                result_data = response["result"]
                if "content" in result_data:
                    content = result_data["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # 最初のコンテンツを返す
                        first_content = content[0]
                        if "text" in first_content:
                            return first_content["text"]
                        else:
                            return str(first_content)
                    else:
                        return str(content)
                else:
                    return "ツールが正常に実行されました（結果なし）"
            else:
                return "ツール実行が完了しました"
                
        except asyncio.TimeoutError:
            logger.error(f"MCPツール '{tool['name']}' の実行がタイムアウトしました")
            raise Exception("ツールの実行がタイムアウトしました")
        except json.JSONDecodeError as e:
            logger.error(f"MCPツール応答のJSON解析に失敗: {e}")
            raise Exception("ツール応答の解析に失敗しました")
    
    async def _cleanup_server(self, server_name: str):
        """サーバーのクリーンアップ"""
        try:
            # JSON-RPCプロセスをクリーンアップ
            if server_name in self.server_processes:
                process = self.server_processes[server_name]
                try:
                    if process.returncode is None:
                        process.terminate()
                        await asyncio.wait_for(process.wait(), timeout=3.0)
                except Exception as e:
                    logger.debug(f"プロセス終了エラー: {e}")
                del self.server_processes[server_name]
            
            # ツールを削除
            to_remove = [key for key in self.available_tools.keys() 
                        if key.startswith(f"{server_name}_")]
            for key in to_remove:
                del self.available_tools[key]
                
        except Exception as e:
            logger.error(f"サーバー '{server_name}' のクリーンアップに失敗: {e}")
    
    async def disconnect_server(self, server_name: str):
        """MCPサーバーから切断"""
        if server_name in self.server_processes:
            logger.info(f"MCPサーバー '{server_name}' を切断中...")
            await self._cleanup_server(server_name)
            logger.info(f"MCPサーバー '{server_name}' を切断しました")
    
    async def connect_all_servers(self):
        """すべてのMCPサーバーに接続"""
        if not self.servers_config:
            logger.info("接続するMCPサーバーがありません")
            return
        
        # 順次接続（並列接続でのタスクスコープの問題を回避）
        for server_name, server_config in self.servers_config.items():
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    await asyncio.wait_for(
                        self.connect_server(server_name, server_config),
                        timeout=15.0
                    )
                    break  # 成功したらループを抜ける
                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        logger.warning(f"MCPサーバー '{server_name}' の接続がタイムアウト (試行 {attempt + 1}/{max_retries})")
                        await asyncio.sleep(2)  # 2秒待ってからリトライ
                    else:
                        logger.error(f"MCPサーバー '{server_name}' の接続がタイムアウトしました (最大試行回数到達)")
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"MCPサーバー '{server_name}' の接続でエラー (試行 {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(2)  # 2秒待ってからリトライ
                    else:
                        logger.error(f"MCPサーバー '{server_name}' の接続でエラー (最大試行回数到達): {e}")
        
        # 接続されたサーバー数（JSON-RPCプロセスのみ）
        connected_servers = set(self.server_processes.keys())
        connected_count = len(connected_servers)
        total_tools = len(self.available_tools)
        logger.info(f"MCP接続完了: {connected_count}個のサーバー, {total_tools}個のツール")
        
        # 接続されたサーバーとツールの詳細をログ出力
        for server_name in connected_servers:
            server_tools = [key for key in self.available_tools.keys() if key.startswith(f"{server_name}_")]
            logger.info(f"  {server_name} (JSON-RPC): {len(server_tools)}個のツール")
        
        # 接続に失敗した場合は診断を実行
        if connected_count == 0 and len(self.servers_config) > 0:
            logger.info("すべてのMCPサーバー接続に失敗しました。診断を実行します...")
            try:
                from mcp_diagnostics import diagnose_mcp_servers
                await diagnose_mcp_servers()
            except Exception as e:
                logger.error(f"MCP診断の実行に失敗: {e}")
    
    async def execute_tool(self, tool_key: str, arguments: dict):
        """MCPツールを実行（JSON-RPC方式のみ）"""
        if tool_key not in self.available_tools:
            raise ValueError(f"ツール '{tool_key}' が見つかりません")
        
        tool_info = self.available_tools[tool_key]
        server_name = tool_info["server"]
        
        try:
            logger.debug(f"MCPツール実行: {tool_key} with {arguments}")
            
            # JSON-RPC方式でツール実行
            result = await self._execute_tool_jsonrpc(tool_info, arguments)
            return result
            
        except Exception as e:
            logger.error(f"MCPツール '{tool_key}' の実行に失敗: {e}")
            
            # プロセスが終了している場合は再接続を試行
            if "broken" in str(e).lower() or "connection" in str(e).lower():
                logger.info(f"MCPサーバー '{server_name}' への再接続を試行します")
                await self.disconnect_server(server_name)
                server_config = tool_info["config"]
                await self.connect_server(server_name, server_config)
            
            raise Exception(f"ツールの実行に失敗しました: {str(e)}")
    
    async def disconnect_all_servers(self):
        """すべてのMCPサーバーを切断"""
        disconnect_tasks = []
        for server_name in list(self.server_processes.keys()):
            task = self.disconnect_server(server_name)
            disconnect_tasks.append(task)
        
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            logger.info("すべてのMCPサーバーを切断しました")
    
    def get_server_info(self):
        """サーバー情報を取得"""
        servers_info = {}
        connected_servers = set(self.server_processes.keys())
        
        for server_name in self.servers_config.keys():
            is_connected = server_name in connected_servers
            tool_count = len([t for t in self.available_tools.keys() if t.startswith(f"{server_name}_")])
            source = self.servers_config[server_name].get("source", "local")
            connection_type = "jsonrpc" if server_name in self.server_processes else "none"
            
            servers_info[server_name] = {
                "connected": is_connected,
                "tool_count": tool_count,
                "source": source,
                "connection_type": connection_type
            }
        
        return {
            "total_servers": len(self.servers_config),
            "connected_servers": len(connected_servers),
            "total_tools": len(self.available_tools),
            "servers": servers_info
        }


# グローバルなMCPマネージャー
mcp_manager = None
_pending_mcp_init = None


def setup_mcp_tools(sts, config, cocoro_dock_client=None):
    """MCPツールをセットアップ（JSON-RPC直接通信版）"""
    global mcp_manager
    
    # 設定ディレクトリを取得
    config_dir = getattr(config, '_config_dir', './UserData')
    if hasattr(config, 'get'):
        # 辞書型の場合は、設定ディレクトリを推測
        config_dir = './UserData'
    
    try:
        # Claude Desktop設定とマージしたMCP設定を取得
        merged_config = get_merged_mcp_config(config_dir)
        servers = merged_config.get("servers", {})
        
        if not servers:
            logger.info("利用可能なMCPサーバーがありません")
            return ""
        
        # 設定されたサーバー数をログ出力
        claude_servers = [name for name, cfg in servers.items() if cfg.get("source") == "claude_desktop"]
        local_servers = [name for name, cfg in servers.items() if cfg.get("source") != "claude_desktop"]
        
        logger.info(f"MCP設定読み込み完了: Claude Desktop={len(claude_servers)}個, ローカル={len(local_servers)}個")
        
        # MCPサーバーマネージャーの初期化
        mcp_manager = MCPServerManager(servers)
        
        async def initialize_mcp_system():
            """MCPシステムを初期化"""
            try:
                await mcp_manager.connect_all_servers()
                await register_dynamic_tools(sts, mcp_manager, cocoro_dock_client)
                logger.info("MCPシステムの初期化が完了しました")
            except Exception as e:
                logger.error(f"MCPシステムの初期化に失敗: {e}")
        
        # 非同期でMCPシステムを初期化
        try:
            # イベントループが実行中かチェック
            asyncio.get_running_loop()
            # 実行中のループがある場合はタスクを作成
            asyncio.create_task(initialize_mcp_system())
        except RuntimeError:
            # イベントループが開始されていない場合は後で実行するように保存
            logger.info("イベントループが開始されていません。初期化を遅延実行します")
            # グローバル変数で初期化関数を保存
            global _pending_mcp_init
            _pending_mcp_init = initialize_mcp_system
        
        # システムプロンプトに追加する説明
        claude_server_list = ", ".join([name.replace("claude_", "") for name in claude_servers]) if claude_servers else "なし"
        local_server_list = ", ".join(local_servers) if local_servers else "なし"
        
        prompt_addition = (
            f"\n\n"
            f"MCPツールが利用可能です（JSON-RPC直接通信）:\n"
            f"- Claude Desktopからインポート: {claude_server_list}\n"
            f"- ローカル設定: {local_server_list}\n"
            f"- ツール実行時にソース（[Claude]/[Local]）を表示\n"
            f"- 直接JSON-RPC通信で動作（anyioライブラリ不要）\n"
            f"- 実際のMCPサーバーと通信してツールを実行\n"
            f"- 利用可能なツールは起動時に自動検出されます\n"
        )
        
        return prompt_addition
        
    except Exception as e:
        logger.error(f"MCP設定の読み込みに失敗: {e}")
        return ""


async def register_dynamic_tools(sts, manager: MCPServerManager, cocoro_dock_client=None):
    """利用可能なMCPツールを動的に登録"""
    registered_count = 0
    
    for tool_key, tool_info in manager.available_tools.items():
        tool = tool_info["tool"]
        server_config = tool_info["config"]
        
        # ツール名にソース情報を追加
        source_prefix = "[Claude]" if server_config.get("source") == "claude_desktop" else "[Local]"
        
        # MCPツールの入力スキーマをAIAvatarKit形式に変換
        # JSON-RPC方式では辞書形式でツール情報が返される
        parameters = tool.get('inputSchema', {
            "type": "object",
            "properties": {},
            "required": []
        })
        description = tool.get('description', '')
        
        tool_spec = {
            "type": "function",
            "function": {
                "name": tool_key,
                "description": f"{source_prefix} {description}",
                "parameters": parameters
            }
        }
        
        # 動的ツール実行関数を作成
        async def execute_mcp_tool(tool_name=tool_key, **kwargs):
            """実際のMCPツールを実行"""
            if cocoro_dock_client:
                asyncio.create_task(
                    cocoro_dock_client.send_status_update(
                        f"MCPツール実行中: {tool_name}", 
                        status_type="mcp_executing"
                    )
                )
            
            try:
                result = await manager.execute_tool(tool_name, kwargs)
                return result
            except Exception as e:
                logger.error(f"MCPツール '{tool_name}' の実行エラー: {e}")
                return f"ツールの実行に失敗しました: {str(e)}"
        
        # AIAvatarKitにツールを登録
        try:
            sts.llm.tool(tool_spec)(execute_mcp_tool)
            registered_count += 1
            logger.debug(f"ツール登録成功: {tool_key}")
        except Exception as e:
            logger.error(f"ツール登録失敗: {tool_key} - {e}")
            logger.debug(f"tool_spec: {tool_spec}")
            logger.debug(f"tool info: {tool_info}")
    
    logger.info(f"MCPツールの登録が完了しました: {registered_count}個のツール")


async def get_mcp_status():
    """MCPシステムの状態を取得"""
    if mcp_manager:
        return mcp_manager.get_server_info()
    return {"error": "MCPマネージャーが初期化されていません"}


async def initialize_mcp_if_pending():
    """保留中のMCP初期化を実行"""
    global _pending_mcp_init
    if _pending_mcp_init:
        logger.info("保留中のMCP初期化を実行します")
        try:
            await _pending_mcp_init()
            _pending_mcp_init = None
        except Exception as e:
            logger.error(f"保留中のMCP初期化に失敗: {e}")


async def shutdown_mcp_system():
    """MCPシステムをシャットダウン"""
    global mcp_manager
    if mcp_manager:
        logger.info("MCPシステムをシャットダウンします...")
        await mcp_manager.disconnect_all_servers()
        logger.info("MCPシステムのシャットダウンが完了しました")