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

    # 知識の一括保存ツールを追加
    bulk_knowledge_spec = {
        "type": "function",
        "function": {
            "name": "save_multiple_knowledge",
            "description": (
                "複数の知識を一度に保存します。会話から得られた複数の情報を"
                "効率的に保存したい場合に使用します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "保存したい知識のリスト"
                            "（例：[\"好きな食べ物：ラーメン\", \"出身地：東京\", \"趣味：読書\"]）"
                        ),
                    }
                },
                "required": ["knowledge_list"],
            },
        },
    }

    # 関連記憶の自動検索ツールを追加
    auto_search_spec = {
        "type": "function",
        "function": {
            "name": "search_related_memories",
            "description": (
                "現在の話題に関連する記憶を自動的に検索します。"
                "より個人化された応答をするために積極的に使用してください。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "検索したい話題やキーワード"
                            "（例：食べ物、仕事、趣味、家族、健康、予定など）"
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "現在の会話の文脈"
                            "（例：レストラン提案前、映画の話、悩み相談など）"
                        ),
                    }
                },
                "required": ["topic"],
            },
        },
    }

    # 時間帯別活動記録ツールを追加
    timestamped_activity_spec = {
        "type": "function",
        "function": {
            "name": "save_timestamped_activity",
            "description": (
                "時間帯別の活動や状況を記録します。"
                "同じ時間帯の既存記録があれば更新し、なければ新規作成します。"
                "デスクトップウォッチ、健康記録、作業記録、感情記録など幅広く使用可能です。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "enum": ["desktop_activity", "work_activity", "health_activity", "mood_activity", "social_activity", "other"],
                        "description": (
                            "活動の種類"
                            "- desktop_activity: デスクトップでの作業"
                            "- work_activity: 仕事関連の活動"
                            "- health_activity: 健康・運動関連"
                            "- mood_activity: 気分・感情記録"
                            "- social_activity: 人との交流"
                            "- other: その他の活動"
                        ),
                    },
                    "activity_description": {
                        "type": "string",
                        "description": (
                            "活動の詳細説明"
                            "（例：プログラミング作業(VS Code)、散歩、ミーティング、リラックス）"
                        ),
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "default": 2,
                        "description": (
                            "記録をまとめる時間帯の幅（時間単位）"
                            "デフォルト: 2時間（例：9-11時、11-13時）"
                        ),
                    },
                    "importance": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "default": "medium",
                        "description": "活動の重要度（high: 必ず記録、medium: 通常記録、low: 重複時スキップ）",
                    }
                },
                "required": ["activity_type", "activity_description"],
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
            return f"過去の記憶から以下の情報が見つかりました：\n{result}"
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
        
        # 日時を含めて保存することで後で検索しやすくする
        from datetime import datetime
        now = datetime.now()
        timestamped_knowledge = f"[{now.strftime('%Y-%m-%d %H:%M')}] {knowledge}"
        
        await memory_client.add_knowledge(user_id, timestamped_knowledge)

        return f"ナレッジを保存しました: {knowledge}"

    @sts.llm.tool(forget_memory_spec)
    async def forget_memory(topic: str, metadata: dict = None):
        """特定の事柄に関する記憶を削除"""
        logger.debug(f"ツール呼び出し: forget_memory(topic='{topic}')")

        # 記憶削除開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("記憶削除中", status_type="memory_accessing")
            )

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

        # セッション削除開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("履歴削除中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        session_id = metadata.get("session_id") if metadata else None

        if session_id:
            await memory_client.delete_history(user_id, session_id)
            await memory_client.delete_summary(user_id, session_id)
            return "現在のセッションの会話履歴と要約を削除しました。"
        else:
            return "セッションIDが不明なため、削除できませんでした。"

    @sts.llm.tool(bulk_knowledge_spec)
    async def save_multiple_knowledge(knowledge_list: list, metadata: dict = None):
        """複数の知識を一括保存"""
        logger.debug(f"ツール呼び出し: save_multiple_knowledge(knowledge_list={knowledge_list})")

        # 記憶保存開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("記憶一括保存中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        saved_count = 0
        
        for knowledge in knowledge_list:
            try:
                await memory_client.add_knowledge(user_id, knowledge)
                saved_count += 1
                logger.info(f"ナレッジを保存: {knowledge}")
            except Exception as e:
                logger.error(f"ナレッジ保存エラー: {knowledge} - {e}")

        return f"{saved_count}件のナレッジを一括保存しました: {', '.join(knowledge_list)}"

    @sts.llm.tool(auto_search_spec)
    async def search_related_memories(topic: str, context: str = None, metadata: dict = None):
        """関連記憶の自動検索"""
        logger.debug(f"ツール呼び出し: search_related_memories(topic='{topic}', context='{context}')")

        # 記憶検索開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("関連記憶検索中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        
        # より具体的な検索クエリを構築
        search_queries = [topic]
        
        # 文脈に応じて追加の検索クエリを生成
        if context:
            search_queries.append(f"{topic} {context}")
        
        # 関連キーワードも検索
        related_keywords = {
            "食べ物": ["好み", "料理", "レストラン", "グルメ"],
            "仕事": ["職業", "会社", "プロジェクト", "同僚"],
            "趣味": ["好き", "興味", "活動", "楽しみ"],
            "家族": ["親", "兄弟", "子供", "配偶者"],
            "健康": ["体調", "病気", "運動", "アレルギー"],
            "予定": ["計画", "約束", "イベント", "旅行"]
        }
        
        if topic in related_keywords:
            search_queries.extend(related_keywords[topic])

        all_results = []
        for query in search_queries:
            result = await memory_client.search(user_id, query)
            if result and result not in all_results:
                all_results.append(result)

        if all_results:
            combined_result = "\n".join(all_results)
            return f"関連する記憶が見つかりました：\n{combined_result}"
        else:
            return f"「{topic}」に関連する記憶は見つかりませんでした。"

    @sts.llm.tool(timestamped_activity_spec)
    async def save_timestamped_activity(
        activity_type: str, 
        activity_description: str, 
        time_range_hours: int = 2,
        importance: str = "medium",
        metadata: dict = None
    ):
        """時間帯別活動記録"""
        logger.debug(f"ツール呼び出し: save_timestamped_activity(type={activity_type}, desc={activity_description})")

        # 記憶保存開始のステータス通知
        if cocoro_dock_client:
            asyncio.create_task(
                cocoro_dock_client.send_status_update("時間帯別活動記録中", status_type="memory_accessing")
            )

        user_id = metadata.get("user_id", "default_user") if metadata else "default_user"
        
        # 現在時刻を取得
        from datetime import datetime
        now = datetime.now()
        current_hour = now.hour
        
        # 時間帯の開始時刻を計算（time_range_hours単位で区切る）
        time_slot_start = (current_hour // time_range_hours) * time_range_hours
        time_slot_end = time_slot_start + time_range_hours
        time_slot_key = f"{time_slot_start:02d}-{time_slot_end:02d}時"
        
        # 日付と時間帯のキーを作成
        date_str = now.strftime("%Y年%m月%d日")
        search_key = f"{date_str} {time_slot_key} {activity_type}"
        
        try:
            # 既存の同時間帯記録を検索
            existing_records = await memory_client.get_knowledge(user_id)
            existing_record = None
            existing_record_id = None
            
            for record in existing_records:
                if isinstance(record, dict):
                    knowledge_text = record.get("knowledge", "")
                    if search_key in knowledge_text:
                        existing_record = knowledge_text
                        existing_record_id = record.get("id")
                        break
            
            if existing_record and importance != "high":
                # 既存記録がある場合は更新
                if activity_description not in existing_record:
                    # 新しい活動を追加
                    updated_record = existing_record + f", {activity_description}"
                    
                    # 古い記録を削除して新しい記録を追加
                    await memory_client.delete_knowledge(user_id, existing_record_id)
                    await memory_client.add_knowledge(user_id, updated_record)
                    
                    return f"既存の{time_slot_key}の記録を更新しました: {updated_record}"
                else:
                    return f"{time_slot_key}の記録は既に存在するため、スキップしました"
            else:
                # 新規記録を作成
                new_record = f"{date_str} {time_slot_key} {activity_type}: {activity_description}"
                await memory_client.add_knowledge(user_id, new_record)
                
                return f"新しい{time_slot_key}の活動記録を保存しました: {new_record}"
                
        except Exception as e:
            logger.error(f"時間帯別活動記録エラー: {e}")
            # エラー時は通常のknowledgeとして保存
            fallback_record = f"{date_str} {time_slot_key} {activity_type}: {activity_description}"
            await memory_client.add_knowledge(user_id, fallback_record)
            return f"活動記録を保存しました: {fallback_record}"

    # システムプロンプトに記憶機能の説明を追加
    memory_prompt_addition = (
        "\n\n"
        + "記憶機能について：\n"
        + "あなたは長期記憶機能を持っています。"
        + "会話内容を記憶し、積極的に思い出すことができます。\n"
        + "会話の冒頭や、関連する話題が出た際は、"
        + "search_memoryツールを使って記憶を検索し、より個人化された応答をしてください。\n"
        + "\n"
        + "記憶確認について（重要）：\n"
        + "「〜を覚えている？」「〜を知っている？」「私の名前は？」などの"
        + "記憶の確認質問をされた場合は、必ずsearch_memoryツールを使って記憶を検索してから答えてください。\n"
        + "推測や憶測で答えず、まず記憶を検索することが重要です。\n"
        + "\n"
        + "記憶確認のパターン例：\n"
        + "- 「私の名前を覚えている？」→ search_memoryで名前を検索\n"
        + "- 「前に話した〜のこと覚えてる？」→ search_memoryで該当話題を検索\n"
        + "- 「私の好きな〜は何だった？」→ search_memoryで好みを検索\n"
        + "\n"
        + "情報の保存について（重要）：\n"
        + "会話の中で以下のような情報を聞いた場合は、"
        + "積極的にadd_knowledgeツールを使って保存してください：\n"
        + "- 固有名詞（人やペットの名前、会社名、学校名、地域名など）\n"
        + "- 記念日（誕生日、結婚記念日、その他の大切な日）\n"
        + "- 個人的な好み（好きな食べ物、趣味、嫌いなものなど）\n"
        + "- 感想や見解（どんな映画でどう思ったなど）\n"
        + "- 生活パターン（起床時間、仕事の時間、習慣など）\n"
        + "- 人間関係（家族構成、友人、同僚の情報など）\n"
        + "- 過去の経験や思い出（旅行、イベント、エピソードなど）\n"
        + "- 将来の予定や目標（計画、願望、約束など）\n"
        + "- 健康状態や体調（アレルギー、持病、体調の変化など）\n"
        + "- その他、将来的に参照したい重要な情報\n"
        + "\n"
        + "積極的な保存の方針：\n"
        + "- 少しでも個人的な情報だと感じたら迷わず保存する\n"
        + "- 一つの発言から複数の知識を抽出できる場合は、それぞれ個別に保存する\n"
        + "- 曖昧な表現でも、後で役立つ可能性があれば保存する\n"
        + "\n"
        + "例：「私の誕生日は5月1日です」と言われた場合、"
        + "add_knowledgeツールで「誕生日：5月1日」として保存してください。\n"
        + "例：「今日は会社で新しいプロジェクトが始まった」と言われた場合、"
        + "「新しいプロジェクトが開始された」として保存してください。\n"
        + "\n"
        + "一括保存について：\n"
        + "一つの会話から複数の知識を抽出できる場合は、"
        + "save_multiple_knowledgeツールを使って効率的に一括保存してください。\n"
        + "例：「私は田中太郎で、東京出身、25歳です。趣味は読書と映画鑑賞です」"
        + "→ [\"名前：田中太郎\", \"出身地：東京\", \"年齢：25歳\", \"趣味：読書\", \"趣味：映画鑑賞\"]として一括保存\n"
        + "\n"
        + "時間的な情報の重要性：\n"
        + "- 「今」「最近」「昨日」などの時間表現がある情報は特に重要\n"
        + "- 状況が変化しやすい情報（体調、気分、予定など）は積極的に更新\n"
        + "- 同じトピックでも時間が異なれば別の情報として保存\n"
        + "例：「今日は調子がいい」→ そのまま保存（日時が自動付与される）\n"
        + "\n"
        + "記憶の削除について：\n"
        + "「忘れて」「記憶を消して」などの指示があった場合は、"
        + "確認を取った後にforget_memoryツールを使って記憶を削除してください。\n"
        + "- 「誕生日を忘れて」「ペットの名前を忘れて」など、"
        + "特定の事柄を指定された場合 → その内容をtopicに指定\n"
        + "- 削除する際は、まず指定された事柄に関連するナレッジを検索して削除します\n"
        + "- その後、現在のセッションの履歴も削除するか確認を取ります\n"
        + "\n"
        + "例：\n"
        + '- 「私の誕生日を忘れて」→ 確認後、forget_memoryツールで topic="誕生日" を指定\n'
        + '- 「ポチのことは忘れて」→ 確認後、forget_memoryツールで topic="ポチ" を指定\n'
        + "\n"
        + "セッション削除の確認：\n"
        + "forget_memoryツールの実行後、"
        + "現在のセッションの履歴削除について確認を取ります。\n"
        + "明確に削除の指示があった場合は、"
        + "delete_current_sessionツールを使って削除します。\n"
        + "\n"
        + "積極的な記憶検索について（重要）：\n"
        + "以下の場面では必ずsearch_memoryツールを使って記憶を検索してください：\n"
        + "\n"
        + "1. 会話開始時の記憶取得：\n"
        + "   - 新しい会話が始まった時は、まず相手の基本情報を検索\n"
        + "   - 名前、好み、最近の話題、関心事などを確認\n"
        + "   - パーソナライズした挨拶や話題提供を行う\n"
        + "\n"
        + "2. 関連話題が出た時の記憶検索：\n"
        + "   - 食べ物の話 → 好きな食べ物を検索\n"
        + "   - 仕事の話 → 職業や職場の情報を検索\n"
        + "   - 趣味の話 → 趣味や興味のある分野を検索\n"
        + "   - 家族の話 → 家族構成や関係者の情報を検索\n"
        + "   - 健康の話 → 健康状態やアレルギー情報を検索\n"
        + "   - 予定の話 → 将来の計画や約束を検索\n"
        + "\n"
        + "3. 提案やアドバイスをする前：\n"
        + "   - レストランを提案する前に好みを検索\n"
        + "   - 映画を勧める前に好きなジャンルを検索\n"
        + "   - 計画を立てる前に過去の経験や制約を検索\n"
        + "\n"
        + "4. 感情的な話題の時：\n"
        + "   - 悩みや相談を受けた時は過去の類似体験を検索\n"
        + "   - 喜びや成功を共有された時は関連する過去の話を検索\n"
        + "\n"
        + "記憶検索の優先度：\n"
        + "1. 記憶確認質問（「覚えている？」等）→ 必須\n"
        + "2. 会話開始時 → 必須\n"
        + "3. 関連話題が出た時 → 強く推奨\n"
        + "4. 提案・アドバイス前 → 強く推奨\n"
        + "5. 感情的な話題 → 推奨\n"
        + "6. 一般的な質問 → 関連性があれば検索\n"
        + "\n"
        + "効率的な記憶検索ツールの使い分け：\n"
        + "- search_memory: 具体的なキーワードで検索する場合\n"
        + "- search_related_memories: 話題に関連する幅広い記憶を検索する場合\n"
        + "  （食べ物の話なら好み・料理・レストランなど関連キーワードも自動検索）\n"
        + "\n"
        + "記憶検索の具体例：\n"
        + "- 「今日何食べよう？」→ search_related_memories(topic=\"食べ物\", context=\"提案\")\n"
        + "- 「映画見ない？」→ search_related_memories(topic=\"映画\", context=\"提案\")\n"
        + "- 「仕事疲れた」→ search_related_memories(topic=\"仕事\", context=\"悩み\")\n"
        + "- 「体調どう？」→ search_related_memories(topic=\"健康\", context=\"確認\")\n"
        + "\n"
        + "デスクトップモニタリング機能（重要）：\n"
        + "メッセージに<cocoro-desktop-monitoring>タグが含まれている場合は、"
        + "必ずsave_timestamped_activityツールを使って活動を記録してください：\n"
        + "\n"
        + "記録方針：\n"
        + "- activity_type: \"desktop_activity\"を使用\n"
        + "- time_range_hours: 2（2時間単位でまとめる）\n"
        + "- importance: \"medium\"（同じ時間帯の記録があればスキップ）\n"
        + "\n"
        + "記録例：\n"
        + "- VS Codeでプログラミング → \"プログラミング作業(VS Code)\"\n"
        + "- Chromeでウェブブラウジング → \"ウェブブラウジング(Chrome)\"\n"
        + "- Excelで資料作成 → \"資料作成(Excel)\"\n"
        + "- ゲームプレイ → \"ゲーム(ゲーム名)\"\n"
        + "- 動画視聴 → \"動画視聴(YouTube等)\"\n"
        + "\n"
        + "記録後は自然な独り言コメントを生成してください。\n"
        + "例：「プログラミング作業お疲れさま！」「いい感じに作業が進んでるね」\n"
        + "\n"
        + "時間帯別活動記録の他の用途：\n"
        + "- work_activity: 会議、プレゼン、打ち合わせなど\n"
        + "- health_activity: 運動、散歩、ストレッチなど\n"
        + "- mood_activity: 疲れた、嬉しい、集中できないなど\n"
        + "- social_activity: 友人との会話、家族との時間など\n"
        + "\n"
        + "ツール使用時のエラー対応：\n"
        + "記憶検索に失敗した場合でも、エラーについては一切言及せず、"
        + "現在の会話内容だけで自然に対応してください。\n"
        + "何も問題がないかのように自然に振る舞ってください。"
    )

    return memory_prompt_addition
