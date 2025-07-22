"""リクエスト処理フック関連のモジュール"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from image_processor import parse_image_response, generate_image_description
from time_utils import generate_current_time_info

logger = logging.getLogger(__name__)


class RequestHookProcessor:
    """リクエスト前処理を担当するクラス"""

    def __init__(
        self,
        config: Dict,
        llm: Any,
        user_id: str,
        llm_status_manager: Any,
        cocoro_dock_client: Optional[Any] = None,
        cocoro_shell_client: Optional[Any] = None,
        wakewords: Optional[list] = None,
    ):
        """初期化

        Args:
            config: 設定辞書
            llm: LLMサービス
            user_id: ユーザーID
            llm_status_manager: LLMステータスマネージャー
            cocoro_dock_client: CocoroDockクライアント
            cocoro_shell_client: CocoroShellクライアント
            wakewords: ウェイクワード一覧
        """
        self.config = config
        self.llm = llm
        self.user_id = user_id
        self.llm_status_manager = llm_status_manager
        self.cocoro_dock_client = cocoro_dock_client
        self.cocoro_shell_client = cocoro_shell_client
        self.wakewords = wakewords or []

    async def process_before_llm(self, request: Any, shared_context_id: Optional[str]) -> None:
        """LLM処理前のリクエスト処理

        Args:
            request: リクエストオブジェクト
            shared_context_id: 共有コンテキストID
        """
        # 時刻情報の更新
        self._update_time_info()

        # ユーザーIDの設定
        self._process_user_id(request)

        # コンテキストIDの処理
        self._process_context_id(request, shared_context_id)

        # リクエスト情報のデバッグログ出力
        self._log_request_details(request)

        # メッセージ処理（音声認識、ウェイクワード検出）
        await self._process_message(request)

        # 通知タグの処理
        self._process_notification_tags(request)

        # デスクトップモニタリングタグの処理
        self._process_desktop_monitoring_tags(request)

        # 画像処理
        await self._process_images(request)

        # LLMステータス通知の開始
        await self._start_llm_status_notifications(request)

    def _update_time_info(self) -> None:
        """現在時刻情報をシステムプロンプトに動的に追加"""
        current_time_info = generate_current_time_info()

        # システムプロンプトに現在時刻を動的に追加
        # 前回の時刻情報があれば削除してから新しい情報を追加
        original_prompt = self.llm.system_prompt
        time_marker = "現在の日時:"

        # 既存の時刻情報を削除
        if time_marker in original_prompt:
            lines = original_prompt.split("\n")
            filtered_lines = [line for line in lines if not line.strip().startswith(time_marker)]
            self.llm.system_prompt = "\n".join(filtered_lines)

        # 新しい時刻情報を追加
        self.llm.system_prompt = self.llm.system_prompt + f"\n\n{current_time_info}\n"

        logger.debug(f"時刻情報を更新: {current_time_info}")

    def _process_user_id(self, request: Any) -> None:
        """ユーザーIDを設定ファイルから読み込んだ値に上書き"""
        if hasattr(request, "user_id") and self.user_id:
            original_user_id = request.user_id
            request.user_id = self.user_id
            logger.info(f"user_idを設定値に変更: {original_user_id} → {self.user_id}")

    def _process_context_id(self, request: Any, shared_context_id: Optional[str]) -> None:
        """音声入力でcontext_idが未設定の場合、共有context_idを設定"""
        if not shared_context_id:
            return

        # テキストチャットか音声入力かを判定
        is_voice_input = hasattr(request, "audio_data") and request.audio_data is not None

        if is_voice_input and not getattr(request, "context_id", None):
            # requestオブジェクトが読み取り専用の場合があるため、
            # 新しい属性として設定を試みる
            try:
                request.context_id = shared_context_id
                logger.info(f"音声入力に共有context_idを設定: {shared_context_id}")
            except AttributeError:
                # 読み取り専用の場合は、別の方法で設定
                logger.warning(f"requestオブジェクトは読み取り専用です。context_id: {shared_context_id}を別の方法で設定します")

    def _log_request_details(self, request: Any) -> None:
        """リクエストの詳細情報をログ出力"""
        logger.debug(f"[on_before_llm] request.text: '{request.text}'")
        logger.debug(f"[on_before_llm] request.session_id: {request.session_id}")
        logger.debug(f"[on_before_llm] request.user_id: {request.user_id}")
        logger.debug(f"[on_before_llm] request.context_id: {getattr(request, 'context_id', 'なし')}")
        logger.debug(f"[on_before_llm] request.metadata: {getattr(request, 'metadata', {})}")
        logger.debug(f"[on_before_llm] has audio_data: {hasattr(request, 'audio_data')} (is None: {getattr(request, 'audio_data', None) is None})")

        # リクエストオブジェクトの全属性をデバッグ出力
        logger.debug(f"[on_before_llm] request type: {type(request)}")
        logger.debug(f"[on_before_llm] request dir: {[attr for attr in dir(request) if not attr.startswith('_')]}")
        if hasattr(request, "__dict__"):
            # audio_dataを除外して表示
            filtered_dict = {k: v for k, v in request.__dict__.items() if k != "audio_data"}
            logger.debug(f"[on_before_llm] request.__dict__: {filtered_dict}")
            if "audio_data" in request.__dict__:
                logger.debug(f"[on_before_llm] audio_data: <{len(request.audio_data) if request.audio_data else 0} bytes>")

    async def _process_message(self, request: Any) -> None:
        """音声認識結果のCocoroDockへの送信とログ出力、ウェイクワード検出"""
        if not request.text:
            return

        # テキストチャットか音声認識かを判定
        # audio_dataの有無で判定（音声認識の場合はaudio_dataがある）
        is_text_chat = False
        if hasattr(request, "audio_data"):
            # audio_dataがNoneまたは存在しない場合はテキストチャット
            if request.audio_data is None:
                is_text_chat = True
        else:
            # audio_data属性自体がない場合もテキストチャット
            is_text_chat = True

        if is_text_chat:
            logger.info(f"💬 テキストチャット受信: '{request.text}' (session_id: {request.session_id}, user_id: {request.user_id})")
        else:
            # 音声認識の場合
            logger.info(f"🎤 音声認識結果: '{request.text}' (session_id: {request.session_id}, user_id: {request.user_id})")
            # 音声認識したテキストをCocoroDockに送信（非同期）
            if self.cocoro_dock_client:
                asyncio.create_task(self.cocoro_dock_client.send_chat_message(role="user", content=request.text))
                logger.debug(f"音声認識テキストをCocoroDockに送信: '{request.text}'")

        # メッセージ受信時に正面を向く処理
        if self.cocoro_shell_client:
            asyncio.create_task(self.cocoro_shell_client.send_control_command(command="lookForward"))
            logger.debug("正面を向くコマンドをCocoroShellに送信")

        # ウェイクワード検出
        if self.wakewords:
            for wakeword in self.wakewords:
                if wakeword.lower() in request.text.lower():
                    # ウェイクワード検出ステータス送信（非同期）
                    if self.cocoro_dock_client:
                        asyncio.create_task(self.cocoro_dock_client.send_status_update("ウェイクワード検出", status_type="voice_detected"))
                    logger.info(f"✨ ウェイクワード検出: '{wakeword}' in '{request.text}'")

    def _process_notification_tags(self, request: Any) -> None:
        """通知タグの処理（metadataに保存のみ）"""
        if not (request.text and "<cocoro-notification>" in request.text):
            return

        notification_pattern = r"<cocoro-notification>\s*({.*?})\s*</cocoro-notification>"
        notification_match = re.search(notification_pattern, request.text, re.DOTALL)

        if notification_match:
            try:
                notification_json = notification_match.group(1)
                notification_data = json.loads(notification_json)
                app_name = notification_data.get("from", "不明なアプリ")
                logger.info(f"通知を検出: from={app_name}")

                # metadataに通知情報を追加
                if not hasattr(request, "metadata") or request.metadata is None:
                    request.metadata = {}
                request.metadata["notification_from"] = app_name
                request.metadata["is_notification"] = True
                request.metadata["notification_message"] = notification_data.get("message", "")
                logger.info(f"通知情報をmetadataに保存: {request.metadata}")
            except Exception as e:
                logger.error(f"通知の解析エラー: {e}")

    def _process_desktop_monitoring_tags(self, request: Any) -> None:
        """デスクトップモニタリング画像タグの処理"""
        if request.text and "<cocoro-desktop-monitoring>" in request.text:
            logger.info("デスクトップモニタリング画像タグを検出（独り言モード）")

    async def _process_images(self, request: Any) -> None:
        """画像がある場合は応答を生成してパース"""
        if not (request.files and len(request.files) > 0):
            return

        try:
            # 画像URLのリストを作成
            image_urls = [file["url"] for file in request.files]

            # 画像の客観的な説明を生成
            image_response = await generate_image_description(image_urls, self.config)

            if image_response:
                # 応答をパースして説明と分類を抽出
                parsed_data = parse_image_response(image_response)

                # メタデータに情報を保存
                if not hasattr(request, "metadata") or request.metadata is None:
                    request.metadata = {}
                request.metadata["image_description"] = parsed_data.get("description", "")
                request.metadata["image_category"] = parsed_data.get("category", "")
                request.metadata["image_mood"] = parsed_data.get("mood", "")
                request.metadata["image_time"] = parsed_data.get("time", "")
                request.metadata["image_count"] = len(image_urls)

                # ユーザーのメッセージに画像情報を追加
                original_text = request.text or ""
                description = parsed_data.get("description", "画像が共有されました")

                # 通知の画像かどうかを判断
                is_notification = request.metadata and request.metadata.get("is_notification", False)
                if is_notification:
                    notification_from = request.metadata.get("notification_from", "不明なアプリ")
                    if len(image_urls) == 1:
                        image_prefix = f"[{notification_from}から画像付き通知: {description}]"
                    else:
                        image_prefix = f"[{notification_from}から{len(image_urls)}枚の画像付き通知: {description}]"
                else:
                    if len(image_urls) == 1:
                        image_prefix = f"[画像: {description}]"
                    else:
                        image_prefix = f"[{len(image_urls)}枚の画像: {description}]"

                if original_text:
                    request.text = f"{image_prefix}\n{original_text}"
                else:
                    request.text = image_prefix

                logger.info(f"画像情報をリクエストに追加: カテゴリ={parsed_data.get('category')}, 雰囲気={parsed_data.get('mood')}, 通知={is_notification}, 画像数={len(image_urls)}")
        except Exception as e:
            logger.error(f"画像処理に失敗しました: {e}")

    async def _start_llm_status_notifications(self, request: Any) -> None:
        """LLM送信開始のステータス通知と定期ステータス送信の開始"""
        if not (self.cocoro_dock_client and request.text):
            return

        # 初回のステータス通知
        asyncio.create_task(self.cocoro_dock_client.send_status_update("LLM API呼び出し", status_type="llm_sending"))

        # 定期ステータス送信を開始
        request_id = f"{request.session_id}_{request.user_id}_{request.context_id or 'no_context'}"
        await self.llm_status_manager.start_periodic_status(request_id)
