"""レスポンス処理関連のモジュール"""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ResponseProcessor:
    """レスポンス処理を担当するクラス"""

    def __init__(
        self,
        user_id: str,
        llm_status_manager: Any,
        session_manager: Any,
        memory_client: Optional[Any] = None,
        cocoro_dock_client: Optional[Any] = None,
        cocoro_shell_client: Optional[Any] = None,
        current_char: Optional[Dict] = None,
        vad_instance: Optional[Any] = None,
    ):
        """初期化
        
        Args:
            user_id: ユーザーID
            llm_status_manager: LLMステータスマネージャー
            session_manager: セッションマネージャー
            memory_client: メモリクライアント
            cocoro_dock_client: CocoroDockクライアント
            cocoro_shell_client: CocoroShellクライアント
            current_char: 現在のキャラクター設定
            vad_instance: VADインスタンス
        """
        self.user_id = user_id
        self.llm_status_manager = llm_status_manager
        self.session_manager = session_manager
        self.memory_client = memory_client
        self.cocoro_dock_client = cocoro_dock_client
        self.cocoro_shell_client = cocoro_shell_client
        self.current_char = current_char or {}
        self.vad_instance = vad_instance

    async def process_response_complete(
        self, 
        request: Any, 
        response: Any,
        shared_context_id_setter: callable
    ) -> None:
        """AI応答完了時の処理
        
        Args:
            request: リクエストオブジェクト
            response: レスポンスオブジェクト
            shared_context_id_setter: 共有context_idを設定する関数
        """
        # 定期ステータス送信を停止
        self._stop_llm_status(request)
        
        # context_idを保存（音声・テキスト共通で使用）
        self._update_shared_context_id(response, shared_context_id_setter)
        
        # セッションアクティビティを更新（これは待つ必要がある）
        await self.session_manager.update_activity(request.user_id or self.user_id, request.session_id)

        # 外部サービスへの送信を非同期で開始（待たずに即座にリターン）
        asyncio.create_task(self._send_to_external_services(request, response))

    def _stop_llm_status(self, request: Any) -> None:
        """定期ステータス送信を停止"""
        request_id = f"{request.session_id}_{request.user_id}_{request.context_id or 'no_context'}"
        self.llm_status_manager.stop_periodic_status(request_id)

    def _update_shared_context_id(self, response: Any, shared_context_id_setter: callable) -> None:
        """context_idを保存（音声・テキスト共通で使用）"""
        if not response.context_id:
            return
            
        shared_context_id_setter(response.context_id)
        logger.debug(f"共有context_idを更新: {response.context_id}")

        # VADの全セッションに共有context_idを設定
        if self.vad_instance and hasattr(self.vad_instance, "sessions"):
            for session_id in list(self.vad_instance.sessions.keys()):
                self.vad_instance.set_session_data(session_id, "context_id", response.context_id)
                logger.debug(
                    f"VADセッション {session_id} にcontext_idを設定: {response.context_id}"
                )

    async def _send_to_external_services(self, request: Any, response: Any) -> None:
        """外部サービスへの送信を非同期で実行"""
        try:
            # ChatMemory処理（メモリー機能が有効な場合）
            if self.memory_client:
                await self.memory_client.enqueue_messages(request, response)
                # save_historyも非同期で実行
                asyncio.create_task(
                    self.memory_client.save_history(
                        user_id=request.user_id or self.user_id,
                        session_id=request.session_id,
                        channel="cocoro_ai",
                    )
                )

            # 並列実行するタスクのリスト
            tasks = []

            # CocoroDock への送信（AI応答のみ）
            if self.cocoro_dock_client and response.text:
                tasks.append(
                    self.cocoro_dock_client.send_chat_message(
                        role="assistant", content=response.text
                    )
                )

            # CocoroShell への送信
            if self.cocoro_shell_client and response.text:
                # 音声パラメータを取得
                voice_params = {
                    "speaker_id": self.current_char.get("voiceSpeakerId", 1),
                    "speed": self.current_char.get("voiceSpeed", 1.0),
                    "pitch": self.current_char.get("voicePitch", 0.0),
                    "volume": self.current_char.get("voiceVolume", 1.0),
                }

                # キャラクター名を取得（複数キャラクター対応）
                character_name = self.current_char.get("name", None)

                tasks.append(
                    self.cocoro_shell_client.send_chat_for_speech(
                        content=response.text,
                        voice_params=voice_params,
                        character_name=character_name,
                    )
                )

            # すべてのタスクを並列実行（結果は待たない）
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.debug(f"外部サービス送信エラー（正常動作）: {result}")
        except Exception as e:
            logger.error(f"外部サービス送信中の予期しないエラー: {e}")