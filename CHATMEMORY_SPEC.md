# ChatMemory ライブラリ仕様書

## 概要

ChatMemoryは、AIとユーザー間の長期記憶を管理するシンプルかつ強力なPythonライブラリです。会話履歴の保存、要約の自動生成、ベクトル検索による情報取得、LLMを活用した回答生成など、会話型AIアプリケーションに必要な記憶管理機能を提供します。

## 主な特徴

- **🌟 シンプルな実装**: 全コードが1ファイルに収められており、PostgreSQLをデータストアとして使用
- **🔎 インテリジェントな検索と回答**: ベクトル検索で要約/知識から素早くコンテキストを取得し、必要に応じて詳細履歴を使用
- **💬 直接回答生成**: LLMを活用して、単なるデータ取得を超えた明確で簡潔な回答を生成
- **🔄 オムニチャネル対応**: チャンネルフィールドで異なるプラットフォーム（Slack、Discord等）の会話履歴を統合管理

## アーキテクチャ

### データモデル

1. **History（履歴）**: 生の会話ログ。すべてのメッセージを時系列で保存
2. **Summary（要約）**: LLMで生成された会話の要約。高速な処理のためにベクトル化
3. **Knowledge（知識）**: 会話とは独立して提供される追加情報。回答の精度向上に活用

### 検索メカニズム

1. **軽量検索**: まずSummaryとKnowledgeに対してベクトル検索を実行
2. **詳細検索**: 初期検索で不十分な場合、Historyに対してベクトル検索を実行

## 技術仕様

### 依存関係

- Python 3.10以上
- PostgreSQL（v16で動作確認済み）
- pgvector拡張
- 必要なPythonパッケージ:
  - fastapi==0.115.8
  - openai==1.64.0
  - uvicorn==0.34.0
  - psycopg2-binary==2.9.10

### データベーススキーマ

#### conversation_history テーブル
```sql
CREATE TABLE conversation_history (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    channel TEXT
);
```

#### conversation_summaries テーブル
```sql
CREATE TABLE conversation_summaries (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    embedding_summary VECTOR(1536),
    content_embedding VECTOR(1536)
);
```

#### user_knowledge テーブル
```sql
CREATE TABLE user_knowledge (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    user_id TEXT NOT NULL,
    knowledge TEXT NOT NULL,
    embedding VECTOR(1536)
);
```

## API仕様

### ChatMemoryクラス

#### 初期化パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|---------|---|---------|-----|
| openai_api_key | str | None | OpenAI APIキー |
| openai_base_url | str | None | OpenAI APIベースURL（カスタムエンドポイント用） |
| llm_model | str | "gpt-4o" | 使用するLLMモデル |
| embedding_model | str | "text-embedding-3-small" | 使用する埋め込みモデル |
| db_name | str | "chatmemory" | PostgreSQLデータベース名 |
| db_user | str | "postgres" | PostgreSQLユーザー名 |
| db_password | str | "postgres" | PostgreSQLパスワード |
| db_host | str | "127.0.0.1" | PostgreSQLホスト |
| db_port | int | 5432 | PostgreSQLポート |
| search_system_prompt | str | デフォルトプロンプト | 検索時のシステムプロンプト |
| search_user_prompt | str | "" | 検索時のユーザープロンプト |
| search_user_prompt_content | str | デフォルトプロンプト | コンテンツ検索時のユーザープロンプト |
| summarize_system_prompt | str | デフォルトプロンプト | 要約生成時のシステムプロンプト |

### REST APIエンドポイント

#### History（履歴）関連

##### POST /history
会話履歴を追加します。セッションが切り替わった場合、前のセッションの要約を自動生成します。

リクエストボディ:
```json
{
    "user_id": "string",
    "session_id": "string",
    "channel": "string (optional)",
    "messages": [
        {
            "role": "user | assistant",
            "content": "string",
            "created_at": "datetime (optional)",
            "metadata": {}
        }
    ]
}
```

##### GET /history
会話履歴を取得します（最大1000件）。

クエリパラメータ:
- `user_id` (optional): ユーザーID
- `session_id` (optional): セッションID
- `channel` (optional): チャンネル名
- `within_seconds` (default: 3600): 過去N秒以内のメッセージを取得（0で無制限）

##### DELETE /history
会話履歴を削除します。

クエリパラメータ:
- `user_id` (optional): ユーザーID
- `session_id` (optional): セッションID
- `channel` (optional): チャンネル名

##### GET /history/session_ids
ユーザーの全セッションIDを取得します。

クエリパラメータ:
- `user_id` (required): ユーザーID

##### GET /history/sessions
ユーザーの最近のセッション情報を取得します。

クエリパラメータ:
- `user_id` (required): ユーザーID
- `within_seconds` (default: 3600): 過去N秒以内のセッション
- `limit` (default: 5): 取得するセッション数の上限

#### Summary（要約）関連

##### POST /summary/create
セッションの要約を生成します。

クエリパラメータ:
- `user_id` (required): ユーザーID
- `session_id` (optional): セッションID（指定しない場合は複数セッションを処理）
- `overwrite` (default: false): 既存の要約を上書きするか
- `max_count` (default: 10): 処理するセッションの最大数

##### GET /summary
要約を取得します（最大1000件）。

クエリパラメータ:
- `user_id` (optional): ユーザーID
- `session_id` (optional): セッションID

##### DELETE /summary
要約を削除します。

クエリパラメータ:
- `user_id` (optional): ユーザーID
- `session_id` (optional): セッションID

#### Knowledge（知識）関連

##### POST /knowledge
ユーザーの知識を追加します。

リクエストボディ:
```json
{
    "user_id": "string",
    "knowledge": "string"
}
```

##### GET /knowledge
ユーザーの知識を取得します。

クエリパラメータ:
- `user_id` (required): ユーザーID

##### DELETE /knowledge
ユーザーの知識を削除します。

クエリパラメータ:
- `user_id` (required): ユーザーID
- `knowledge_id` (optional): 知識ID（指定しない場合は全削除）

#### Search（検索）関連

##### POST /search
要約と知識を検索し、LLMで回答を生成します。

リクエストボディ:
```json
{
    "user_id": "string",
    "query": "string",
    "top_k": 5,
    "search_content": false,
    "include_retrieved_data": false
}
```

レスポンス:
```json
{
    "result": {
        "answer": "string",
        "retrieved_data": "string (optional)"
    }
}
```

## 制限事項

- 一度の履歴取得は最大1000件まで
- 埋め込みベクトルの次元は1536固定
- OpenAI以外のLLMプロバイダーはサポートされていない（ただし、`llm`と`embed`メソッドをオーバーライドすることで対応可能）