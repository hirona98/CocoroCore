"""
REST API クライアント実装
統一API仕様書に準拠したCocoroDock/CocoroShellとの通信クライアント
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class CocoroDockClient:
    """CocoroDock との通信を管理するクライアント"""

    def __init__(self, base_url: str = "http://127.0.0.1:55600", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        # HTTPクライアントの設定を最適化
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0),  # 非同期化したので長めでOK
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=False,  # ローカル接続なのでHTTP/1.1で十分
        )

    async def send_chat_message(self, role: str, content: str) -> bool:
        """
        チャットメッセージをUIに送信

        Args:
            role: "user" または "assistant"
            content: メッセージ内容

        Returns:
            成功時True、失敗時False
        """
        payload = {"role": role, "content": content, "timestamp": datetime.now(timezone.utc).isoformat()}

        try:
            response = await self.client.post(f"{self.base_url}/api/addChatUi", json=payload)
            response.raise_for_status()
            logger.debug(f"CocoroDockへのメッセージ送信成功: role={role}")
            return True
        except httpx.ConnectError:
            logger.debug("CocoroDock未起動。処理を継続します。")
            return False
        except Exception as e:
            logger.error(f"CocoroDock送信エラー: {e}")
            return False

    async def get_config(self) -> Optional[Dict[str, Any]]:
        """
        現在の設定を取得

        Returns:
            設定辞書またはNone（エラー時）
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/config")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"設定取得エラー: {e}")
            return None

    async def update_config(self, config: Dict[str, Any]) -> bool:
        """
        設定を更新

        Args:
            config: 更新する設定の辞書

        Returns:
            成功時True、失敗時False
        """
        try:
            response = await self.client.put(f"{self.base_url}/api/config", json=config)
            response.raise_for_status()
            logger.info("設定更新成功")
            return True
        except Exception as e:
            logger.error(f"設定更新エラー: {e}")
            return False

    async def send_control_command(
        self, command: str, params: Optional[Dict[str, Any]] = None, reason: Optional[str] = None
    ) -> bool:
        """
        制御コマンドを送信

        Args:
            command: "shutdown", "restart", "reloadConfig"
            params: コマンドパラメータ
            reason: コマンド実行理由（オプション）

        Returns:
            成功時True、失敗時False
        """
        payload = {"command": command, "params": params or {}}
        if reason:
            payload["reason"] = reason

        try:
            response = await self.client.post(f"{self.base_url}/api/control", json=payload)
            response.raise_for_status()
            logger.info(f"制御コマンド送信成功: {command}")
            return True
        except Exception as e:
            logger.error(f"制御コマンドエラー: {command}, {e}")
            return False

    async def send_status_update(self, message: str, status_type: Optional[str] = None) -> bool:
        """
        ステータス更新をCocoroDockに送信

        Args:
            message: ステータスメッセージ
            status_type: ステータスタイプ（"voice_waiting", "amivoice_sending", "llm_sending", "memory_accessing"など）

        Returns:
            成功時True、失敗時False
        """
        payload = {"message": message, "timestamp": datetime.now(timezone.utc).isoformat()}
        if status_type:
            payload["type"] = status_type

        try:
            response = await self.client.post(f"{self.base_url}/api/status", json=payload)
            response.raise_for_status()
            logger.debug(f"ステータス更新送信成功: {message}")
            return True
        except httpx.ConnectError:
            logger.debug("CocoroDock未起動。ステータス更新をスキップします。")
            return False
        except Exception as e:
            logger.debug(f"ステータス更新エラー（正常動作）: {e}")
            return False

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()


class CocoroShellClient:
    """CocoroShell との通信を管理するクライアント"""

    def __init__(self, base_url: str = "http://127.0.0.1:55605", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        # HTTPクライアントの設定を最適化
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0),  # 非同期化したので長めでOK
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=False,  # ローカル接続なのでHTTP/1.1で十分
        )

    async def send_chat_for_speech(
        self,
        content: str,
        voice_params: Optional[Dict[str, Any]] = None,
        animation: Optional[str] = "talk",
        character_name: Optional[str] = None,
    ) -> bool:
        """
        音声合成付きでチャットメッセージを送信

        Args:
            content: 音声合成するテキスト
            voice_params: 音声パラメータ（speaker_id, speed, pitch, volume）
            animation: アニメーション（"talk", "idle", None）
            character_name: キャラクター名（オプション、複数キャラクター対応）

        Returns:
            成功時True、失敗時False
        """
        payload = {"content": content, "voice_params": voice_params or {}, "animation": animation}
        if character_name:
            payload["character_name"] = character_name

        try:
            response = await self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            logger.debug("CocoroShellへの音声合成要求成功")
            return True
        except httpx.ConnectError:
            logger.debug("CocoroShell未起動。処理を継続します。")
            return False
        except Exception as e:
            logger.error(f"CocoroShell送信エラー: {e}")
            return False

    async def send_animation(self, animation_name: str) -> bool:
        """
        アニメーションを制御

        Args:
            animation_name: アニメーション名

        Returns:
            成功時True、失敗時False
        """
        payload = {"animation_name": animation_name}

        try:
            response = await self.client.post(f"{self.base_url}/api/animation", json=payload)
            response.raise_for_status()
            logger.debug(f"アニメーション制御成功: {animation_name}")
            return True
        except Exception as e:
            logger.error(f"アニメーション制御エラー: {e}")
            return False

    async def send_control_command(
        self, command: str, params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        制御コマンドを送信

        Args:
            command: 制御コマンド（"shutdown"など）
            params: コマンドパラメータ

        Returns:
            成功時True、失敗時False
        """
        payload = {"command": command, "params": params or {}}

        try:
            response = await self.client.post(f"{self.base_url}/api/control", json=payload)
            response.raise_for_status()
            logger.info(f"制御コマンド送信成功: {command}")
            return True
        except Exception as e:
            logger.error(f"制御コマンドエラー: {command}, {e}")
            return False

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()
