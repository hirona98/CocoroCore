"""ツール設定関連のモジュール"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ToolsConfigurator:
    """ChatMemoryとMCPツールの設定を担当するクラス"""

    def __init__(self):
        """初期化"""
        pass

    def setup_memory_tools(
        self,
        sts: Any,
        config: Dict,
        memory_client: Optional[Any],
        session_manager: Any,
        cocoro_dock_client: Optional[Any],
        llm: Any,
        memory_enabled: bool,
    ) -> str:
        """ChatMemoryツールの設定
        
        Args:
            sts: STSパイプライン
            config: 設定辞書
            memory_client: メモリクライアント
            session_manager: セッションマネージャー
            cocoro_dock_client: CocoroDockクライアント
            llm: LLMサービス
            memory_enabled: メモリ有効フラグ
            
        Returns:
            メモリプロンプト追加文字列
        """
        memory_prompt_addition = ""
        
        if memory_enabled and memory_client:
            logger.info("ChatMemoryツールを設定します")
            
            try:
                from memory_tools import setup_memory_tools
                
                # メモリツールをセットアップ
                memory_prompt_addition = setup_memory_tools(
                    sts, config, memory_client, session_manager, cocoro_dock_client
                )

                # システムプロンプトにメモリ機能の説明を追加（初回のみ）
                if memory_prompt_addition and memory_prompt_addition not in llm.system_prompt:
                    llm.system_prompt = llm.system_prompt + memory_prompt_addition
                    logger.info("メモリ機能の説明をシステムプロンプトに追加しました")
                    
            except Exception as e:
                logger.error(f"ChatMemoryツールの設定に失敗: {e}")
                memory_prompt_addition = ""
        
        return memory_prompt_addition

    def setup_mcp_tools(
        self,
        sts: Any,
        config: Dict,
        cocoro_dock_client: Optional[Any],
        llm: Any,
    ) -> str:
        """MCPツールの設定
        
        Args:
            sts: STSパイプライン
            config: 設定辞書
            cocoro_dock_client: CocoroDockクライアント
            llm: LLMサービス
            
        Returns:
            MCPプロンプト追加文字列
        """
        mcp_prompt_addition = ""
        
        # MCPツールをセットアップ（isEnableMcpがTrueの場合のみ）
        if config.get("isEnableMcp", False):
            logger.info("MCPツールを初期化します")
            
            try:
                from mcp_tools import setup_mcp_tools
                
                mcp_prompt_addition = setup_mcp_tools(sts, config, cocoro_dock_client)
                if mcp_prompt_addition:
                    llm.system_prompt = llm.system_prompt + mcp_prompt_addition
                    logger.info("MCPツールの説明をシステムプロンプトに追加しました")
                    
            except Exception as e:
                logger.error(f"MCPツールの設定に失敗: {e}")
                mcp_prompt_addition = ""
        else:
            logger.info("MCPツールは無効になっています")
        
        return mcp_prompt_addition

    def register_cleanup_tasks(self, shutdown_handler: Any) -> None:
        """クリーンアップタスクの登録
        
        Args:
            shutdown_handler: シャットダウンハンドラー
        """
        try:
            from mcp_tools import shutdown_mcp_system
            
            # MCPシステムのクリーンアップタスクを登録
            shutdown_handler.register_cleanup_task(shutdown_mcp_system, "MCP System")
            logger.info("MCPシステムのクリーンアップタスクを登録しました")
            
        except Exception as e:
            logger.error(f"クリーンアップタスクの登録に失敗: {e}")