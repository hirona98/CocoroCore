"""ChatMemoryサービスと統合するLLMツール"""

import asyncio
import logging
from typing import Optional

from memory_client import ChatMemoryClient
from session_manager import SessionManager

logger = logging.getLogger(__name__)


def setup_memory_tools(
    sts,
    config,
    memory_client: ChatMemoryClient,
    session_manager: Optional[SessionManager] = None,
    cocoro_dock_client=None,
):
    """ChatMemoryとの統合をツールで実現

    Args:
        sts: STSPipelineインスタンス
        config: 設定辞書
        memory_client: ChatMemoryClientインスタンス
        session_manager: SessionManagerインスタンス（オプション）
        cocoro_dock_client: CocoroDockClientインスタンス（オプション）

    Returns:
        メモリプロンプトの追加文字列
    """

    # 記憶検索ツールを追加
    memory_search_spec = {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": (
                "過去の会話や記憶から情報を検索します。"
                "ユーザーの好み、過去の話題、個人的な情報などを探す時に使用します。\n"
                "画像関連の記憶を検索したい場合は、検索語に『画像』『写真』『見せた』"
                "などのキーワードを含めてください。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "検索したい内容。例：\n"
                            "- 一般検索: 'ユーザーの好きな食べ物'、'前回話した内容'\n"
                            "- 画像検索: '画像 遊園地'、'写真 ペット'、'見せた 料理'"
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    }

    # ナレッジ追加ツールを追加
    add_knowledge_spec = {
        "type": "function",
        "function": {
            "name": "add_knowledge",
            "description": (
                "ユーザーに関する情報（固有名詞、記念日、好み、家族の名前など）を"
                "長期記憶として保存します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge": {
                        "type": "string",
                        "description": (
                            "保存する知識（例：ユーザーの誕生日は1月1日、"
                            "ペットの名前はポチ、好きな食べ物はラーメンなど）"
                        ),
                    }
                },
                "required": ["knowledge"],
            },
        },
    }




    # 要約生成ツールを追加
    create_summary_spec = {
        "type": "function",
        "function": {
            "name": "create_summary",
            "description": (
                "現在の会話セッションの要約を手動で生成します。"
                "長い会話の整理や重要な内容のまとめに使用します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }

    # ナレッジ取得ツールを追加
    get_knowledge_spec = {
        "type": "function",
        "function": {
            "name": "get_knowledge",
            "description": (
                "保存されているユーザーのナレッジ（知識）一覧を取得します。"
                "ユーザーについて何を覚えているか確認する時に使用します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }

    @sts.llm.tool(memory_search_spec)
    async def search_memory(query: str, metadata: dict = None):
        """過去の記憶を検索"""
        logger.debug(f"ツール呼び出し: search_memory(query='{query}')")

        # 記憶検索開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("記憶検索中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        result = await memory_client.search(user_id, query)

        if result:
            return result
        else:
            return "関連する記憶が見つかりませんでした。"

    @sts.llm.tool(add_knowledge_spec)
    async def add_knowledge(knowledge: str, metadata: dict = None):
        """情報をナレッジとして保存"""
        logger.debug(f"ツール呼び出し: add_knowledge(knowledge='{knowledge}')")

        # 記憶保存開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("記憶保存中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        await memory_client.add_knowledge(user_id, knowledge)

        return f"ナレッジを保存しました: {knowledge}"




    @sts.llm.tool(create_summary_spec)
    async def create_summary(metadata: dict = None):
        """現在のセッションの要約を生成"""
        # 要約生成開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("要約生成中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        session_id = metadata.get("session_id") if metadata else None

        if session_id:
            await memory_client.create_summary(user_id, session_id)
            return "現在のセッションの要約を生成しました。"
        else:
            # session_idがない場合は、SessionManagerから現在のアクティブセッションを取得
            try:
                # SessionManagerがあればアクティブセッションを確認
                if session_manager:
                    all_sessions = await session_manager.get_all_sessions()
                    
                    # user_idに対応するセッションを探す
                    target_session_id = None
                    for session_key in all_sessions.keys():
                        if session_key.startswith(f"{user_id}:"):
                            target_session_id = session_key.split(":", 1)[1]
                            break
                    
                    if target_session_id:
                        await memory_client.create_summary(user_id, target_session_id)
                        return f"セッション {target_session_id} の要約を生成しました。"

            except Exception as e:
                logger.error(f"要約生成エラー: {e}")
                return f"要約生成に失敗しました: {str(e)}"

    @sts.llm.tool(get_knowledge_spec)
    async def get_knowledge(metadata: dict = None):
        """保存されているナレッジを取得"""
        logger.debug("ツール呼び出し: get_knowledge()")

        # ナレッジ取得開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("ナレッジ取得中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        knowledge_list = await memory_client.get_knowledge(user_id)

        if knowledge_list:
            # ナレッジを整理して返す
            formatted_knowledge = []
            for i, item in enumerate(knowledge_list, 1):
                if isinstance(item, dict):
                    knowledge_text = item.get("knowledge", "")
                    formatted_knowledge.append(f"{i}. {knowledge_text}")
                else:
                    formatted_knowledge.append(f"{i}. {item}")
            
            return "保存されているナレッジ:\n" + "\n".join(formatted_knowledge)
        else:
            return "保存されているナレッジはありません。"

    # システムプロンプトに記憶機能の説明を追加
    memory_prompt_addition = (
        "\n\n"
        + "記憶機能の必須ルール：\n"
        + "- 会話開始時: 必ずsearch_memoryで基本情報を検索してからパーソナライズした挨拶\n"
        + "- 記憶確認質問（「覚えている？」「知っている？」「私の名前は？」等）: 必ず"
        + "検索してから回答\n"
        + "- 固有名詞・日付・好み・感想が出現: 即座にadd_knowledgeで保存\n"
        + "- 応答前: 必ずsearch_memoryで関連情報を検索してからパーソナライズした応答\n"
        + "- 画像関連検索: 検索語に『画像』『写真』『見せた』を含めて検索\n"
        + "- 要約記憶: 要約を保存してと言われたらcreate_summaryで現在の会話を要約保存\n"
    )

    return memory_prompt_addition
