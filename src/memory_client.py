"""ChatMemoryサービスとの通信を管理するクライアント"""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


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
        """メッセージをキューに追加"""
        # contentがnullまたは空の場合はスキップ
        if not request.text or not response.text:
            logger.debug(f"空のメッセージをスキップ: user_content={request.text}, assistant_content={response.text}")
            return

        async with self._queue_lock:
            # ユーザーメッセージのmetadata（通知情報を含む）
            user_metadata = {"session_id": request.session_id, "user_id": request.user_id}
            if hasattr(request, "metadata") and request.metadata:
                user_metadata.update(request.metadata)

            # 通知メッセージの処理
            if user_metadata.get("is_notification"):
                # 通知メッセージはsystemロールで保存
                notification_from = user_metadata.get("notification_from", "不明なアプリ")
                notification_message = user_metadata.get("notification_message", "")
                self._message_queue.append(
                    {
                        "role": "system",
                        "content": f"[通知: {notification_from}] {notification_message}",
                        "metadata": user_metadata,
                    }
                )
                logger.info(f"通知メッセージをシステムメッセージとして履歴に追加: from={notification_from}")
                # userロールでの保存はスキップ

            elif user_metadata.get("image_description"):
                # 画像説明がある場合は、システムメッセージとして先に追加
                # メタデータから画像情報を構築
                image_info = user_metadata["image_description"]
                category = user_metadata.get("image_category", "")
                mood = user_metadata.get("image_mood", "")
                time = user_metadata.get("image_time", "")

                # 分類情報があれば追加
                classification = ""
                if category or mood or time:
                    classification = f" (分類: {category}/{mood}/{time})"

                self._message_queue.append(
                    {
                        "role": "system",
                        "content": f"[画像が共有されました: {image_info}]{classification}",
                        "metadata": {
                            "session_id": request.session_id,
                            "user_id": request.user_id,
                            "type": "image_description",
                            "image_category": category,
                            "image_mood": mood,
                            "image_time": time,
                        },
                    }
                )
                logger.info(f"画像説明をシステムメッセージとして履歴に追加: {image_info[:30]}... [{category}/{mood}/{time}]")

                # デスクトップモニタリングの場合、userメッセージは保存しない
                if "<cocoro-desktop-monitoring>" in request.text:
                    logger.info("デスクトップモニタリング画像のため、userメッセージの保存をスキップ")
                    # assistantの応答のみ保存に進む
                else:
                    # 通常の画像共有の場合、画像情報を除去してuserメッセージを保存
                    cleaned_text = self._remove_image_prefix(request.text)
                    if cleaned_text:  # テキストがある場合のみ保存
                        self._message_queue.append(
                            {
                                "role": "user",
                                "content": cleaned_text,
                                "metadata": user_metadata,
                            }
                        )

            else:
                # 通常のメッセージ
                self._message_queue.append(
                    {
                        "role": "user",
                        "content": request.text,
                        "metadata": user_metadata,
                    }
                )

            # アシスタントの応答は通知情報を含まない
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
