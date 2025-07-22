"""ChatMemoryサービスとの通信を管理するクライアント"""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """メッセージタイプの定義"""

    USER_CHAT = "user_chat"
    NOTIFICATION = "notification"
    DESKTOP_MONITORING = "desktop_monitoring"


class ChatMemoryClient:
    """ChatMemoryサービスとの通信を管理するクライアント"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # 非同期化したので通常のタイムアウト設定に戻す
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0))
        self._message_queue: List[Dict] = []
        self._queue_lock = asyncio.Lock()

    async def enqueue_messages(self, request, response):
        """メッセージタイプに応じた適切な保存処理"""
        # response.textが空の場合はスキップ
        if not response.text:
            logger.debug(f"空のレスポンスをスキップ: assistant_content={response.text}")
            return

        async with self._queue_lock:
            # メッセージタイプを判定
            message_type = self._determine_message_type(request)

            # タイプ別処理
            if message_type == MessageType.NOTIFICATION:
                await self._handle_notification_message(request, response)
            elif message_type == MessageType.DESKTOP_MONITORING:
                await self._handle_desktop_monitoring_message(request, response)
            else:  # MessageType.USER_CHAT
                await self._handle_user_chat_message(request, response)

    def _determine_message_type(self, request: Any) -> MessageType:
        """リクエストからメッセージタイプを判定"""
        request_text = request.text or ""

        # 優先順位1: 通知メッセージ
        if "<cocoro-notification>" in request_text:
            return MessageType.NOTIFICATION

        # 優先順位2: デスクトップモニタリング
        if "<cocoro-desktop-monitoring>" in request_text:
            return MessageType.DESKTOP_MONITORING

        # 優先順位3: 通常のユーザーチャット
        return MessageType.USER_CHAT

    async def _handle_notification_message(self, request: Any, response: Any) -> None:
        """通知メッセージの処理"""
        user_metadata = self._build_user_metadata(request)

        # 通知タグから情報を直接抽出
        notification_info = self._extract_notification_info(request.text or "")
        notification_from = notification_info.get("from", "不明なアプリ")
        notification_message = notification_info.get("message", "")

        # 画像付き通知の場合
        if user_metadata.get("image_description"):
            image_info = user_metadata["image_description"]
            classification = self._build_classification(user_metadata)

            content = f"[画像付き通知: {notification_from}] {notification_message}\n[画像内容: {image_info}]{classification}"
            logger.info(f"画像付き通知メッセージをシステムメッセージとして履歴に追加: from={notification_from}")
        else:
            content = f"[通知: {notification_from}] {notification_message}"
            logger.info(f"通知メッセージをシステムメッセージとして履歴に追加: from={notification_from}")

        # systemロールで保存
        self._message_queue.append(
            {
                "role": "system",
                "content": content,
                "metadata": user_metadata,
            }
        )

        # アシスタントの応答を追加
        self._add_assistant_response(request, response)

    async def _handle_desktop_monitoring_message(self, request: Any, response: Any) -> None:
        """デスクトップモニタリングメッセージの処理"""
        user_metadata = self._build_user_metadata(request)

        # 画像説明が必須
        if not user_metadata.get("image_description"):
            logger.warning("デスクトップモニタリングに画像説明がありません")
            return

        image_info = user_metadata["image_description"]
        classification = self._build_classification(user_metadata)

        # systemロールで画像説明のみ保存
        self._message_queue.append(
            {
                "role": "system",
                "content": f"[画像が共有されました: {image_info}]{classification}",
                "metadata": {
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "type": "image_description",
                    "image_category": user_metadata.get("image_category", ""),
                    "image_mood": user_metadata.get("image_mood", ""),
                    "image_time": user_metadata.get("image_time", ""),
                },
            }
        )

        logger.info("デスクトップモニタリング画像説明をシステムメッセージとして履歴に追加")

        # userメッセージは保存しない
        # アシスタントの応答を追加
        self._add_assistant_response(request, response)

    async def _handle_user_chat_message(self, request: Any, response: Any) -> None:
        """通常のユーザーチャットメッセージの処理"""
        # request.textが空の場合はスキップ
        if not request.text:
            logger.debug("空のユーザーメッセージをスキップ")
            return

        user_metadata = self._build_user_metadata(request)

        # 画像がある場合
        if user_metadata.get("image_description"):
            # 画像説明をsystemロールで保存
            image_info = user_metadata["image_description"]
            classification = self._build_classification(user_metadata)

            self._message_queue.append(
                {
                    "role": "system",
                    "content": f"[画像が共有されました: {image_info}]{classification}",
                    "metadata": {
                        "session_id": request.session_id,
                        "user_id": request.user_id,
                        "type": "image_description",
                        "image_category": user_metadata.get("image_category", ""),
                        "image_mood": user_metadata.get("image_mood", ""),
                        "image_time": user_metadata.get("image_time", ""),
                    },
                }
            )

            logger.info(f"画像説明をシステムメッセージとして履歴に追加: {image_info[:30]}...")

            # 画像プレフィックスを除去してuserメッセージを保存
            cleaned_text = self._remove_image_prefix(request.text)
            if cleaned_text:
                self._message_queue.append(
                    {
                        "role": "user",
                        "content": cleaned_text,
                        "metadata": user_metadata,
                    }
                )
        else:
            # 画像がない通常のメッセージ
            self._message_queue.append(
                {
                    "role": "user",
                    "content": request.text,
                    "metadata": user_metadata,
                }
            )

        # アシスタントの応答を追加
        self._add_assistant_response(request, response)

    def _build_user_metadata(self, request: Any) -> Dict[str, Any]:
        """ユーザーメタデータを構築"""
        user_metadata = {"session_id": request.session_id, "user_id": request.user_id}
        if hasattr(request, "metadata") and request.metadata:
            user_metadata.update(request.metadata)
        return user_metadata

    def _extract_notification_info(self, text: str) -> Dict[str, str]:
        """通知タグからJSON形式の情報を抽出"""
        import re
        import json

        if not text or "<cocoro-notification>" not in text:
            return {}

        notification_pattern = r"<cocoro-notification>\s*(.*?)\s*</cocoro-notification>"
        match = re.search(notification_pattern, text, re.DOTALL)

        if match:
            content = match.group(1).strip()
            try:
                return json.loads(content)
            except Exception as e:
                logger.error(f"通知JSON解析エラー: {e}")
                return {}

        return {}

    def _build_classification(self, metadata: Dict[str, Any]) -> str:
        """分類情報を構築"""
        category = metadata.get("image_category", "")
        mood = metadata.get("image_mood", "")
        time = metadata.get("image_time", "")

        if category or mood or time:
            return f" (分類: {category}/{mood}/{time})"
        return ""

    def _add_assistant_response(self, request: Any, response: Any) -> None:
        """アシスタントの応答を追加"""
        self._message_queue.append(
            {
                "role": "assistant",
                "content": response.text,
                "metadata": {"session_id": request.session_id, "user_id": request.user_id},
            }
        )

    def _remove_image_prefix(self, text: str) -> str:
        """画像プレフィックスを除去"""
        import re

        # 複数のパターンに対応
        patterns = [
            r"^\[画像を共有しました: .+?\](?:\n(.+))?$",
            r"^\[画像: .+?\](?:\n(.+))?$",
            r"^\[\d+枚の画像: .+?\](?:\n(.+))?$",
            # 通知の画像パターンも追加
            r"^\[.+?から画像付き通知: .+?\](?:\n(.+))?$",
            r"^\[.+?から\d+枚の画像付き通知: .+?\](?:\n(.+))?$",
        ]

        for pattern in patterns:
            match = re.match(pattern, text, re.DOTALL)
            if match:
                return match.group(1) or ""

        return text

    async def save_history(self, user_id: str, session_id: str, channel: str = "cocoro_ai"):
        """キューに溜まったメッセージを履歴として保存"""
        async with self._queue_lock:
            if not self._message_queue:
                return

            messages = self._message_queue.copy()
            self._message_queue.clear()

        try:
            response = await self.client.post(
                f"{self.base_url}/history",
                json={
                    "user_id": user_id,
                    "session_id": session_id,
                    "channel": channel,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            logger.info(f"履歴を保存しました: {len(messages)}件のメッセージ")
        except httpx.ConnectError:
            logger.debug("ChatMemory未起動。処理を継続します。")
            # 失敗したメッセージをキューに戻す
            async with self._queue_lock:
                self._message_queue = messages + self._message_queue
        except Exception as e:
            logger.error(f"履歴の保存に失敗しました: {e}")
            # 失敗したメッセージをキューに戻す
            async with self._queue_lock:
                self._message_queue = messages + self._message_queue

    async def search(self, user_id: str, query: str, top_k: int = 5) -> Optional[dict]:
        """記憶検索（高速）"""
        try:
            response = await self.client.post(
                f"{self.base_url}/search_direct",
                json={
                    "user_id": user_id,
                    "query": query,
                    "top_k": top_k,
                },
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                logger.error(f"記憶検索エラー: {result['error']}")
                return None

            return result
        except httpx.ConnectError:
            logger.debug("ChatMemory未起動。処理を継続します。")
            return None
        except Exception as e:
            logger.error(f"記憶検索に失敗しました: {e}")
            return None

    async def create_summary(self, user_id: str, session_id: str = None):
        """指定したセッションの要約を生成"""
        try:
            params = {"user_id": user_id}
            if session_id:
                params["session_id"] = session_id

            response = await self.client.post(f"{self.base_url}/summary/create", params=params)
            response.raise_for_status()
            logger.info(f"要約を生成しました: user_id={user_id}, session_id={session_id}")
        except Exception as e:
            logger.error(f"要約の生成に失敗しました: {e}")

    async def add_knowledge(self, user_id: str, knowledge: str):
        """ユーザーの知識（固有名詞、記念日など）を追加"""
        try:
            response = await self.client.post(
                f"{self.base_url}/knowledge",
                json={
                    "user_id": user_id,
                    "knowledge": knowledge,
                },
            )
            response.raise_for_status()
            logger.info(f"ナレッジを追加しました: {knowledge}")
        except Exception as e:
            logger.error(f"ナレッジの追加に失敗しました: {e}")

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()
