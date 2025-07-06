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
                "などのキーワードを含めてください。\n"
                "ユーザーについて保存した情報の全体を知りたい場合は、"
                "『私について覚えていること』『保存した情報』で検索してください。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "検索したい内容。例：\n"
                            "- 一般検索: 'ユーザーの好きな食べ物'、'前回話した内容'\n"
                            "- 画像検索: '画像 遊園地'、'写真 ペット'、'見せた 料理'\n"
                            "- 情報一覧: '私について覚えていること'、'保存した情報'"
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
                "重要な情報を長期記憶として積極的に保存します。迷ったら保存してください。\n"
                "【個人情報】名前、年齢、職業、趣味、好み、習慣、性格、価値観\n"
                "【プライベート】家族、恋人、友人、ペット、健康状態、悩み、目標、夢\n"
                "【関係性】人間関係、職場の人、チームメンバー、知人、過去の人間関係\n"
                "【日常・予定】スケジュール、ルーティン、約束、予定、記念日\n"
                "【仕事・学習】プロジェクト、スキル、経験、学んだこと、問題解決法\n"
                "【環境・設定】使用ツール、設定値、ファイル場所、システム構成\n"
                "【会話の文脈】重要な決定、継続中の話題、未完了のタスク、約束事"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge": {
                        "type": "string",
                        "description": (
                            "保存する知識。具体例：\n"
                            "- 個人: 'hirona は猫が好きで、2匹飼っている'\n"
                            "- 関係: '田中さんは同僚で、毎週火曜にミーティング'\n"
                            "- 予定: '来月沖縄旅行に行く予定'\n"
                            "- 技術: 'React より Vue.js を好む'\n"
                            "- 設定: 'CocoroAI設定ファイルは UserData/setting.json'\n"
                            "- 悩み: '最近仕事が忙しくて疲れ気味'"
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


    # システムプロンプトに記憶機能の説明を追加
    memory_prompt_addition = (
        "\n\n"
        + "記憶機能の必須ルール：\n"
        + "- 会話開始時: 必ずsearch_memoryで基本情報を検索してからパーソナライズした挨拶\n"
        + "- 記憶確認質問（「覚えている？」「知っている？」「私の名前は？」等）: 必ず"
        + "検索してから回答\n"
        + "- 新情報の積極保存: 毎回の会話で新しい情報があればadd_knowledgeで保存\n"
        + "  * 必須保存: 名前、日付、場所、数値、好み、関係性、予定、設定\n"
        + "  * 感情・状況: '好き'/'嫌い'、'疲れ'、'忙しい'、'悩み'、'目標'\n"
        + "  * 人間関係: 家族、友人、同僚、チーム、知人の情報\n"
        + "  * 技術情報: 使用ツール、設定値、エラー解決法、学習内容\n"
        + "  * 迷ったら保存: 後で検索できる方が有益\n"
        + "- 応答前: 必ずsearch_memoryで関連情報を検索してからパーソナライズした応答\n"
        + "- 画像関連検索: 検索語に『画像』『写真』『見せた』を含めて検索\n"
        + "- 要約記憶: 要約を保存してと言われたらcreate_summaryで現在の会話を要約保存\n"
    )

    return memory_prompt_addition
