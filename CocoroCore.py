from fastapi import FastAPI

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.chatgpt import ChatGPTService

# from aiavatar.sts.llm.gemini import GeminiService
from config_loader import load_config

# 設定ファイルを読み込む
config = load_config()

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

    uvicorn.run(app, host="127.0.0.1", port=port)
