"""ChatMemoryサービスと統合するLLMツール"""
import logging
from typing import Optional

from memory_client import ChatMemoryClient
from session_manager import SessionManager

logger = logging.getLogger(__name__)


def setup_memory_tools(sts, config, memory_client: ChatMemoryClient, session_manager: Optional[SessionManager] = None):
    """ChatMemoryとの統合をツールで実現
    
    Args:
        sts: STSPipelineインスタンス
        config: 設定辞書
        memory_client: ChatMemoryClientインスタンス
        session_manager: SessionManagerインスタンス（オプション）
        
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
                "ユーザーの好み、過去の話題、個人的な情報などを探す時に使用します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "検索したい内容（例：ユーザーの好きな食べ物、前回話した内容など）"
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
                "ユーザーに関する重要な情報（固有名詞、記念日、好み、家族の名前など）を"
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

    # 記憶削除ツールを追加
    forget_memory_spec = {
        "type": "function",
        "function": {
            "name": "forget_memory",
            "description": (
                "ユーザーから忘れてほしいと指示された特定の事柄に関する"
                "記憶（ナレッジ）を削除します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "削除したい事柄の内容（例：誕生日、ペットの名前、特定の出来事など）"
                        ),
                    }
                },
                "required": ["topic"],
            },
        },
    }

    # セッション削除確認ツールを追加
    delete_session_spec = {
        "type": "function",
        "function": {
            "name": "delete_current_session",
            "description": "ユーザーが確認した後、現在のセッションの履歴と要約を削除します。",
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
        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        result = await memory_client.search(user_id, query)
        if result:
            return f"過去の記憶から以下の情報が見つかりました：\n{result}"
        else:
            return "関連する記憶が見つかりませんでした。"

    @sts.llm.tool(add_knowledge_spec)
    async def add_knowledge(knowledge: str, metadata: dict = None):
        """重要な情報をナレッジとして保存"""
        logger.debug(f"ツール呼び出し: add_knowledge(knowledge='{knowledge}')")
        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        await memory_client.add_knowledge(user_id, knowledge)
        return f"ナレッジを保存しました: {knowledge}"

    @sts.llm.tool(forget_memory_spec)
    async def forget_memory(topic: str, metadata: dict = None):
        """特定の事柄に関する記憶を削除"""
        logger.debug(f"ツール呼び出し: forget_memory(topic='{topic}')")
        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        session_id = metadata.get("session_id") if metadata else None

        # ナレッジから該当する項目を検索して削除
        knowledge_list = await memory_client.get_knowledge(user_id)
        deleted_count = 0

        for knowledge_item in knowledge_list:
            # knowledge_itemが辞書型の場合の処理
            if isinstance(knowledge_item, dict):
                knowledge_text = knowledge_item.get("knowledge", "")
                knowledge_id = knowledge_item.get("id")

                # トピックに関連する内容かチェック（大文字小文字を無視）
                if topic.lower() in knowledge_text.lower():
                    await memory_client.delete_knowledge(user_id, knowledge_id)
                    deleted_count += 1
                    logger.info(f"削除したナレッジ: {knowledge_text}")

        result_message = ""
        if deleted_count > 0:
            result_message = f"「{topic}」に関する{deleted_count}件のナレッジを削除しました。\n"
        else:
            result_message = f"「{topic}」に関するナレッジは見つかりませんでした。\n"

        # ヒストリーとサマリーの削除について確認
        if session_id:
            result_message += (
                f"\n現在の会話履歴にも「{topic}」に関する内容が含まれている可能性があります。"
            )
            result_message += (
                "\n直近の会話履歴と要約も削除しますか？"
                "（「はい」と答えると現在のセッションの履歴が削除されます）"
            )

        return result_message

    @sts.llm.tool(delete_session_spec)
    async def delete_current_session(metadata: dict = None):
        """現在のセッションの履歴と要約を削除"""
        logger.debug("ツール呼び出し: delete_current_session()")
        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        session_id = metadata.get("session_id") if metadata else None

        if session_id:
            await memory_client.delete_history(user_id, session_id)
            await memory_client.delete_summary(user_id, session_id)
            return "現在のセッションの会話履歴と要約を削除しました。"
        else:
            return "セッションIDが不明なため、削除できませんでした。"

    # システムプロンプトに記憶機能の説明を追加
    memory_prompt_addition = (
        "\n\n"
        + "記憶機能について：\n"
        + "あなたは長期記憶機能を持っています。"
        + "過去の会話内容を記憶し、必要に応じて思い出すことができます。\n"
        + "ユーザーの好み、過去の話題、個人的な情報などが必要な場合は、"
        + "search_memoryツールを使って記憶を検索してください。\n"
        + "\n"
        + "重要な情報の保存について：\n"
        + "ユーザーから以下のような重要な情報を聞いた場合は、"
        + "add_knowledgeツールを使って保存してください：\n"
        + "- 固有名詞（人やペットの名前、会社名、学校名、地域名など）\n"
        + "- 記念日（誕生日、結婚記念日、その他の大切な日）\n"
        + "- 個人的な好み（好きな食べ物、趣味、嫌いなものなど）\n"
        + "- その他、将来的に参照したい重要な情報\n"
        + "\n"
        + "例：ユーザーが「私の誕生日は5月1日です」と言った場合、"
        + "add_knowledgeツールで「ユーザーの誕生日：5月1日」として保存してください。\n"
        + "\n"
        + "記憶の削除について：\n"
        + "ユーザーから「忘れて」「記憶を消して」などの指示があった場合は、"
        + "forget_memoryツールを使って記憶を削除してください。\n"
        + "- 「誕生日を忘れて」「ペットの名前を忘れて」など、"
        + "特定の事柄を指定された場合 → その内容をtopicに指定\n"
        + "- 削除する際は、まず指定された事柄に関連するナレッジを検索して削除します\n"
        + "- その後、現在のセッションの履歴も削除するか確認を取ります\n"
        + "\n"
        + "例：\n"
        + '- 「私の誕生日を忘れて」→ forget_memoryツールで topic="誕生日" を指定\n'
        + '- 「ポチのことは忘れて」→ forget_memoryツールで topic="ポチ" を指定\n'
        + "\n"
        + "セッション削除の確認：\n"
        + "forget_memoryツールの実行後、"
        + "現在のセッションの履歴削除についてユーザーに確認を取ります。\n"
        + "ユーザーが明確に削除の指示をした場合は、"
        + "delete_current_sessionツールを使って削除します。"
    )

    return memory_prompt_addition