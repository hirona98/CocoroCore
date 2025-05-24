# ChatMemory 使用者向けガイド

## はじめに

ChatMemoryは、チャットボットやAIアシスタントに長期記憶機能を簡単に追加できるライブラリです。このガイドでは、ChatMemoryを使用してアプリケーションを構築する方法を説明します。

## インストール

### 前提条件

- Python 3.10以上
- PostgreSQL（pgvector拡張がインストール済み）
- OpenAI APIキー

### パッケージのインストール

```bash
pip install chatmemory
```

## クイックスタート

### 1. 最小構成のAPIサーバー

```python
from fastapi import FastAPI
from chatmemory import ChatMemory

# ChatMemoryの初期化
cm = ChatMemory(
    openai_api_key="YOUR_OPENAI_API_KEY",
    llm_model="gpt-4o",
    db_name="postgres",
    db_user="postgres",
    db_password="postgres",
    db_host="127.0.0.1",
    db_port=5432,
)

# FastAPIアプリケーションの作成
app = FastAPI()
app.include_router(cm.get_router())

# uvicorn main:app --reload で起動
```

### 2. 基本的な使用例

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# ユーザーとセッションの識別子
user_id = "user_123"
session_id = "session_456"

# 1. 会話履歴の追加
response = requests.post(f"{BASE_URL}/history", json={
    "user_id": user_id,
    "session_id": session_id,
    "channel": "myapp",  # アプリケーション名
    "messages": [
        {"role": "user", "content": "私はラーメンが好きです"},
        {"role": "assistant", "content": "どんなラーメンがお好きですか？"},
        {"role": "user", "content": "味噌ラーメンが一番好きです"},
        {"role": "assistant", "content": "味噌ラーメンはコクがあって美味しいですね"}
    ]
})

# 2. 別のセッションに切り替え（自動的に前のセッションの要約が生成される）
new_session_id = "session_789"
response = requests.post(f"{BASE_URL}/history", json={
    "user_id": user_id,
    "session_id": new_session_id,
    "messages": [
        {"role": "user", "content": "今日は何を食べようかな"}
    ]
})

# 要約生成を待つ
time.sleep(5)

# 3. 記憶を検索して回答を生成
response = requests.post(f"{BASE_URL}/search", json={
    "user_id": user_id,
    "query": "私の好きな食べ物は何？",
    "include_retrieved_data": True
})

print(response.json()["result"]["answer"])
# 出力例: "あなたの好きな食べ物は味噌ラーメンです。"
```

## 主要な使用パターン

### 1. マルチチャンネル対応

異なるプラットフォーム（Discord、Slack、Web等）からの会話を統合管理できます。

```python
# Discordからの会話
requests.post(f"{BASE_URL}/history", json={
    "user_id": user_id,
    "session_id": "discord_session_1",
    "channel": "discord",
    "messages": [
        {"role": "user", "content": "Discordから投稿しています"}
    ]
})

# Slackからの会話
requests.post(f"{BASE_URL}/history", json={
    "user_id": user_id,
    "session_id": "slack_session_1",
    "channel": "slack",
    "messages": [
        {"role": "user", "content": "Slackから投稿しています"}
    ]
})

# 特定チャンネルの履歴を取得
response = requests.get(f"{BASE_URL}/history", params={
    "user_id": user_id,
    "channel": "discord"
})
```

### 2. 知識の追加と活用

会話とは独立した情報を追加して、回答の精度を向上させます。

```python
# ユーザーの基本情報を知識として追加
requests.post(f"{BASE_URL}/knowledge", json={
    "user_id": user_id,
    "knowledge": "ユーザーは東京在住の30歳のエンジニアです。趣味はプログラミングと読書です。"
})

# 知識を活用した検索
response = requests.post(f"{BASE_URL}/search", json={
    "user_id": user_id,
    "query": "私の職業は何ですか？"
})
```

### 3. セッション管理

```python
# 最近のセッション情報を取得
response = requests.get(f"{BASE_URL}/history/sessions", params={
    "user_id": user_id,
    "within_seconds": 86400,  # 過去24時間
    "limit": 10
})

# 特定期間内の履歴を取得
response = requests.get(f"{BASE_URL}/history", params={
    "user_id": user_id,
    "within_seconds": 3600  # 過去1時間
})
```

### 4. 要約の手動生成

```python
# 特定セッションの要約を生成
response = requests.post(f"{BASE_URL}/summary/create", params={
    "user_id": user_id,
    "session_id": session_id,
    "overwrite": True  # 既存の要約を上書き
})

# 要約を取得
response = requests.get(f"{BASE_URL}/summary", params={
    "user_id": user_id,
    "session_id": session_id
})
```

## チャットボットへの統合例

### Discord Bot (discord.py)

```python
import discord
from discord.ext import commands
import requests
import asyncio

bot = commands.Bot(command_prefix='!')
CHATMEMORY_URL = "http://localhost:8000"

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # ChatMemoryに履歴を保存
    user_id = str(message.author.id)
    session_id = f"{user_id}_{message.channel.id}"
    
    # 非同期でChatMemory APIを呼び出す
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: requests.post(
        f"{CHATMEMORY_URL}/history",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "channel": "discord",
            "messages": [
                {"role": "user", "content": message.content}
            ]
        }
    ))

@bot.command()
async def remember(ctx, *, query):
    """過去の記憶を検索"""
    user_id = str(ctx.author.id)
    
    # 記憶を検索
    response = requests.post(
        f"{CHATMEMORY_URL}/search",
        json={
            "user_id": user_id,
            "query": query
        }
    )
    
    answer = response.json()["result"]["answer"]
    await ctx.send(answer)
```

### Function Calling (OpenAI)

```python
import openai
import requests

def search_memory(user_id: str, query: str) -> str:
    """ChatMemoryから関連する記憶を検索"""
    response = requests.post(
        "http://localhost:8000/search",
        json={
            "user_id": user_id,
            "query": query,
            "top_k": 3
        }
    )
    return response.json()["result"]["answer"]

# OpenAIのFunction Callingで使用
functions = [
    {
        "name": "search_memory",
        "description": "ユーザーの過去の会話や情報を検索",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["user_id", "query"]
        }
    }
]

# チャットの中で必要に応じてsearch_memory関数が呼ばれる
```

## カスタマイズ

### プロンプトのカスタマイズ

```python
cm = ChatMemory(
    openai_api_key="YOUR_API_KEY",
    # 検索時の回答生成プロンプト
    search_system_prompt="ユーザーの質問に対して、提供された情報のみを使用して日本語で回答してください。",
    # 要約生成プロンプト
    summarize_system_prompt="以下の会話を要約し、重要なキーワードを含めてください。"
)
```

### LiteLLMとの統合

OpenAI以外のLLMを使用する場合：

```python
import litellm
from chatmemory import ChatMemory

class CustomChatMemory(ChatMemory):
    async def llm(self, system_prompt: str, user_prompt: str) -> str:
        response = await litellm.acompletion(
            model="claude-3-opus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content
    
    async def embed(self, text: str) -> List[float]:
        response = await litellm.aembedding(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
```

## ベストプラクティス

1. **セッション管理**: ユーザーごと、会話の文脈ごとに適切にセッションIDを設定
2. **チャンネル活用**: マルチプラットフォーム対応の場合は必ずチャンネルを指定
3. **定期的な要約生成**: 長い会話は定期的に要約を生成して検索効率を向上
4. **知識の活用**: ユーザーの基本情報や重要な事実は知識として別途保存
5. **エラーハンドリング**: API呼び出しは必ずtry-exceptで囲む

## トラブルシューティング

### データベース接続エラー
- PostgreSQLが起動しているか確認
- pgvector拡張がインストールされているか確認
- 接続情報（ホスト、ポート、認証情報）が正しいか確認

### 要約が生成されない
- セッションが切り替わったときに自動生成される
- 手動生成する場合は`/summary/create`エンドポイントを使用

### 検索結果が不正確
- 十分な会話履歴があるか確認
- 要約が生成されているか確認
- `search_content=True`オプションで詳細検索を有効化

## 次のステップ

- [API仕様書](./CHATMEMORY_SPEC.md)で詳細な技術仕様を確認
- [GitHubリポジトリ](https://github.com/uezo/chatmemory)で最新情報を確認
- 問題や要望は[Issues](https://github.com/uezo/chatmemory/issues)で報告