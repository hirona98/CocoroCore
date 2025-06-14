# CocoroCore 理想的なAPI設計

## 設計原則

1. **AIAvatarKit標準への準拠**
   - AIAvatarKitが提供する標準的なインターフェースを最大限活用
   - カスタムエンドポイントは最小限に留める
   - 拡張はメタデータとツールで実現

2. **シンプルさの追求**
   - 単一責任の原則に従う
   - CocoroCore = AIエージェントのコア機能のみ
   - 周辺機能は外部コンポーネントに委譲

3. **ステートレス設計**
   - セッション状態はcontext_idで管理
   - 永続化が必要な情報は外部ストレージ（ChatMemory）へ

## 提供すべきAPI

### 1. コア機能（AIAvatarKit標準）

#### POST /chat
**AIAvatarKitの標準エンドポイントをそのまま使用**

```json
// リクエスト
{
  "text": "こんにちは",
  "session_id": "unique-session-id",
  "user_id": "user-123",
  "context_id": "context-456",  // 省略可能、自動生成
  "files": [],  // 画像など
  "metadata": {
    // アプリケーション固有のデータ
    "source": "cocoro_dock",
    "character": "alice",
    "notification": {
      "from": "Calendar",
      "message": "Meeting in 5 minutes"
    }
  }
}

// レスポンス（SSE）
data: {"type": "start", "context_id": "context-456", ...}
data: {"type": "chunk", "text": "こんにちは！", "voice_text": "こんにちは！", ...}
data: {"type": "tool_call", "tool_call": {"name": "search_memory", ...}}
data: {"type": "final", "text": "こんにちは！今日はいい天気ですね。", ...}
```

**特徴：**
- SSE（Server-Sent Events）によるストリーミング
- メタデータによる拡張性（通知、キャラクター指定など）
- ツール呼び出しのネイティブサポート

### 2. 管理用エンドポイント（最小限）

#### GET /health
**ヘルスチェック**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "llm_status": "ready",
  "memory_status": "connected"
}
```

#### POST /shutdown
**グレースフルシャットダウン**
```json
{
  "grace_period_seconds": 30
}
```

### 3. 外部連携の考え方

#### A. ChatMemory（長期記憶）
**LLMツールとして実装**
```python
@sts.llm.tool(search_memory_spec)
async def search_memory(query: str, metadata: dict = None):
    # ChatMemoryのAPIを呼び出し
    pass

@sts.llm.tool(add_knowledge_spec)
async def add_knowledge(knowledge: str, metadata: dict = None):
    # ChatMemoryのAPIを呼び出し
    pass
```

#### B. 通知処理
**メタデータまたは専用ツールとして実装**
```python
# 方法1: メタデータで受け取り
request.metadata.get("notification")

# 方法2: 専用ツールとして
@sts.llm.tool(process_notification_spec)
async def process_notification(app_name: str, message: str):
    # 通知に対する反応を生成
    pass
```

#### C. UI表示・音声合成
**フックで実装**
```python
@sts.on_finish
async def send_to_ui_and_tts(request, response):
    # CocoroDockへ送信（チャット表示）
    # CocoroShellへ送信（音声合成・アニメーション）
    pass
```

## 実装の重要ポイント

### 1. システムプロンプトの動的管理
```python
# キャラクター別のプロンプトを動的に設定
system_prompt = load_character_prompt(character_name)
llm.system_prompt = system_prompt
```

### 2. コンテキスト管理
```python
# AIAvatarKitの標準的なコンテキスト管理を使用
# context_idで会話の継続性を保証
# 必要に応じてcontext_managerをカスタマイズ
```

### 3. エラーハンドリング
```python
# 外部サービスの障害に対する適切な対処
# ChatMemory障害 → 機能は低下するが動作は継続
# UI/TTS障害 → ログに記録して処理は継続
```

## なぜこの設計が理想的か

1. **AIAvatarKitの思想に忠実**
   - 標準的な使い方でフレームワークの恩恵を最大限受けられる
   - アップデートへの追従が容易

2. **拡張性が高い**
   - メタデータとツールで機能追加が可能
   - 新しい要件にも柔軟に対応

3. **保守性が高い**
   - シンプルな構造で理解しやすい
   - 各コンポーネントの責任が明確

4. **パフォーマンスが良い**
   - 不要な中間層がない
   - SSEによる効率的なストリーミング

## 現在の実装との違い

### 削除すべきもの
- カスタムエンドポイント（必要性が低い）
- 複雑な通信レイヤー
- 重複した機能

### 改善すべきもの
- システムプロンプトの管理方法
- エラーハンドリングの統一
- ログ出力の整理

### 維持すべきもの
- AIAvatarHttpServerの使用
- ChatMemoryとのツール統合
- フックによる外部連携

## まとめ

CocoroCoreは、AIAvatarKitの標準的な使い方に従い、単一の`/chat`エンドポイントを中心とした設計にすべきです。カスタマイズはメタデータ、ツール、フックで実現し、コアはシンプルに保つことで、保守性と拡張性の両立を実現できます。