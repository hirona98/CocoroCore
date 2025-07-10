"""MCP診断ツール"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


async def diagnose_mcp_servers(config_dir: str = None):
    """MCPサーバーの診断を実行"""
    logger.info("=== MCP サーバー診断を開始 ===")
    
    try:
        # 設定ディレクトリを取得（config_loaderと同じロジック）
        if config_dir is None:
            import sys
            if getattr(sys, "frozen", False):
                # PyInstallerなどで固められたexeの場合
                base_dir = os.path.dirname(sys.executable)
            else:
                # 通常のPythonスクリプトとして実行された場合
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            config_dir = os.path.join(base_dir, "UserData")
            
            # 基本ディレクトリに設定ファイルがない場合は親ディレクトリを確認
            setting_path = os.path.join(config_dir, "setting.json")
            if not os.path.exists(setting_path):
                parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                config_dir = os.path.join(parent_dir, "UserData")
                
                # 親ディレクトリに設定ファイルがない場合は親の親ディレクトリを確認
                setting_path = os.path.join(config_dir, "setting.json")
                if not os.path.exists(setting_path):
                    grandparent_dir = os.path.dirname(parent_dir)
                    config_dir = os.path.join(grandparent_dir, "UserData")
        
        # MCP設定ファイルを読み込み
        mcp_config_path = os.path.join(config_dir, "cocoroAiMcp.json")
        
        if not os.path.exists(mcp_config_path):
            logger.info("MCPサーバー設定ファイルが見つかりません: " + mcp_config_path)
            return
        
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        servers = config_data.get("mcpServers", {})
        
        if not servers:
            logger.info("診断対象のMCPサーバーがありません")
            return
        
        for server_name, server_config in servers.items():
            logger.info(f"\n--- {server_name} の診断 ---")
            
            
            command = server_config.get("command", "")
            args = server_config.get("args", [])
            env_vars = server_config.get("env", {})
            
            # 1. コマンドの存在確認
            logger.info(f"コマンド: {command}")
            logger.info(f"引数: {args}")
            
            if not command:
                logger.error("❌ コマンドが指定されていません")
                continue
            
            if not shutil.which(command):
                logger.error(f"❌ コマンドが見つかりません: {command}")
                continue
            else:
                logger.info(f"✅ コマンドが見つかりました: {shutil.which(command)}")
            
            # 2. 環境変数の確認
            # Windows環境では空の環境変数辞書を渡すとエラーになるため、
            # 現在の環境変数をベースにして追加の環境変数をマージ
            processed_env = os.environ.copy()
            
            for key, value in env_vars.items():
                if isinstance(value, str) and value.startswith("env:"):
                    env_var_name = value[4:]
                    env_value = os.environ.get(env_var_name)
                    if env_value:
                        processed_env[key] = env_value
                        logger.info(f"✅ 環境変数 {env_var_name} は設定されています")
                    else:
                        logger.warning(f"⚠️ 環境変数 {env_var_name} が見つかりません")
                else:
                    processed_env[key] = value
            
            # 3. コマンドの実行テスト（バージョン確認など）
            logger.info("コマンド実行テスト...")
            try:
                if command == "npx":
                    # npxの場合はバージョン確認
                    result = subprocess.run(
                        [command, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ npx バージョン: {result.stdout.strip()}")
                    else:
                        logger.warning(f"⚠️ npx実行エラー: {result.stderr}")
                    
                    # npmの存在確認
                    npm_result = subprocess.run(
                        ["npm", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if npm_result.returncode == 0:
                        logger.info(f"✅ npm バージョン: {npm_result.stdout.strip()}")
                    else:
                        logger.warning(f"⚠️ npm実行エラー: {npm_result.stderr}")
                    
                    # NPXパッケージの存在確認
                    if args:
                        package_name = None
                        if "-y" in args:
                            try:
                                y_index = args.index("-y")
                                if y_index + 1 < len(args):
                                    package_name = args[y_index + 1]
                            except ValueError:
                                pass
                        if not package_name and args:
                            package_name = args[0]
                        
                        if package_name:
                            logger.info(f"NPXパッケージ確認: {package_name}")
                            npm_view_result = subprocess.run(
                                ["npm", "view", package_name, "name"],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            if npm_view_result.returncode == 0:
                                logger.info(f"✅ NPXパッケージが利用可能: {package_name}")
                            else:
                                logger.error(f"❌ NPXパッケージが見つかりません: {package_name}")
                                logger.debug(f"npm view エラー: {npm_view_result.stderr}")
                
                elif command == "python":
                    # Pythonの場合はバージョン確認
                    result = subprocess.run(
                        [command, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ Python バージョン: {result.stdout.strip()}")
                    else:
                        logger.warning(f"⚠️ Python実行エラー: {result.stderr}")
                
                else:
                    logger.info(f"⚪ {command} の詳細テストはスキップ")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️ {command} の実行がタイムアウトしました")
            except Exception as e:
                logger.warning(f"⚠️ {command} の実行テストに失敗: {e}")
            
            # 4. 特定のMCPサーバーに対する追加チェック
            if "filesystem" in server_name.lower():
                # ファイルシステムサーバーの場合、指定されたパスの確認
                if args and len(args) > 2:
                    for arg in args[2:]:  # npx -y @modelcontextprotocol/server-filesystem の後の引数
                        if os.path.exists(arg):
                            logger.info(f"✅ パスが存在します: {arg}")
                        else:
                            logger.warning(f"⚠️ パスが見つかりません: {arg}")
            
            elif "playwright" in server_name.lower():
                # Playwrightサーバーの場合
                logger.info("⚪ Playwrightサーバーは追加のセットアップが必要な場合があります")
            
            # 5. 簡易接続テスト（実際のMCPプロトコルではなく、プロセス起動のみ）
            logger.info("簡易接続テスト...")
            try:
                # Windows環境では空の環境変数辞書を渡すとエラーになるため、
                # 現在の環境変数をベースにして追加の環境変数をマージ
                full_env = processed_env  # 既にos.environ.copy()済み
                
                # Windows環境でコンソールウィンドウを非表示にする
                import platform
                creation_flags = 0
                if platform.system() == "Windows":
                    import subprocess
                    creation_flags = subprocess.CREATE_NO_WINDOW
                
                process = await asyncio.create_subprocess_exec(
                    command, *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=full_env,
                    creationflags=creation_flags
                )
                
                # プロセスの起動を確認
                logger.debug(f"MCPサーバープロセス PID: {process.pid}")
                
                # 2秒待ってプロセスの状態を確認
                await asyncio.sleep(2)
                
                if process.returncode is None:
                    logger.info("✅ プロセス起動成功（MCP通信は未テスト）")
                    
                    # MCPサーバーとの基本的な通信テスト（JSON-RPC初期化メッセージ）
                    logger.info("MCP初期化テスト...")
                    try:
                        # MCPプロトコルの初期化メッセージを送信
                        init_message = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {
                                    "name": "CocoroCore",
                                    "version": "1.0.0"
                                }
                            }
                        }
                        
                        # メッセージを送信
                        message_json = json.dumps(init_message) + "\n"
                        process.stdin.write(message_json.encode('utf-8'))
                        await process.stdin.drain()
                        
                        # 応答を待機（3秒間）
                        try:
                            stdout_data = await asyncio.wait_for(
                                process.stdout.readline(),
                                timeout=3.0
                            )
                            if stdout_data:
                                response = stdout_data.decode('utf-8').strip()
                                logger.info(f"✅ MCP応答受信: {response[:100]}...")
                            else:
                                logger.warning("⚠️ MCP応答がありません")
                        except asyncio.TimeoutError:
                            logger.warning("⚠️ MCP応答タイムアウト (3秒)")
                            
                    except Exception as mcp_test_error:
                        logger.warning(f"⚠️ MCP通信テストでエラー: {mcp_test_error}")
                    
                    # プロセスを終了
                    process.terminate()
                    await process.wait()
                else:
                    stderr_data = await process.stderr.read()
                    stdout_data = await process.stdout.read()
                    logger.error(f"❌ プロセスが即座に終了: exit code {process.returncode}")
                    if stderr_data:
                        logger.error(f"エラー出力: {stderr_data.decode('utf-8', errors='ignore')}")
                    if stdout_data:
                        logger.info(f"標準出力: {stdout_data.decode('utf-8', errors='ignore')}")
                
            except Exception as e:
                logger.error(f"❌ プロセス起動に失敗: {e}")
        
        logger.info("\n=== MCP サーバー診断完了 ===")
        
    except Exception as e:
        logger.error(f"診断中にエラーが発生しました: {e}")


if __name__ == "__main__":
    # スタンドアローンで実行する場合
    logging.basicConfig(level=logging.INFO)
    asyncio.run(diagnose_mcp_servers())