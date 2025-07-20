"""音声処理関連のモジュール"""

import asyncio
import logging
from datetime import datetime, timezone

from aiavatar.device.audio import AudioDevice, AudioRecorder
from vad_manager import VADEventHandler

logger = logging.getLogger(__name__)


def create_vad_context_updater(session_id: str, vad_instance, shared_context_provider):
    """VADセッションのcontext_idを定期的に更新する関数を作成
    
    Args:
        session_id: VADセッションID
        vad_instance: VADインスタンス
        shared_context_provider: 共有context_idを提供する関数
        
    Returns:
        VADコンテキスト更新関数
    """
    async def update_vad_context():
        """VADセッションのcontext_idを定期的に更新"""
        last_context_id = shared_context_provider()
        
        while True:
            await asyncio.sleep(0.5)  # 0.5秒ごとにチェック
            current_context_id = shared_context_provider()
            if current_context_id and current_context_id != last_context_id:
                # 共有context_idが更新されたらVADセッションも更新
                vad_instance.set_session_data(session_id, "context_id", current_context_id)
                logger.info(
                    f"VADセッション {session_id} のcontext_idを更新: {current_context_id}"
                )
                last_context_id = current_context_id
    
    return update_vad_context


async def process_mic_input(
    vad_instance,
    user_id: str,
    shared_context_provider,
    cocoro_dock_client=None
):
    """マイクからの音声入力を処理する関数
    
    Args:
        vad_instance: VADインスタンス
        user_id: ユーザーID
        shared_context_provider: 共有context_idを提供する関数
        cocoro_dock_client: CocoroDockクライアント（オプション）
    """
    try:
        logger.info("マイク入力を開始します")

        # 音声入力待ち状態の通知
        if cocoro_dock_client:
            await cocoro_dock_client.send_status_update(
                "音声入力待ち", status_type="voice_waiting"
            )

        audio_device = AudioDevice()
        logger.info(f"使用するマイクデバイス: {audio_device.input_device}")

        audio_recorder = AudioRecorder(
            sample_rate=16000,
            device_index=audio_device.input_device,
            channels=1,
            chunk_size=512,
        )
        logger.info("AudioRecorderを初期化しました")

        # デフォルトユーザーIDとセッションIDを設定
        default_user_id = user_id
        # セッションIDの重複を防ぐためにマイクロ秒を追加
        default_session_id = f"voice_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        # VADにユーザーIDとコンテキストIDを設定
        vad_instance.set_session_data(
            default_session_id, "user_id", default_user_id, create_session=True
        )
        
        # 共有context_idがある場合は使用
        shared_context_id = shared_context_provider()
        if shared_context_id:
            vad_instance.set_session_data(default_session_id, "context_id", shared_context_id)
            logger.info(f"VADに共有context_idを設定: {shared_context_id}")

        logger.info(
            f"VADセッション設定完了: session_id={default_session_id}, "
            f"user_id={default_user_id}, context_id={shared_context_id}"
        )

        # context_id更新タスクを開始
        update_vad_context = create_vad_context_updater(
            default_session_id, vad_instance, shared_context_provider
        )
        asyncio.create_task(update_vad_context())

        # VADログ監視用のカスタムハンドラーを設定
        # AIAvatarKitのVADロガーにハンドラーを追加
        vad_logger = logging.getLogger("aiavatar.sts.vad.standard")
        vad_event_handler = VADEventHandler(vad_instance)
        vad_event_handler.setLevel(logging.INFO)
        vad_logger.addHandler(vad_event_handler)

        # 環境音キャリブレーションを開始
        if hasattr(vad_instance, "start_environment_calibration"):
            vad_instance.start_environment_calibration()

        # キャリブレーション専用タスクを作成
        async def calibration_task():
            """5秒間のキャリブレーション専用タスク"""
            if hasattr(vad_instance, "process_audio_sample"):
                for i in range(100):  # 5秒間で100サンプル（0.05秒間隔）
                    await asyncio.sleep(0.05)
                    vad_instance.process_audio_sample(None)  # キャリブレーション用の仮データ
                    if (
                        hasattr(vad_instance, "calibration_done")
                        and vad_instance.calibration_done
                    ):
                        break
                logger.debug("キャリブレーションタスク終了")

        # キャリブレーションタスクを開始
        asyncio.create_task(calibration_task())

        # 定期調整タスクを作成
        async def periodic_adjustment_task():
            """定期的にVADの調整を実行するタスク"""
            await asyncio.sleep(5.1)  # キャリブレーション完了を待つ
            logger.debug("⚙️ 定期調整タスク開始")

            while True:
                try:
                    await asyncio.sleep(10.0)  # 10秒間隔
                    if (
                        hasattr(vad_instance, "process_audio_sample")
                        and hasattr(vad_instance, "calibration_done")
                        and vad_instance.calibration_done
                    ):
                        logger.debug("🔄 定期調整タスクから音声サンプル処理を実行")
                        vad_instance.process_audio_sample(None)  # 定期調整用のダミーデータ
                except Exception as e:
                    logger.error(f"定期調整タスクエラー: {e}")

        # 定期調整タスクを開始
        asyncio.create_task(periodic_adjustment_task())

        # マイクストリームを処理
        logger.info("マイクストリームの処理を開始します")
        stream_count = 0
        recording_start_time = None
        sample_count = 0

        async for audio_chunk in await vad_instance.process_stream(
            audio_recorder.start_stream(), session_id=default_session_id
        ):
            stream_count += 1

            # 音声サンプルの処理（定期調整）- キャリブレーション完了後のみ
            if (
                hasattr(vad_instance, "process_audio_sample")
                and hasattr(vad_instance, "calibration_done")
                and vad_instance.calibration_done
            ):
                sample_count += 1
                if sample_count % 10 == 0:  # 10チャンクごとに音量測定
                    logger.debug(
                        f"🎵 音声サンプル処理実行: {sample_count}回目 (10チャンクごと)"
                    )
                    vad_instance.process_audio_sample(audio_chunk)
            elif (
                hasattr(vad_instance, "calibration_done") and not vad_instance.calibration_done
            ):
                logger.debug("⏳ キャリブレーション中のため音声サンプル処理をスキップ")

            # 録音開始時刻を記録
            if stream_count == 1:
                recording_start_time = asyncio.get_event_loop().time()

            # 録音が成功したかチェック（音声チャンクが返ってきた時点で成功）
            if audio_chunk and recording_start_time:
                duration = asyncio.get_event_loop().time() - recording_start_time
                if duration > 1.0:  # 1秒以上の録音は成功とみなす
                    if hasattr(vad_instance, "handle_recording_event"):
                        vad_instance.handle_recording_event("success")
                elif duration < 0.3:  # 0.3秒未満は短すぎる
                    if hasattr(vad_instance, "handle_recording_event"):
                        vad_instance.handle_recording_event("too_short")
                recording_start_time = None  # リセット

            if stream_count % 100 == 0:  # 100チャンクごとにログ出力
                logger.debug(f"音声チャンクを処理中: {stream_count}チャンク目")

                # キャリブレーション状況をログ出力
                if (
                    hasattr(vad_instance, "calibration_done")
                    and not vad_instance.calibration_done
                ):
                    if hasattr(vad_instance, "environment_samples"):
                        sample_count_cal = len(vad_instance.environment_samples)
                        logger.debug(f"環境音サンプル収集中: {sample_count_cal}個")

    except Exception as e:
        logger.error(f"マイク入力エラー: {e}", exc_info=True)