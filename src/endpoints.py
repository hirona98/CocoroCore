"""CocoroCore API エンドポイント定義"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI
from voice_processor import process_mic_input

logger = logging.getLogger(__name__)


def setup_endpoints(app: FastAPI, deps: Dict) -> None:
    """エンドポイントを設定する
    
    Args:
        app: FastAPIアプリケーション
        deps: 依存関係のオブジェクト辞書
    """
    # 依存関係を展開
    config = deps["config"]
    current_char = deps["current_char"]
    memory_enabled = deps["memory_enabled"]
    llm_model = deps["llm_model"]
    session_manager = deps["session_manager"]
    dock_log_handler = deps["dock_log_handler"]
    is_use_stt = deps["is_use_stt"]
    stt_api_key = deps["stt_api_key"]
    vad_instance = deps["vad_instance"]
    user_id = deps["user_id"]
    get_shared_context_id = deps["get_shared_context_id"]
    cocoro_dock_client = deps["cocoro_dock_client"]
    mic_input_task = deps["mic_input_task"]
    shutdown_handler = deps["shutdown_handler"]
    deps_container = deps["deps_container"]
    
    # ヘルスチェックエンドポイント（管理用）
    @app.get("/health")
    async def health_check():
        """ヘルスチェック用エンドポイント"""
        # MCP状態を取得（isEnableMcpがTrueの場合のみ）
        mcp_status = None
        if config.get("isEnableMcp", False):
            from mcp_tools import get_mcp_status
            mcp_status = await get_mcp_status()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "character": current_char.get("name", "unknown"),
            "memory_enabled": memory_enabled,
            "llm_model": llm_model,
            "active_sessions": session_manager.get_active_session_count(),
            "mcp_status": mcp_status,
        }

    # MCPツール登録ログ取得エンドポイント
    @app.get("/api/mcp/tool-registration-log")
    async def get_mcp_tool_registration_log():
        """MCPツール登録ログを取得"""
        # isEnableMcpがFalseの場合は空のログを返す
        if not config.get("isEnableMcp", False):
            return {
                "status": "success",
                "message": "MCPは無効になっています",
                "logs": []
            }
        
        try:
            from mcp_tools import get_mcp_tool_registration_log
            logs = get_mcp_tool_registration_log()
            return {
                "status": "success",
                "message": f"{len(logs)}件のログを取得しました",
                "logs": logs
            }
        except Exception as e:
            logger.error(f"MCPツール登録ログ取得エラー: {e}")
            return {
                "status": "error",
                "message": f"ログ取得に失敗しました: {e}",
                "logs": []
            }

    # 制御コマンドエンドポイント
    @app.post("/api/control")
    async def control(request: dict):
        """制御コマンドを実行"""
        command = request.get("command")
        params = request.get("params", {})
        reason = request.get("reason")

        if command == "shutdown":
            # シャットダウン処理
            grace_period = params.get("grace_period_seconds", 30)
            logger.info(
                f"制御コマンドによるシャットダウン要求: 理由={reason}, 猶予期間={grace_period}秒"
            )
            shutdown_handler.request_shutdown(grace_period)
            return {
                "status": "success",
                "message": "Shutdown requested",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        elif command == "sttControl":
            # STT（音声認識）制御
            enabled = params.get("enabled", True)
            logger.info(f"STT制御コマンド: enabled={enabled}")

            # is_use_sttフラグを更新
            deps_container.is_use_stt = enabled

            # マイク入力タスクの制御
            if enabled:
                # STTを有効化
                current_mic_task = deps_container.mic_input_task
                if not current_mic_task or current_mic_task.done():
                    # APIキーが設定されている場合のみ開始
                    if stt_api_key and vad_instance:
                        new_task = asyncio.create_task(
                            process_mic_input(vad_instance, user_id, get_shared_context_id, cocoro_dock_client)
                        )
                        deps_container.mic_input_task = new_task
                        return {
                            "status": "success",
                            "message": "STT enabled",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    else:
                        return {
                            "status": "error",
                            "message": "STT instances are not available (API key or VAD missing)",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                else:
                    return {
                        "status": "success",
                        "message": "STT is already enabled",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            else:
                # STTを無効化
                current_mic_task = deps_container.mic_input_task
                if current_mic_task and not current_mic_task.done():
                    logger.info("マイク入力タスクを停止します")
                    current_mic_task.cancel()
                    try:
                        await current_mic_task
                    except asyncio.CancelledError:
                        pass
                    return {
                        "status": "success",
                        "message": "STT disabled",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    return {
                        "status": "success",
                        "message": "STT is already disabled",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
        elif command == "microphoneControl":
            # マイクロフォン設定制御
            try:
                auto_adjustment = params.get("autoAdjustment", True)
                input_threshold = params.get("inputThreshold", -45.0)

                logger.info(
                    f"マイクロフォン制御コマンド: autoAdjustment={auto_adjustment}, inputThreshold={input_threshold:.1f}dB"
                )

                # VADインスタンスに設定を反映
                if vad_instance and hasattr(vad_instance, "update_settings"):
                    vad_instance.update_settings(auto_adjustment, input_threshold)
                    return {
                        "status": "success",
                        "message": "Microphone settings updated",
                        "autoAdjustment": auto_adjustment,
                        "inputThreshold": input_threshold,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    logger.warning("VADインスタンスが利用できません")
                    return {
                        "status": "error",
                        "message": "VAD instance is not available",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except Exception as e:
                logger.error(f"マイクロフォン設定更新エラー: {e}")
                return {
                    "status": "error",
                    "message": f"Microphone settings update error: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        elif command == "start_log_forwarding":
            # ログ転送開始
            try:
                if dock_log_handler is not None:
                    dock_log_handler.set_enabled(True)
                    logger.info("ログ転送を開始しました")
                    return {
                        "status": "success",
                        "message": "Log forwarding started",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    logger.warning("ログハンドラーが利用できません")
                    return {
                        "status": "error",
                        "message": "Log handler is not available",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except Exception as e:
                logger.error(f"ログ転送開始エラー: {e}")
                return {
                    "status": "error",
                    "message": f"Log forwarding start error: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        elif command == "stop_log_forwarding":
            # ログ転送停止
            try:
                if dock_log_handler is not None:
                    dock_log_handler.set_enabled(False)
                    logger.info("ログ転送を停止しました")
                    return {
                        "status": "success",
                        "message": "Log forwarding stopped",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                else:
                    return {
                        "status": "success",
                        "message": "Log forwarding was already stopped",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except Exception as e:
                logger.error(f"ログ転送停止エラー: {e}")
                return {
                    "status": "error",
                    "message": f"Log forwarding stop error: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        else:
            return {
                "status": "error",
                "message": f"Unknown command: {command}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }