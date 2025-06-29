"""音声アクティビティ検出（VAD）管理モジュール"""

import asyncio
import logging
import random
from typing import Callable, Optional

from aiavatar.sts.vad import StandardSpeechDetector

logger = logging.getLogger(__name__)


class SmartVoiceDetector(StandardSpeechDetector):
    """環境に応じて自動的に音量閾値を調節するVAD"""

    def __init__(
        self,
        context_provider: Optional[Callable[[], str]] = None,
        dock_client=None,
        auto_adjustment=True,
        fixed_threshold=-45.0,
        *args,
        **kwargs,
    ):
        """
        Args:
            context_provider: 共有コンテキストIDを提供する関数
            dock_client: ステータス通知用のDockクライアント
            auto_adjustment: 自動閾値調整のON/OFF
            fixed_threshold: 自動調整OFFの時の固定閾値（dB）
        """
        # 初期閾値を-60dBに設定（環境音測定用）
        if "volume_db_threshold" not in kwargs:
            kwargs["volume_db_threshold"] = -60.0
        super().__init__(*args, **kwargs)

        self.context_provider = context_provider
        self.dock_client = dock_client
        self.initial_threshold = kwargs.get("volume_db_threshold", -60.0)
        self.base_threshold = self.initial_threshold
        self.current_threshold = self.initial_threshold
        self.calibration_done = False
        self.too_long_count = 0
        self.success_count = 0
        self.adjustment_history = []
        self.last_adjustment_time = 0
        self.adjustment_interval = 5.0  # 5秒間隔（高速対応）
        self.environment_samples = []
        self.calibration_start_time = None

        # 新しい設定項目
        self.auto_adjustment_enabled = auto_adjustment
        self.fixed_threshold = fixed_threshold
        self.periodic_task = None  # 定期調整タスクの参照

        # 自動調整がOFFの場合は固定閾値を適用
        if not self.auto_adjustment_enabled:
            self.current_threshold = self.fixed_threshold
            self.base_threshold = self.fixed_threshold
            self.calibration_done = True  # キャリブレーションをスキップ
            self._update_threshold_properties()
            logger.info(f"🔧 VAD固定閾値モード: {self.fixed_threshold:.1f}dB")

    def update_settings(self, auto_adjustment: bool, fixed_threshold: float):
        """VAD設定を更新する

        Args:
            auto_adjustment: 自動閾値調整のON/OFF
            fixed_threshold: 自動調整OFFの時の固定閾値（dB）
        """
        logger.info(
            f"🔧 VAD設定更新: auto_adjustment={auto_adjustment}, fixed_threshold={fixed_threshold:.1f}dB"
        )

        self.auto_adjustment_enabled = auto_adjustment
        self.fixed_threshold = fixed_threshold

        if not auto_adjustment:
            # 自動調整OFFの場合は固定閾値を適用
            self.current_threshold = fixed_threshold
            self.base_threshold = fixed_threshold
            self.calibration_done = True
            self._update_threshold_properties()
            logger.info(f"🔧 VAD固定閾値モードに変更: {fixed_threshold:.1f}dB")

            # 定期調整タスクを停止
            self.stop_periodic_adjustment_task()

            # 自動調整機能を停止するためのフラグを設定
            if self.dock_client:
                asyncio.create_task(
                    self.dock_client.send_status_update(
                        f"VAD固定閾値モード: {fixed_threshold:.1f}dB",
                        status_type="microphone_updated",
                    )
                )
        else:
            # 自動調整ONの場合はキャリブレーションを再開
            self.calibration_done = False
            self.calibration_start_time = None
            self.environment_samples = []
            logger.info("🔧 VAD自動調整モードに変更")

            # 定期調整タスクを再開
            asyncio.create_task(self.start_periodic_adjustment_task())

            if self.dock_client:
                asyncio.create_task(
                    self.dock_client.send_status_update(
                        "VAD自動調整モード", status_type="microphone_updated"
                    )
                )

    def get_session_data(self, session_id, key):
        """セッションデータを取得（共有コンテキストIDに対応）"""
        # 既にセッションにcontext_idが設定されている場合はそれを優先
        existing_context = super().get_session_data(session_id, key)
        if key == "context_id":
            if existing_context:
                logger.debug(f"VADの既存context_idを使用: {existing_context}")
                return existing_context
            elif self.context_provider:
                shared_context_id = self.context_provider()
                if shared_context_id:
                    logger.debug(f"VADが共有context_idを返します: {shared_context_id}")
                    return shared_context_id
        return existing_context

    def _update_threshold_properties(self):
        """閾値プロパティを更新するヘルパーメソッド"""
        # StandardSpeechDetectorのグローバル閾値を更新
        self.volume_db_threshold = self.current_threshold

        # 既存の全セッションの閾値も更新（重要！）
        if hasattr(self, "recording_sessions"):
            for session_id in list(self.recording_sessions.keys()):
                try:
                    # 個別セッションの閾値を更新
                    session = self.recording_sessions.get(session_id)
                    if session:
                        session.amplitude_threshold = 32767 * (
                            10 ** (self.current_threshold / 20.0)
                        )
                except Exception as e:
                    logger.debug(f"セッション {session_id} の閾値更新に失敗: {e}")

    def start_environment_calibration(self):
        """環境音キャリブレーションを開始"""
        # 自動調整が無効の場合はキャリブレーションをスキップ
        if not self.auto_adjustment_enabled:
            logger.info(
                f"🔧 VAD自動調整無効のため、キャリブレーションをスキップ（固定閾値: {self.fixed_threshold:.1f}dB）"
            )
            return

        if not self.calibration_done:
            self.calibration_start_time = asyncio.get_event_loop().time()
            self.environment_samples = []
            logger.info("🎤 環境音キャリブレーション開始（5秒間）")

            # ステータス通知を送信
            if self.dock_client:
                asyncio.create_task(
                    self.dock_client.send_status_update(
                        "環境音キャリブレーション開始", status_type="voice_calibration"
                    )
                )

    def process_audio_sample(self, audio_data):
        """音声サンプルを処理（環境音測定とリアルタイム調整）"""
        current_time = asyncio.get_event_loop().time()

        # 仮の音量計算（実際の実装では音声データから計算）
        # この例では時間ベースでランダムな値を生成
        db_level = -45.0 + random.uniform(-10, 10)  # 仮の音量レベル

        # 環境音キャリブレーション中
        if not self.calibration_done and self.calibration_start_time:
            elapsed = current_time - self.calibration_start_time

            if elapsed < 5.0:
                self.environment_samples.append(db_level)
                return
            else:
                # 5秒経過：キャリブレーション完了
                self._complete_calibration()

        # 定期調整（自動調整が有効な場合のみ）
        if (
            self.auto_adjustment_enabled
            and self.calibration_done
            and (current_time - self.last_adjustment_time) >= self.adjustment_interval
        ):
            self._periodic_adjustment(db_level)
            self.last_adjustment_time = current_time

    def _complete_calibration(self):
        """環境音キャリブレーションを完了し、基準閾値を設定"""
        if self.environment_samples:
            # 統計情報を計算
            sorted_levels = sorted(self.environment_samples)

            # 中央値を計算
            percentile_50_index = int(len(sorted_levels) * 0.5)
            percentile_50 = sorted_levels[percentile_50_index]  # 中央値

            # 中央値より5dB上を基準閾値として設定（より現実的な値）
            self.base_threshold = percentile_50 + 5.0
            self.current_threshold = self.base_threshold

            # StandardSpeechDetectorの実際のプロパティを更新
            self._update_threshold_properties()

            # キャリブレーション結果をログ出力
            logger.info(
                f"🎯 環境音キャリブレーション完了: 基準閾値={self.base_threshold:.1f}dB "
                f"(中央値={percentile_50:.1f}dB+5dB)"
            )

            # キャリブレーション完了のステータス通知を送信
            if self.dock_client:
                asyncio.create_task(
                    self.dock_client.send_status_update(
                        f"環境音キャリブレーション完了 (基準閾値: {self.base_threshold:.1f}dB)",
                        status_type="voice_calibration_complete",
                    )
                )

            self.calibration_done = True
            self.last_adjustment_time = asyncio.get_event_loop().time()
        else:
            # サンプルが取得できない場合はデフォルト値を使用
            self.base_threshold = -45.0
            self.current_threshold = self.base_threshold
            self.volume_db_threshold = self.current_threshold
            logger.warning(
                f"⚠️ 環境音キャリブレーション失敗: デフォルト閾値={self.base_threshold:.1f}dB"
            )

            # キャリブレーション失敗のステータス通知を送信
            if self.dock_client:
                asyncio.create_task(
                    self.dock_client.send_status_update(
                        f"環境音キャリブレーション失敗 (デフォルト閾値: {self.base_threshold:.1f}dB)",
                        status_type="voice_calibration_failed",
                    )
                )

            self.calibration_done = True

    def _periodic_adjustment(self, current_db_level):
        """定期的な閾値調整（環境変化に高速対応）"""
        audio_difference = current_db_level - self.current_threshold

        if audio_difference > 3.0:
            # 音量が高い環境：段階的に調整
            if audio_difference > 10.0:
                adjustment = 6.0
            elif audio_difference > 7.0:
                adjustment = 4.0
            else:
                adjustment = 2.0

            old_threshold = self.current_threshold
            self.current_threshold = self.current_threshold + adjustment
            self._update_threshold_properties()
            logger.info(
                f"🔊 閾値調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                f"(+{adjustment:.1f})"
            )

        elif audio_difference < -3.0:
            # 音量が低い環境：感度を上げる（静かになった時の高速対応）
            if audio_difference < -15.0:
                adjustment = -8.0
            elif audio_difference < -10.0:
                adjustment = -5.0
            elif audio_difference < -6.0:
                adjustment = -3.0
            else:
                adjustment = -2.0

            old_threshold = self.current_threshold
            self.current_threshold = self.current_threshold + adjustment
            self._update_threshold_properties()
            logger.info(
                f"🔊 閾値調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB "
                f"({adjustment:.1f})"
            )

    def handle_recording_event(self, event_type: str):
        """録音イベントに基づいて閾値を調整"""
        # 自動調整が無効の場合は調整しない
        if not self.auto_adjustment_enabled:
            return

        if not self.calibration_done:
            return  # キャリブレーション完了まで調整しない

        if event_type == "too_long":
            self.too_long_count += 1
            if self.too_long_count >= 1:  # 1回目から即座に調整
                # 閾値を大幅に上げて感度を下げる（無音を検出しやすくする）
                old_threshold = self.current_threshold
                self.current_threshold = self.current_threshold + 8.0  # さらに大幅に調整

                # StandardSpeechDetectorの実際のプロパティを更新
                self._update_threshold_properties()

                logger.info(
                    f"🔊 緊急調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB (感度ダウン)"
                )
                self.too_long_count = 0
                self.success_count = 0

        elif event_type == "success":
            self.success_count += 1
            if self.success_count >= 8:
                # 安定している場合は少し感度を上げる
                old_threshold = self.current_threshold
                self.current_threshold = self.current_threshold - 1.0
                self._update_threshold_properties()
                logger.info(
                    f"🔊 微調整: {old_threshold:.1f}→{self.current_threshold:.1f}dB (感度アップ)"
                )
                self.success_count = 0

        elif event_type == "too_short":
            # 音声が短すぎる場合は感度を上げる
            old_threshold = self.current_threshold
            self.current_threshold = self.current_threshold - 2.0
            self._update_threshold_properties()
            logger.info(f"🔊 短音声対応: {old_threshold:.1f}→{self.current_threshold:.1f}dB")

    async def calibrate_environment(self, audio_stream, duration=5.0):
        """環境ノイズレベルを測定して基準閾値を設定"""
        logger.info("🎤 環境音のキャリブレーションを開始...")
        noise_levels = []
        start_time = asyncio.get_event_loop().time()

        async for chunk in audio_stream:
            if asyncio.get_event_loop().time() - start_time > duration:
                break
            # 音量レベルを計算（実際の実装はAIAvatarKitの内部処理に依存）
            # ここでは仮の値を使用
            noise_levels.append(-45.0)  # 仮の値

        if noise_levels:
            # 90パーセンタイルをノイズフロアとして使用
            sorted_levels = sorted(noise_levels)
            percentile_90_index = int(len(sorted_levels) * 0.9)
            noise_floor = sorted_levels[percentile_90_index]
            self.base_threshold = noise_floor + 10.0
            self.current_threshold = self.base_threshold
            self.volume_db_threshold = self.current_threshold
            logger.info(f"🎯 キャリブレーション完了: 基準閾値 = {self.base_threshold:.1f} dB")
            self.calibration_done = True

    async def start_periodic_adjustment_task(self):
        """独立した定期調整タスクを開始"""
        if self.periodic_task and not self.periodic_task.done():
            logger.info("🔄 定期調整タスクは既に実行中です")
            return

        logger.info("🔄 定期調整タスクを開始（5秒間隔）")

        async def periodic_adjustment_loop():
            while True:
                try:
                    await asyncio.sleep(self.adjustment_interval)

                    # 自動調整が有効で、キャリブレーションが完了している場合のみ調整
                    if self.auto_adjustment_enabled and self.calibration_done:
                        # 仮の環境音レベルを生成（実環境では音声レベルを測定）
                        current_db_level = -45.0 + random.uniform(-15, 15)

                        self._periodic_adjustment(current_db_level)
                except asyncio.CancelledError:
                    logger.info("🔄 定期調整タスクが停止されました")
                    break
                except Exception as e:
                    logger.error(f"定期調整タスクでエラー: {e}")

        self.periodic_task = asyncio.create_task(periodic_adjustment_loop())

    def stop_periodic_adjustment_task(self):
        """定期調整タスクを停止"""
        if self.periodic_task and not self.periodic_task.done():
            self.periodic_task.cancel()
            logger.info("🔄 定期調整タスクを停止しました")
            self.periodic_task = None


class VADEventHandler(logging.Handler):
    """VADイベントを検出してSmartVoiceDetectorに通知するハンドラー"""

    def __init__(self, vad_instance):
        super().__init__()
        self.vad_instance = vad_instance

    def emit(self, record):
        if record.name == "aiavatar.sts.vad.standard":
            message = record.getMessage()
            if "Recording too long" in message:
                logger.debug("VADイベント検出: Recording too long")
                if hasattr(self.vad_instance, "handle_recording_event"):
                    self.vad_instance.handle_recording_event("too_long")
            elif "sec" in message:
                # 録音時間を検出して10秒制限をチェック
                import re

                duration_match = re.search(r"(\d+\.\d+)\s*sec", message)
                if duration_match:
                    duration = float(duration_match.group(1))
                    if duration >= 8.0:  # 10秒近くになったら調整開始
                        logger.info(f"🚨 録音時間が長い: {duration:.1f}秒")
                        if hasattr(self.vad_instance, "handle_recording_event"):
                            self.vad_instance.handle_recording_event("too_long")
