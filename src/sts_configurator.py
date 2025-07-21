"""STSパイプライン設定関連のモジュール"""

import logging
from typing import Any, Optional, List

from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.tts import SpeechSynthesizerDummy
from dummy_db import DummyPerformanceRecorder

logger = logging.getLogger(__name__)


class STSConfigurator:
    """STSパイプラインの設定を担当するクラス"""

    def __init__(self):
        """初期化"""
        pass

    def create_pipeline(
        self,
        llm: Any,
        stt_instance: Optional[Any],
        vad_instance: Optional[Any],
        voice_recorder_enabled: bool,
        voice_recorder_instance: Any,
        wakewords: Optional[List[str]],
        debug_mode: bool = False,
    ) -> STSPipeline:
        """STSパイプラインを作成し設定する
        
        Args:
            llm: LLMサービス
            stt_instance: STTインスタンス
            vad_instance: VADインスタンス
            voice_recorder_enabled: 音声記録有効フラグ
            voice_recorder_instance: 音声記録インスタンス
            wakewords: ウェイクワード一覧
            debug_mode: デバッグモード
            
        Returns:
            設定済みのSTSパイプライン
        """
        # 音声合成はCocoroShell側で行うためダミーを使用
        custom_tts = SpeechSynthesizerDummy()

        # STSパイプラインを初期化
        sts = STSPipeline(
            llm=llm,
            tts=custom_tts,
            stt=stt_instance,
            vad=vad_instance,  # VADインスタンスを追加
            voice_recorder_enabled=voice_recorder_enabled,
            voice_recorder=voice_recorder_instance,
            wakewords=wakewords,
            wakeword_timeout=60.0,  # ウェイクワードタイムアウト（秒）
            performance_recorder=DummyPerformanceRecorder(),
            debug=debug_mode,
        )

        # カスタム処理を適用
        self._setup_custom_methods(sts)
        
        return sts

    def _setup_custom_methods(self, sts: STSPipeline) -> None:
        """カスタムメソッドをSTSパイプラインに設定
        
        Args:
            sts: STSパイプライン
        """
        self._setup_process_request_override(sts)
        self._setup_is_awake_override(sts)

    def _setup_process_request_override(self, sts: STSPipeline) -> None:
        """process_requestメソッドをオーバーライドして、音声入力時のcontext_id処理を追加"""
        if not hasattr(sts, "process_request"):
            logger.warning("STSPipelineにprocess_requestメソッドが見つかりません")
            return

        original_process_request = sts.process_request

        async def custom_process_request(request):
            """音声入力時に共有context_idを適用するカスタムメソッド"""
            # 共有context_idの取得（外部から設定される）
            shared_context_id = getattr(sts, '_shared_context_id', None)

            # 音声入力かつ共有context_idがある場合
            if shared_context_id:
                # SimpleNamespaceオブジェクトの場合
                if hasattr(request, "__dict__"):
                    if hasattr(request, "audio_data") and request.audio_data is not None:
                        if not getattr(request, "context_id", None):
                            request.context_id = shared_context_id
                            logger.info(
                                f"音声入力リクエストに共有context_idを設定: {shared_context_id}"
                            )
                # 辞書型の場合
                elif isinstance(request, dict):
                    if request.get("audio_data") is not None:
                        if not request.get("context_id"):
                            request["context_id"] = shared_context_id
                            logger.info(
                                f"音声入力リクエスト(dict)に共有context_idを設定: "
                                f"{shared_context_id}"
                            )

            # 元のメソッドを呼び出し
            return await original_process_request(request)

        # メソッドを置き換え
        sts.process_request = custom_process_request

    def _setup_is_awake_override(self, sts: STSPipeline) -> None:
        """is_awakeメソッドをオーバーライドして、テキストチャットの場合は常にTrueを返す"""
        original_is_awake = sts.is_awake

        def custom_is_awake(request, last_request_at):
            # 共有context_idの取得（外部から設定される）
            shared_context_id = getattr(sts, '_shared_context_id', None)
            
            # 共有context_idがある場合は、既に会話が開始されているのでウェイクワード不要
            if shared_context_id:
                logger.debug(f"既存の会話コンテキストあり（{shared_context_id}）、ウェイクワード不要")
                return True

            # audio_dataの有無でテキストチャットか判定
            # テキストチャットの場合はaudio_dataがNoneまたは存在しない
            is_text_chat = False
            if hasattr(request, "audio_data"):
                if request.audio_data is None:
                    is_text_chat = True
            else:
                # audio_data属性自体がない場合もテキストチャット
                is_text_chat = True

            if is_text_chat:
                logger.debug("テキストチャットのため、ウェイクワード検出済みとして処理")
                return True

            # それ以外（音声入力）は元の処理を実行
            return original_is_awake(request, last_request_at)

        sts.is_awake = custom_is_awake

    def setup_text_request_override(self, sts: STSPipeline) -> None:
        """_process_text_requestメソッドをオーバーライド"""
        if not hasattr(sts, "_process_text_request"):
            return

        original_process_text_request = sts._process_text_request

        async def custom_process_text_request(request):
            """テキストリクエスト処理時に共有context_idを適用"""
            # 共有context_idの取得（外部から設定される）
            shared_context_id = getattr(sts, '_shared_context_id', None)

            # 共有context_idがあり、リクエストにcontext_idがない場合は設定
            if shared_context_id and not getattr(request, "context_id", None):
                if hasattr(request, "__dict__"):
                    request.context_id = shared_context_id
                    logger.info(f"テキストリクエストに共有context_idを設定: {shared_context_id}")
                elif isinstance(request, dict) and not request.get("context_id"):
                    request["context_id"] = shared_context_id
                    logger.info(
                        f"テキストリクエスト(dict)に共有context_idを設定: {shared_context_id}"
                    )

            # 元のメソッドを呼び出し
            return await original_process_text_request(request)

        sts._process_text_request = custom_process_text_request
        logger.info("STSパイプラインの_process_text_requestメソッドをオーバーライドしました")

    def setup_invoke_wrapper(self, sts: STSPipeline) -> None:
        """STSパイプラインのinvokeメソッドをラップ"""
        original_invoke = sts.invoke

        async def wrapped_invoke(request):
            # 共有context_idの取得（外部から設定される）
            shared_context_id = getattr(sts, '_shared_context_id', None)

            # テキストリクエストで共有context_idがある場合
            if shared_context_id and hasattr(request, "text") and request.text:
                # context_idが未設定の場合は共有context_idを設定
                if not getattr(request, "context_id", None):
                    request.context_id = shared_context_id
                    logger.info(f"STSリクエストに共有context_idを設定: {shared_context_id}")

            # 元のinvokeを呼び出し
            async for chunk in original_invoke(request):
                yield chunk

        # メソッドを置き換え
        sts.invoke = wrapped_invoke

    @staticmethod
    def set_shared_context_id(sts: STSPipeline, context_id: Optional[str]) -> None:
        """STSパイプラインに共有context_idを設定
        
        Args:
            sts: STSパイプライン
            context_id: 共有context_id
        """
        sts._shared_context_id = context_id


def create_sts_configurator() -> STSConfigurator:
    """STSConfiguratorインスタンスを作成
    
    Returns:
        STSConfiguratorインスタンス
    """
    return STSConfigurator()