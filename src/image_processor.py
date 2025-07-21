"""画像処理関連のモジュール"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def parse_image_response(response_text: str) -> dict:
    """画像応答を解析してメタデータを抽出"""
    result = {
        "description": "",
        "category": "",
        "mood": "", 
        "time": ""
    }
    
    if response_text is None:
        return result
    
    lines = response_text.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('説明:'):
            result["description"] = line[3:].strip()
        elif line.startswith('分類:'):
            # メタデータを解析: [カテゴリ] / [雰囲気] / [時間帯]
            metadata_text = line[3:].strip()
            parts = [p.strip() for p in metadata_text.split('/')]
            if len(parts) >= 1:
                result["category"] = parts[0]
            if len(parts) >= 2:
                result["mood"] = parts[1]
            if len(parts) >= 3:
                result["time"] = parts[2]
    
    return result


async def generate_image_description(image_urls: list[str], config: dict) -> Optional[str]:
    """画像の客観的な説明を生成（複数画像対応）
    
    Args:
        image_urls: 画像URLのリスト
        config: 設定情報（APIキー、モデル情報を含む）
        
    Returns:
        画像の説明テキスト、または失敗時はNone
    """
    try:
        import litellm

        if not image_urls:
            return None

        # LLMクライアントの設定を取得
        character_list = config.get("characterList", [])
        current_char_index = config.get("currentCharacterIndex", 0)
        
        if character_list and current_char_index < len(character_list):
            current_char = character_list[current_char_index]
            api_key = current_char.get("apiKey")
            model = current_char.get("llmModel", "openai/gpt-4o-mini")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            model = "openai/gpt-4o-mini"
            
        if not api_key:
            logger.warning("APIキーが設定されていないため、画像説明の生成をスキップします")
            return None
            
        # システムプロンプトを画像数に応じて調整
        if len(image_urls) == 1:
            system_prompt = (
                "画像を客観的に分析し、以下の形式で応答してください：\n\n"
                "説明: [この画像の詳細で客観的な説明]\n"
                "分類: [カテゴリ] / [雰囲気] / [時間帯]\n\n"
                "説明は簡潔かつ的確に、以下を含めてください：\n"
                "- 画像の種類（写真/イラスト/スクリーンショット/図表など）\n"
                "- 内容や被写体\n"
                "- 色彩や特徴\n"
                "- 文字情報があれば記載\n"
                "例：\n"
                "説明: 後楽園遊園地を描いたカラーイラスト。中央に白い観覧車と赤いゴンドラ、右側に青黄ストライプのメリーゴーラウンド。青空の下、来園者が散歩している平和な風景。\n"
                "分類: 風景 / 楽しい / 昼\n\n"
                "分類の選択肢：\n"
                "- カテゴリ: 風景/人物/食事/建物/画面（プログラム）/画面（SNS）/画面（ゲーム）/画面（買い物）/画面（鑑賞）/[その他任意の分類]\n"
                "- 雰囲気: 明るい/楽しい/悲しい/静か/賑やか/[その他任意の分類]\n"
                "- 時間帯: 朝/昼/夕方/夜/不明"
            )
            user_text = "この画像を客観的に説明してください。"
        else:
            system_prompt = (
                f"複数の画像（{len(image_urls)}枚）を客観的に分析し、以下の形式で応答してください：\n\n"
                "説明: [すべての画像の詳細で客観的な説明]\n"
                "分類: [主要カテゴリ] / [全体的な雰囲気] / [時間帯]\n\n"
                "説明は簡潔かつ的確に、以下を含めてください：\n"
                "- 各画像の種類（写真/イラスト/スクリーンショット/図表など）\n"
                "- 内容や被写体\n"
                "- 色彩や特徴\n"
                "- 文字情報があれば記載\n"
                "- 画像間の関連性があれば記載\n"
                "例：\n"
                "説明: 1枚目：後楽園遊園地を描いたカラーイラスト。中央に白い観覧車と赤いゴンドラ。2枚目：同じ遊園地の夜景写真。ライトアップされた観覧車が美しい。関連性：同じ遊園地の昼と夜の風景。\n"
                "分類: 風景 / 楽しい / 昼夜\n\n"
                "分類の選択肢：\n"
                "- カテゴリ: 風景/人物/食事/建物/画面（プログラム）/画面（SNS）/画面（ゲーム）/画面（買い物）/画面（鑑賞）/[その他任意の分類]\n"
                "- 雰囲気: 明るい/楽しい/悲しい/静か/賑やか/[その他任意の分類]\n"
                "- 時間帯: 朝/昼/夕方/夜/不明"
            )
            user_text = f"これら{len(image_urls)}枚の画像を客観的に説明してください。"
        
        # メッセージコンテンツを構築
        user_content = []
        for i, image_url in enumerate(image_urls):
            user_content.append({"type": "image_url", "image_url": {"url": image_url}})
        user_content.append({"type": "text", "text": user_text})
            
        # Vision APIで画像の説明を生成
        response = await litellm.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            api_key=api_key,
            temperature=0.3,
        )
        
        full_response = response.choices[0].message.content
        logger.info(f"画像説明を生成しました（{len(image_urls)}枚）: {full_response[:50]}...")
        return full_response
        
    except Exception as e:
        logger.error(f"画像説明の生成に失敗しました: {e}")
        return None