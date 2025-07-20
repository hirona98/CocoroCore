"""API クライアント初期化処理モジュール"""

import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


def initialize_memory_client(current_char: Dict, config: Dict) -> Tuple[Optional[Any], bool, str]:
    """ChatMemoryクライアントの初期化
    
    Args:
        current_char: 現在のキャラクター設定
        config: 設定辞書
        
    Returns:
        (memory_client, memory_enabled, memory_prompt_addition)
    """
    memory_enabled = current_char.get("isEnableMemory", False)
    memory_port = config.get("cocoroMemoryPort", 55602)
    memory_url = f"http://127.0.0.1:{memory_port}"
    memory_client = None
    memory_prompt_addition = ""
    
    if memory_enabled:
        try:
            from memory_client import ChatMemoryClient
            memory_client = ChatMemoryClient(base_url=memory_url)
            memory_prompt_addition = (
                "\n\n## メモリ機能について\n"
                "長期記憶が有効になっています。以下のツールを使用して記憶を管理してください：\n"
                "- search_memory: 過去の会話や記憶を検索\n"
                "- add_knowledge: 重要な情報を長期記憶に保存\n"
                "- forget_memory: 不要な記憶を削除\n"
                "- delete_current_session: 現在のセッションを削除"
            )
            logger.info(f"ChatMemoryクライアントを初期化しました: {memory_url}")
        except Exception as e:
            logger.error(f"ChatMemoryクライアントの初期化に失敗しました: {e}")
            memory_enabled = False
    
    return memory_client, memory_enabled, memory_prompt_addition


def initialize_api_clients(config: Dict) -> Tuple[Optional[Any], Optional[Any]]:
    """REST APIクライアントの初期化
    
    Args:
        config: 設定辞書
        
    Returns:
        (cocoro_dock_client, cocoro_shell_client)
    """
    cocoro_dock_port = config.get("cocoroDockPort", 55600)
    cocoro_shell_port = config.get("cocoroShellPort", 55605)
    enable_cocoro_dock = config.get("enableCocoroDock", True)
    enable_cocoro_shell = config.get("enableCocoroShell", True)

    cocoro_dock_client = None
    cocoro_shell_client = None

    # CocoroDockクライアントの早期初期化（ステータス通知用）
    if enable_cocoro_dock:
        try:
            from api_clients import CocoroDockClient
            cocoro_dock_client = CocoroDockClient(f"http://127.0.0.1:{cocoro_dock_port}")
            logger.info(f"CocoroDockクライアントを初期化しました: ポート {cocoro_dock_port}")
        except Exception as e:
            logger.error(f"CocoroDockクライアントの初期化に失敗: {e}")

    # CocoroShellクライアントの初期化
    if enable_cocoro_shell:
        try:
            from api_clients import CocoroShellClient
            cocoro_shell_client = CocoroShellClient(f"http://127.0.0.1:{cocoro_shell_port}")
            logger.info(f"CocoroShellクライアントを初期化しました: ポート {cocoro_shell_port}")
        except Exception as e:
            logger.error(f"CocoroShellクライアントの初期化に失敗: {e}")

    return cocoro_dock_client, cocoro_shell_client


def initialize_llm_manager(cocoro_dock_client: Optional[Any]) -> Any:
    """LLMステータスマネージャーの初期化
    
    Args:
        cocoro_dock_client: CocoroDockクライアント
        
    Returns:
        LLMステータスマネージャー
    """
    from llm_manager import LLMStatusManager
    return LLMStatusManager(cocoro_dock_client)


def initialize_session_manager() -> Any:
    """セッションマネージャーの初期化
    
    Returns:
        セッションマネージャー
    """
    from session_manager import SessionManager
    return SessionManager(timeout_seconds=300, max_sessions=1000)