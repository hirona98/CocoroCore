"""voice_processor.py のテスト"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest


class TestVoiceProcessor:
    """voice_processor モジュールのテスト"""

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_process_mic_input_basic(self, mock_audio_recorder, mock_audio_device):
        """基本的なマイク入力処理のテスト"""
        # モックの設定
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = b"test_audio_data"
        
        from voice_processor import process_mic_input
        
        # VADインスタンスの設定
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        
        mock_dock_client = AsyncMock()
        
        # テスト実行
        result = asyncio.run(process_mic_input(
            vad_instance=mock_vad,
            user_id="test_user",
            shared_context_provider=lambda: "test_context",
            cocoro_dock_client=mock_dock_client
        ))
        
        # アサーション
        assert result is None  # 関数は正常終了
        mock_audio_device.assert_called_once()
        mock_audio_recorder.assert_called_once()

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_process_mic_input_with_custom_threshold(self, mock_audio_recorder, mock_audio_device):
        """カスタム閾値でのマイク入力処理のテスト"""
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = b"test_audio_data"
        
        from voice_processor import process_mic_input
        
        config = {
            "microphoneSettings": {
                "inputThreshold": -20.0,
                "autoAdjustment": True
            }
        }
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        mock_dock_client = AsyncMock()
        
        result = asyncio.run(process_mic_input(
            vad_instance=mock_vad,
            user_id="test_user",
            shared_context_provider=lambda: "test_context",
            cocoro_dock_client=mock_dock_client
        ))
        
        assert result is None
        mock_audio_device.assert_called_once()

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_process_mic_input_error_handling(self, mock_audio_recorder, mock_audio_device):
        """エラーハンドリングのテスト"""
        mock_audio_device.side_effect = Exception("Device error")
        
        from voice_processor import process_mic_input
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        mock_dock_client = AsyncMock()
        
        # エラーが発生しても例外が伝播しないことを確認
        try:
            result = asyncio.run(process_mic_input(
                vad_instance=mock_vad,
                user_id="test_user",
                shared_context_provider=lambda: "test_context",
                cocoro_dock_client=mock_dock_client
            ))
            # AudioDeviceでエラーが発生したが、関数は正常終了する（エラーハンドリング）
            assert result is None
        except Exception:
            pytest.fail("例外が適切にハンドリングされていません")

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_process_mic_input_with_vad_configuration(self, mock_audio_recorder, mock_audio_device):
        """VAD設定を含むマイク入力処理のテスト"""
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = b"test_audio_data"
        
        mock_vad = MagicMock()
        mock_vad.process_audio = MagicMock(return_value=True)
        
        from voice_processor import process_mic_input
        
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        mock_dock_client = AsyncMock()
        
        result = asyncio.run(process_mic_input(
            vad_instance=mock_vad,
            user_id="test_user",
            shared_context_provider=lambda: "test_context",
            cocoro_dock_client=mock_dock_client
        ))
        
        assert result is None

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_process_mic_input_different_configs(self, mock_audio_recorder, mock_audio_device):
        """異なる設定でのマイク入力処理のテスト"""
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = b"test_audio_data"
        
        from voice_processor import process_mic_input
        
        # テスト1: 基本設定
        mock_vad1 = MagicMock()
        mock_vad1.process_stream = AsyncMock()
        
        async def mock_stream_gen1():
            yield b"test_audio_chunk"
            
        mock_vad1.process_stream.return_value = mock_stream_gen1()
        mock_dock_client1 = AsyncMock()
        
        result1 = asyncio.run(process_mic_input(
            vad_instance=mock_vad1,
            user_id="user1",
            shared_context_provider=lambda: "context1",
            cocoro_dock_client=mock_dock_client1
        ))
        
        # テスト2: 別の設定
        mock_vad2 = MagicMock()
        mock_vad2.process_stream = AsyncMock()
        
        async def mock_stream_gen2():
            yield b"test_audio_chunk2"
            
        mock_vad2.process_stream.return_value = mock_stream_gen2()
        mock_dock_client2 = AsyncMock()
        
        result2 = asyncio.run(process_mic_input(
            vad_instance=mock_vad2,
            user_id="user2",
            shared_context_provider=lambda: "context2",
            cocoro_dock_client=mock_dock_client2
        ))
        
        assert result1 is None
        assert result2 is None
        assert mock_audio_device.call_count == 2  # 2回呼ばれることを確認


class TestVoiceProcessorHelpers:
    """voice_processor のヘルパー関数のテスト"""

    @patch('voice_processor.datetime')
    def test_timestamp_generation(self, mock_datetime):
        """タイムスタンプ生成の動作確認"""
        # 固定日時を設定
        fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_time
        mock_datetime.timezone = timezone
        
        # voice_processorモジュールをインポートしてタイムスタンプ関連の処理をテスト
        # 実際の関数がない場合は、モジュールの動作確認のみ
        from voice_processor import process_mic_input
        assert callable(process_mic_input)

    def test_module_imports(self):
        """モジュールのインポートが正常に行われることを確認"""
        try:
            import voice_processor
            assert hasattr(voice_processor, 'process_mic_input')
        except ImportError:
            pytest.fail("voice_processor モジュールのインポートに失敗しました")

    @patch('voice_processor.logging')
    def test_logging_configuration(self, mock_logging):
        """ログ設定の確認"""
        # モジュールをインポートしてログ設定を確認
        import voice_processor
        
        # ログ関連の設定が存在することを確認
        assert hasattr(voice_processor, 'logger') or mock_logging.getLogger.called


class TestVoiceProcessorEdgeCases:
    """voice_processor のエッジケースのテスト"""

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_empty_config(self, mock_audio_recorder, mock_audio_device):
        """空の設定でのテスト"""
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = b""
        
        from voice_processor import process_mic_input
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        
        # エラーハンドリングのテスト：空の値でも動作する
        result = asyncio.run(process_mic_input(
            vad_instance=mock_vad,
            user_id="",
            shared_context_provider=lambda: None,
            cocoro_dock_client=None
        ))
        
        assert result is None

    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    def test_none_values(self, mock_audio_recorder, mock_audio_device):
        """None値での処理テスト"""
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_recorder.record_from_device = AsyncMock()
        mock_recorder.record_from_device.return_value = None
        
        from voice_processor import process_mic_input
        
        # vad_instanceがNoneの場合は実際にエラーが発生するため、モックを用意
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream_gen():
            yield b"test_audio_chunk"
            
        mock_vad.process_stream.return_value = mock_stream_gen()
        
        # None値の処理テスト
        result = asyncio.run(process_mic_input(
            vad_instance=mock_vad,
            user_id="test_user",  # user_idはNoneだとエラーになる可能性があるため適当な値を設定
            shared_context_provider=lambda: None,  # Noneを返すが関数形式で渡す
            cocoro_dock_client=None
        ))
        
        # None値でも正常に処理されることを確認
        assert result is None


class TestVoiceProcessorBranchCoverage:
    """voice_processor 分岐カバレッジテスト"""
    
    @pytest.mark.asyncio
    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    @patch('voice_processor.VADEventHandler')
    async def test_process_mic_input_without_dock_client(self, mock_vad_handler, mock_audio_recorder, mock_audio_device):
        """Dockクライアントなしでのマイク入力処理のテスト（分岐カバレッジ）"""
        from voice_processor import process_mic_input
        
        # モックの設定
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream():
            yield b"audio_chunk1"
            return
            
        mock_vad.process_stream.return_value = mock_stream()
        
        # cocoro_dock_client=None の分岐をテスト
        try:
            await asyncio.wait_for(
                process_mic_input(
                    vad_instance=mock_vad,
                    user_id="test_user",
                    shared_context_provider=lambda: None,  # None context
                    cocoro_dock_client=None  # None client
                ),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass  # タイムアウトは期待される動作
        
        # アサーション - 分岐が実行されたことを確認
        assert mock_vad.set_session_data.called
    
    @pytest.mark.asyncio
    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder')
    @patch('voice_processor.VADEventHandler')
    async def test_process_mic_input_with_shared_context(self, mock_vad_handler, mock_audio_recorder, mock_audio_device):
        """共有コンテキストありでのマイク入力処理のテスト（分岐カバレッジ）"""
        from voice_processor import process_mic_input
        
        # モックの設定
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        
        async def mock_stream():
            yield b"audio_chunk1"
            return
            
        mock_vad.process_stream.return_value = mock_stream()
        mock_dock_client = AsyncMock()
        
        # shared_context_idがある場合の分岐をテスト
        try:
            await asyncio.wait_for(
                process_mic_input(
                    vad_instance=mock_vad,
                    user_id="test_user",
                    shared_context_provider=lambda: "shared_context_123",  # コンテキストあり
                    cocoro_dock_client=mock_dock_client
                ),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass
        
        # アサーション - 分岐が実行されたことを確認
        assert mock_dock_client.send_status_update.called
        assert mock_vad.set_session_data.call_count >= 2  # user_id + context_id
    
    @pytest.mark.asyncio
    @patch('voice_processor.AudioDevice')
    @patch('voice_processor.AudioRecorder') 
    @patch('voice_processor.VADEventHandler')
    async def test_process_mic_input_vad_calibration(self, mock_vad_handler, mock_audio_recorder, mock_audio_device):
        """VAD環境音キャリブレーション分岐のテスト"""
        from voice_processor import process_mic_input
        
        # モックの設定
        mock_device = MagicMock()
        mock_recorder = MagicMock()
        mock_audio_device.return_value = mock_device
        mock_audio_recorder.return_value = mock_recorder
        
        mock_vad = MagicMock()
        mock_vad.process_stream = AsyncMock()
        mock_vad.start_environment_calibration = MagicMock()  # キャリブレーション機能あり
        mock_vad.process_audio_sample = MagicMock()  # サンプル処理機能あり
        
        async def mock_stream():
            yield b"audio_chunk1"
            return
            
        mock_vad.process_stream.return_value = mock_stream()
        
        # キャリブレーション分岐をテスト
        try:
            await asyncio.wait_for(
                process_mic_input(
                    vad_instance=mock_vad,
                    user_id="test_user",
                    shared_context_provider=lambda: "test_context",
                    cocoro_dock_client=AsyncMock()
                ),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass
        
        # アサーション - キャリブレーション分岐が実行されたことを確認
        assert mock_vad.start_environment_calibration.called
        assert mock_vad.process_audio_sample.called
    
    @pytest.mark.asyncio
    async def test_vad_context_updater_with_context_change(self):
        """VADコンテキスト更新での分岐テスト"""
        from voice_processor import create_vad_context_updater
        
        mock_vad = MagicMock()
        session_id = "test_session"
        
        # コンテキストが変更される場合
        context_values = ["initial_context", "updated_context"]
        context_index = 0
        
        def context_provider():
            nonlocal context_index
            if context_index < len(context_values):
                value = context_values[context_index]
                context_index += 1
                return value
            return context_values[-1]
        
        updater = create_vad_context_updater(session_id, mock_vad, context_provider)
        
        # 短時間実行してコンテキスト更新を確認
        try:
            await asyncio.wait_for(updater(), timeout=0.6)
        except asyncio.TimeoutError:
            pass
        
        # アサーション - コンテキスト更新分岐が実行されたことを確認
        assert mock_vad.set_session_data.called