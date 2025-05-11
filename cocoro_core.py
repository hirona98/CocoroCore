import argparse
from fastapi import FastAPI

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.chatgpt import ChatGPTService

# from aiavatar.sts.llm.gemini import GeminiService
from config_loader import load_config

# コマンドライン引数を解析
parser = argparse.ArgumentParser(description="CocoroCore AI Assistant Server")
parser.add_argument(
    "folder_path", nargs="?", help="設定ファイルのフォルダパス（省略可）"
)
parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
args = parser.parse_args()

# フォルダパスが位置引数で渡された場合は--config-dirより優先
if args.folder_path:
    args.config_dir = args.folder_path

# 設定ファイルを読み込む
config = load_config(args.config_dir if hasattr(args, "config_dir") else None)

# setting.jsonから値を取得
llm_openai_api_key = config.get("characterList", [])[
    config.get("currentCharacterIndex", 0)
].get("apiKey")
llm_gemini_api_key = config.get("characterList", [])[
    config.get("currentCharacterIndex", 0)
].get("apiKey")
llm_model = config.get("characterList", [])[config.get("currentCharacterIndex", 0)].get(
    "llmModel"
)
# 設定ファイルからポート番号を取得
port = config.get("cocoroCorePort", 55601)

llm = ChatGPTService(
    openai_api_key=llm_openai_api_key,
    model=llm_model,
    temperature=0.0,
    system_prompt="{system_prompt}",
)

# llm = GeminiService(
#     gemini_api_key=LLM_GEMINI_API_KEY,
#     model=LLM_MODEL,
#     temperature=0.0,
#     system_prompt="{system_prompt}",
# )

# AIAvatarインスタンスを作成
aiavatar_app = AIAvatarHttpServer(
    llm=llm,
    system_prompt="{system_prompt}",
    debug=True,
)

# FastAPIアプリを設定し、AIAvatarのルーターを含める
app = FastAPI()
router = aiavatar_app.get_api_router()
app.include_router(router)


# サーバー起動
if __name__ == "__main__":
    import uvicorn

    # 設定情報のログ出力
    print("CocoroCore を起動します")
    print(
        f"設定ディレクトリ: {args.config_dir if hasattr(args, 'config_dir') and args.config_dir else '(デフォルト)'}"
    )
    print(f"使用ポート: {port}")

    try:
        uvicorn.run(app, host="127.0.0.1", port=port)
    except Exception as e:
        print(f"サーバー起動エラー: {e}")
        import traceback

        traceback.print_exc()
        input("Enterキーを押すと終了します...")
