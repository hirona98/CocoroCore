import os
from dotenv import load_dotenv
from fastapi import FastAPI

from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.llm.chatgpt import ChatGPTService
#from aiavatar.sts.llm.gemini import GeminiService


# 環境変数を読み込む
load_dotenv()

LLM_OPENAI_API_KEY = os.getenv("LLM_OPENAI_API_KEY")
LLM_GEMINI_API_KEY = os.getenv("LLM_GEMINI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")

STT_OPENAI_API_KEY = os.getenv("STT_OPENAI_API_KEY")


llm = ChatGPTService(
    openai_api_key=LLM_OPENAI_API_KEY,
    model=LLM_MODEL,
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
    openai_api_key=STT_OPENAI_API_KEY, # API Key for STT
    system_prompt="{system_prompt}",
    debug=True
)

# FastAPIアプリを設定し、AIAvatarのルーターを含める
app = FastAPI()
router = aiavatar_app.get_api_router()
app.include_router(router)

aiavatarkit_port = 55601

# サーバー起動
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=aiavatarkit_port)
