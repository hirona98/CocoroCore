"""LLM管理モジュール"""

import asyncio
import logging
import os
from typing import Callable, Optional

from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.llm.context_manager.base import SQLiteContextManager
from config_loader import get_config_directory

logger = logging.getLogger(__name__)


class LLMStatusManager:
    """LLM処理状況を管理するクラス"""

    def __init__(self, dock_client):
        self.dock_client = dock_client
        self.active_requests = {}  # request_id: asyncio.Task のマッピング

    async def start_periodic_status(self, request_id: str):
        """定期的なステータス送信を開始"""

        async def send_periodic_status():
            counter = 0
            try:
                while True:
                    await asyncio.sleep(1.0)
                    counter += 1
                    if self.dock_client:
                        await self.dock_client.send_status_update(
                            "LLM応答待ち", status_type="llm_processing"
                        )
                        logger.debug(f"LLM処理ステータス送信: {counter}秒")
            except asyncio.CancelledError:
                logger.debug(f"LLM処理ステータス送信を終了: request_id={request_id}")
                raise

        # タスクを作成して保存
        task = asyncio.create_task(send_periodic_status())
        self.active_requests[request_id] = task
        logger.debug(f"LLM処理ステータス送信を開始: request_id={request_id}")

    def stop_periodic_status(self, request_id: str):
        """定期的なステータス送信を停止"""
        if request_id in self.active_requests:
            task = self.active_requests[request_id]
            task.cancel()
            del self.active_requests[request_id]
            logger.debug(f"LLM処理ステータス送信タスクをキャンセル: request_id={request_id}")


class LLMWithSharedContext:
    """共有コンテキストIDを管理するLLMラッパークラス"""

    def __init__(self, base_llm, context_provider: Optional[Callable[[], str]] = None):
        """
        Args:
            base_llm: ベースとなるLLMサービス
            context_provider: 共有コンテキストIDを提供する関数
        """
        self.base_llm = base_llm
        self.context_provider = context_provider

    def __getattr__(self, name):
        """属性アクセスを基底クラスに委譲"""
        return getattr(self.base_llm, name)

    def __setattr__(self, name, value):
        """base_llm以外の属性は基底クラスに設定"""
        if name in ("base_llm", "context_provider"):
            super().__setattr__(name, value)
        else:
            setattr(self.base_llm, name, value)

    async def get_response(self, messages, context_id=None, **kwargs):
        """レスポンス取得（共有コンテキストID対応）"""
        # 共有context_idがあり、引数にcontext_idがない場合は使用
        if self.context_provider and not context_id:
            shared_context_id = self.context_provider()
            if shared_context_id:
                context_id = shared_context_id
                logger.debug(f"LLMレスポンスで共有context_idを使用: {context_id}")

        # 基底クラスのget_responseを呼び出し
        return await self.base_llm.get_response(messages, context_id=context_id, **kwargs)

    async def get_response_stream(self, messages, context_id=None, **kwargs):
        """ストリームレスポンス取得（共有コンテキストID対応）"""
        # 共有context_idがあり、引数にcontext_idがない場合は使用
        if self.context_provider and not context_id:
            shared_context_id = self.context_provider()
            if shared_context_id:
                context_id = shared_context_id
                logger.debug(f"LLMストリームレスポンスで共有context_idを使用: {context_id}")

        # 基底クラスのget_response_streamを呼び出し
        async for chunk in self.base_llm.get_response_stream(
            messages, context_id=context_id, **kwargs
        ):
            yield chunk


def create_llm_service(
    api_key: str,
    model: str,
    system_prompt: str,
    base_url: Optional[str] = None,
    context_provider: Optional[Callable[[], str]] = None,
    temperature: float = 1.0,
) -> LLMWithSharedContext:
    """LLMサービスを作成する関数

    Args:
        api_key: APIキー
        model: LLMモデル名
        system_prompt: システムプロンプト
        base_url: ローカルLLMのベースURL（Noneの場合はデフォルト使用）
        context_provider: 共有コンテキストIDを提供する関数
        temperature: 温度設定

    Returns:
        設定済みのLLMサービス
    """
    if not api_key:
        raise ValueError("APIキーが設定されていません。設定ファイルを確認してください。")

    # UserDataフォルダにcontext.dbを保存するためのカスタムContextManager
    config_dir = get_config_directory()
    context_db_path = os.path.join(config_dir, "context.db")
    context_manager = SQLiteContextManager(db_path=context_db_path)
    
    # ベースLLMサービス初期化用パラメーター
    llm_params = {
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "context_manager": context_manager,
    }
    
    # base_urlが指定されている場合は追加
    if base_url and base_url.strip():
        llm_params["base_url"] = base_url.strip()
        logger.info(f"ローカルLLM設定: model={model}, base_url={base_url}")
    
    # ベースLLMサービスを初期化
    base_llm = LiteLLMService(**llm_params)

    # ラッパーを適用
    return LLMWithSharedContext(base_llm, context_provider)
