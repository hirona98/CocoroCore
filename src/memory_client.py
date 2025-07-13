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
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0)
        )
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
            if hasattr(request, 'metadata') and request.metadata:
                user_metadata.update(request.metadata)
            
            # 画像説明がある場合は、システムメッセージとして先に追加
            if user_metadata.get('image_description'):
                # メタデータから画像情報を構築
                image_info = user_metadata['image_description']
                category = user_metadata.get('image_category', '')
                mood = user_metadata.get('image_mood', '')
                time = user_metadata.get('image_time', '')
                
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
                            "image_time": time
                        },
                    }
                )
                logger.info(f"画像説明をシステムメッセージとして履歴に追加: {image_info[:30]}... [{category}/{mood}/{time}]")
            
            # ユーザーの元の発言を抽出
            user_original_text = request.text
            if user_metadata.get('image_description'):
                # 画像情報が追加されている場合、元の発言部分を抽出
                # パターン: "[画像を共有しました: ...]\n元の発言" または "[画像を共有しました: ...]" のみ
                import re
                pattern = r'^\[画像を共有しました: .+?\](?:\n(.+))?$'
                match = re.match(pattern, request.text, re.DOTALL)
                if match:
                    user_original_text = match.group(1) if match.group(1) else ""
            
            self._message_queue.append(
                {
                    "role": "user",
                    "content": user_original_text,
                    "metadata": user_metadata,
                }
            )
            
            # アシスタントの応答は通知情報を含まない
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