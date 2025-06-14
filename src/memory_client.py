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
        self.client = httpx.AsyncClient(timeout=timeout)
        self._message_queue: List[Dict] = []
        self._queue_lock = asyncio.Lock()

    async def enqueue_messages(self, request, response):
        """メッセージをキューに追加"""
        async with self._queue_lock:
            self._message_queue.append(
                {
                    "role": "user",
                    "content": request.text,
                    "metadata": {
                        "session_id": request.session_id, 
                        "user_id": request.user_id
                    },
                }
            )
            self._message_queue.append(
                {
                    "role": "assistant",
                    "content": response.text,
                    "metadata": {
                        "session_id": request.session_id, 
                        "user_id": request.user_id
                    },
                }
            )

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
        except Exception as e:
            logger.error(f"履歴の保存に失敗しました: {e}")
            # 失敗したメッセージをキューに戻す
            async with self._queue_lock:
                self._message_queue = messages + self._message_queue

    async def search(self, user_id: str, query: str, top_k: int = 5) -> Optional[str]:
        """過去の記憶を検索して回答を生成"""
        try:
            response = await self.client.post(
                f"{self.base_url}/search",
                json={
                    "user_id": user_id,
                    "query": query,
                    "top_k": top_k,
                    "search_content": True,
                    "include_retrieved_data": False,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["result"]["answer"]
        except Exception as e:
            logger.error(f"記憶の検索に失敗しました: {e}")
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

    async def delete_history(self, user_id: str, session_id: str = None):
        """指定したユーザーの会話履歴を削除"""
        try:
            params = {"user_id": user_id}
            if session_id:
                params["session_id"] = session_id

            response = await self.client.delete(
                f"{self.base_url}/history",
                params=params,
            )
            response.raise_for_status()
            logger.info(f"履歴を削除しました: user_id={user_id}, session_id={session_id}")
        except Exception as e:
            logger.error(f"履歴の削除に失敗しました: {e}")

    async def delete_summary(self, user_id: str, session_id: str = None):
        """指定したユーザーの要約を削除"""
        try:
            params = {"user_id": user_id}
            if session_id:
                params["session_id"] = session_id

            response = await self.client.delete(
                f"{self.base_url}/summary",
                params=params,
            )
            response.raise_for_status()
            logger.info(f"要約を削除しました: user_id={user_id}, session_id={session_id}")
        except Exception as e:
            logger.error(f"要約の削除に失敗しました: {e}")

    async def get_knowledge(self, user_id: str):
        """ユーザーの知識を取得"""
        try:
            response = await self.client.get(
                f"{self.base_url}/knowledge",
                params={"user_id": user_id},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"ナレッジの取得に失敗しました: {e}")
            return []

    async def delete_knowledge(self, user_id: str, knowledge_id: int = None):
        """指定したナレッジを削除"""
        try:
            params = {"user_id": user_id}
            if knowledge_id:
                params["knowledge_id"] = knowledge_id

            response = await self.client.delete(
                f"{self.base_url}/knowledge",
                params=params,
            )
            response.raise_for_status()
            logger.info(f"ナレッジを削除しました: knowledge_id={knowledge_id}")
        except Exception as e:
            logger.error(f"ナレッジの削除に失敗しました: {e}")

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()