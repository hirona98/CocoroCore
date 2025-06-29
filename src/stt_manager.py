"""STT（音声認識）管理モジュール"""

import asyncio
import logging
from typing import Optional

from aiavatar.sts.stt.amivoice import AmiVoiceSpeechRecognizer

logger = logging.getLogger(__name__)


class STTWithStatus:
    """ステータス通知機能付きSTTラッパークラス"""

    def __init__(self, base_stt, dock_client):
        """
        Args:
            base_stt: ベースとなるSTTサービス
            dock_client: ステータス通知用のDockクライアント
        """
        self.base_stt = base_stt
        self.dock_client = dock_client
        # 基底クラスの属性を引き継ぐ
        for attr in dir(base_stt):
            if not attr.startswith("_") and attr != "transcribe":
                setattr(self, attr, getattr(base_stt, attr))

    async def transcribe(self, data: bytes) -> str:
        """音声認識実行（ステータス通知付き）"""
        # 音声認識開始のステータス送信
        if self.dock_client:
            asyncio.create_task(
                self.dock_client.send_status_update("音声認識(API)", status_type="amivoice_sending")
            )
        # 実際の音声認識を実行
        return await self.base_stt.transcribe(data)

    async def close(self):
        """STTサービスを閉じる"""
        if hasattr(self.base_stt, "close"):
            await self.base_stt.close()


def create_stt_service(
    engine: str, api_key: str, language: str = "ja", dock_client=None, debug: bool = False
) -> Optional[STTWithStatus]:
    """STTサービスを作成する関数

    Args:
        engine: STTエンジン名（"openai" または "amivoice"）
        api_key: APIキー
        language: 言語設定（OpenAI用）
        dock_client: ステータス通知用のDockクライアント
        debug: デバッグモード

    Returns:
        設定済みのSTTサービス（APIキーがない場合はNone）
    """
    if not api_key:
        logger.warning("STT APIキーが設定されていないため、STT機能は利用できません")
        return None

    # 音声認識エンジンの選択
    if engine.lower() == "openai":
        logger.info("STTインスタンスを作成します: OpenAI Whisper")
        from aiavatar.sts.stt.openai import OpenAISpeechRecognizer

        base_stt = OpenAISpeechRecognizer(
            openai_api_key=api_key,
            sample_rate=16000,
            language=language,
            debug=debug,
        )
    else:  # デフォルトはAmiVoice
        logger.info(f"STTインスタンスを作成します: AmiVoice (engine={engine})")

        base_stt = AmiVoiceSpeechRecognizer(
            amivoice_api_key=api_key,
            engine="-a2-ja-general",  # 日本語汎用エンジン
            sample_rate=16000,
            debug=debug,
        )

    # ステータス通知機能付きラッパーを適用
    return STTWithStatus(base_stt, dock_client)
