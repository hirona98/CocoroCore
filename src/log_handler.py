"""
CocoroDock用カスタムログハンドラー
"""

import logging
import json
import asyncio
from typing import Optional
import httpx
from datetime import datetime


class CocoroDockLogHandler(logging.Handler):
    """
    CocoroDockにログメッセージを送信するカスタムハンドラー
    """

    def __init__(self, dock_url: str = "http://127.0.0.1:55600", component_name: str = "CocoroCore"):
        super().__init__()
        self.dock_url = dock_url.rstrip("/")
        self.component_name = component_name
        self._enabled = False
        self._client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._startup_buffer = []  # 起動時ログ用バッファ（最大500件）
        self._buffer_sent = False  # バッファ送信済みフラグ
        
    def set_enabled(self, enabled: bool):
        """ログ送信の有効/無効を設定"""
        self._enabled = enabled
        if enabled and self._client is None:
            # 非同期クライアントを初期化
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=1.0),
                limits=httpx.Limits(max_keepalive_connections=2, max_connections=5)
            )
        elif not enabled and self._client is not None:
            # クライアントを閉じる
            try:
                asyncio.create_task(self._client.aclose())
            except Exception:
                pass
            self._client = None

    def emit(self, record: logging.LogRecord):
        """ログレコードを処理してCocoroDockに送信"""
        try:
            # httpxのapi/logsリクエストログを除外（無限ループ防止）
            if (record.name == "httpx" and 
                "/api/logs" in record.getMessage()):
                return

            # ログメッセージを作成
            log_message = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "component": self.component_name,
                "message": self.format(record)
            }

            if not self._enabled or self._client is None:
                # ログ送信が無効の場合はバッファに保存（最大500件まで）
                if len(self._startup_buffer) < 500:
                    self._startup_buffer.append(log_message)
                return

            # 初回有効化時にバッファ内容を送信
            if not self._buffer_sent:
                self._send_buffered_logs()
                self._buffer_sent = True

            # 通常のリアルタイム送信
            self._schedule_send(log_message)

        except Exception as e:
            # ログハンドラー内でエラーが発生してもメイン処理をブロックしない
            # エラーログは出力しない（無限ループを防ぐため）
            pass

    def _schedule_send(self, log_message: dict):
        """ログメッセージの非同期送信をスケジュール"""
        try:
            # 現在のイベントループを取得
            try:
                loop = asyncio.get_running_loop()
                # ループが実行中の場合のみタスクを作成
                loop.create_task(self._send_log_async(log_message))
            except RuntimeError:
                # イベントループが実行されていない場合は送信をスキップ
                # run_until_complete や asyncio.run は使わない（ブロッキングを避ける）
                pass
        except Exception as e:
            # エラーログは出力しない（無限ループを防ぐため）
            pass

    async def _send_log_async(self, log_message: dict):
        """ログメッセージを非同期でCocoroDockに送信"""
        if self._client is None:
            return

        try:
            response = await self._client.post(
                f"{self.dock_url}/api/logs",
                json=log_message,
                timeout=2.0
            )
            response.raise_for_status()
        except httpx.ConnectError:
            # CocoroDockが起動していない場合はサイレントに無視
            pass
        except httpx.TimeoutException:
            # タイムアウトの場合もサイレントに無視
            pass
        except Exception as e:
            # その他のエラーもサイレントに処理
            # エラーログは出力しない（無限ループを防ぐため）
            pass

    def _send_buffered_logs(self):
        """バッファ内のログを送信"""
        try:
            # バッファ内のログを順次送信
            for log_message in self._startup_buffer:
                self._schedule_send(log_message)
            # 送信後にバッファをクリア
            self._startup_buffer.clear()
        except Exception as e:
            # エラーログは出力しない（無限ループを防ぐため）
            pass

    def close(self):
        """ハンドラーを閉じる"""
        self.set_enabled(False)
        super().close()