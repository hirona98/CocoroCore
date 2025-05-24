# ChatMemory統合ガイド

このドキュメントでは、CocoroAIでChatMemoryを使用した長期記憶機能の設定方法を説明します。

## 設定方法

### 1. ChatMemoryサーバーのセットアップ

まず、ChatMemoryサーバーを起動する必要があります。ChatMemoryはPostgreSQLとpgvector拡張を使用します。

```bash
# PostgreSQLとpgvectorのセットアップ（既にインストール済みの場合はスキップ）
# Docker Composeを使用する場合の例:
docker-compose up -d postgres

# ChatMemoryサーバーの起動
pip install chatmemory
python -m chatmemory --host 0.0.0.0 --port 8000
```

### 2. CocoroAIの設定

`UserData/setting.json`に以下の設定を追加します：

```json
{
  "chatMemoryEnabled": true,
  "chatMemoryUrl": "http://localhost:8000",
  // ... 既存の設定 ...
}
```

### 設定項目の説明

- `chatMemoryEnabled` (boolean): ChatMemory機能を有効にするかどうか（デフォルト: false）
- `chatMemoryUrl` (string): ChatMemoryサーバーのURL（デフォルト: "http://localhost:8000"）

## 使用方法

### 記憶の保存

CocoroAIとの会話は自動的にChatMemoryに保存されます。各会話は以下の情報と共に保存されます：

- ユーザーID（デフォルト: "default_user"）
- セッションID（デフォルト: "default_session"）
- チャンネル（"cocoro_ai"固定）

### 記憶の検索

AIは必要に応じて過去の記憶を検索します。例えば：

- 「前に話した内容を覚えている？」
- 「私の好きな食べ物は何だっけ？」
- 「この前の話の続きをしよう」

といった質問に対して、自動的に`search_memory`ツールを使用して過去の会話から関連情報を取得します。

## 実装詳細

### ChatMemoryClient

`cocoro_core.py`に実装されている`ChatMemoryClient`クラスは、ChatMemoryサーバーとの通信を管理します：

```python
class ChatMemoryClient:
    def __init__(self, base_url: str, timeout: float = 30.0)
    async def enqueue_messages(self, request, response)
    async def save_history(self, user_id: str, session_id: str, channel: str = "cocoro_ai")
    async def search(self, user_id: str, query: str, top_k: int = 5) -> Optional[str]
    async def close(self)
```

### 統合フロー

1. **初期化時**: ChatMemory設定が有効な場合、`ChatMemoryClient`インスタンスを作成
2. **会話時**: `on_finish`コールバックで会話内容をキューに追加し、履歴として保存
3. **検索時**: `search_memory`ツールで過去の記憶を検索
4. **終了時**: `shutdown`イベントでクライアントをクリーンアップ

## トラブルシューティング

### ChatMemoryサーバーに接続できない

1. ChatMemoryサーバーが起動しているか確認
2. URLが正しいか確認（デフォルト: http://localhost:8000）
3. ファイアウォール設定を確認

### 記憶が保存されない

1. `chatMemoryEnabled`が`true`になっているか確認
2. ChatMemoryサーバーのログを確認
3. PostgreSQLが正常に動作しているか確認

### 記憶の検索が機能しない

1. 会話履歴が正しく保存されているか確認（ChatMemoryのAPIで確認可能）
2. OpenAI APIキーが正しく設定されているか確認（埋め込みベクトル生成に必要）

## 注意事項

- ChatMemoryは現在、PostgreSQLをバックエンドとして使用します
- 埋め込みベクトルの生成にはOpenAI APIを使用します（ChatMemoryサーバー側で設定が必要）
- デフォルトではすべてのユーザーが"default_user"として扱われます。複数ユーザーに対応する場合は、追加の実装が必要です