"""
Ollama Chat API 画像サポートパッチ
LiteLLMのollama chat実装に画像処理を追加するパッチ
"""

import json
from typing import Any, Dict, List

from litellm.llms.ollama.common_utils import _convert_image


def patch_ollama_chat_transform():
    """LiteLLMのOllama chat transformationに画像処理を追加"""
    try:
        from litellm.llms.ollama.chat.transformation import OllamaChatConfig

        # 元のtransform_requestメソッドを保存
        original_transform_request = OllamaChatConfig.transform_request

        def patched_transform_request(
            self,
            model: str,
            messages: List[Any],
            optional_params: dict,
            litellm_params: dict,
            headers: dict,
        ) -> dict:
            # 元のメソッドを呼び出し
            data = original_transform_request(
                self, model, messages, optional_params, litellm_params, headers
            )

            # メッセージから画像を抽出して処理
            for i, message in enumerate(data.get("messages", [])):
                if isinstance(message, dict):
                    content = message.get("content")

                    # contentがリスト形式（マルチモーダル）の場合
                    if isinstance(content, list):
                        images = []
                        text_content = ""

                        for item in content:
                            if isinstance(item, dict):
                                if item.get("type") == "image_url":
                                    # 画像URLを抽出
                                    image_url = item.get("image_url", {}).get("url", "")
                                    if image_url:
                                        # data:image形式の場合、Base64部分を抽出
                                        if image_url.startswith("data:"):
                                            base64_data = (
                                                image_url.split(",", 1)[1]
                                                if "," in image_url
                                                else image_url
                                            )
                                            images.append(base64_data)
                                        else:
                                            images.append(image_url)
                                elif item.get("type") == "text":
                                    text_content = item.get("text", "")

                        # imagesフィールドを追加
                        if images:
                            message["images"] = [_convert_image(img) for img in images]
                            # contentをテキストのみに変更
                            message["content"] = text_content

            return data

        # メソッドを置き換え
        OllamaChatConfig.transform_request = patched_transform_request
        print("✅ Ollama chat画像サポートパッチを適用しました")
        return True

    except Exception as e:
        print(f"❌ パッチ適用エラー: {e}")
        return False


def convert_to_ollama_image(image_url: str) -> str:
    """画像URLをollamaが期待する形式に変換"""
    if image_url.startswith("data:"):
        # data:image/png;base64,xxxxx -> xxxxx
        return image_url.split(",", 1)[1] if "," in image_url else image_url
    return image_url
