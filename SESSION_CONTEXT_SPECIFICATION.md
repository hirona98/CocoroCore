# CocoroCore セッション・コンテキスト仕様書

## 概要

このドキュメントは、CocoroCoreにおけるsession_idとcontext_idの仕様を説明します。
CocoroDockやCocoroShellの実装者向けのリファレンスです。

## 1. session_idの仕様

### 定義
- **session_id**: クライアントセッションを識別するID
- クライアント（CocoroDock/CocoroShell）が生成・管理
- 形式は自由（ユニークであれば良い）

### 用途
- SessionManagerでのセッション管理
- タイムアウト管理（5分間）
- 同時実行の制御

### 推奨形式
```
{client_prefix}_{timestamp}_{uuid}

例：
- dock_20240120123456_a1b2c3d4...
- shell_20240120123456_e5f6g7h8...
```

### CocoroCore側の処理
```python
# SessionManagerでの管理
await session_manager.update_activity(
    request.user_id or 'default_user',
    request.session_id
)
```

## 2. context_idの仕様

### 定義
- **context_id**: 会話の文脈を管理するID
- AIAvatarKitが管理
- 会話履歴の継続性を保証

### 生成ルール
1. クライアントがcontext_idを指定しない場合 → CocoroCoreが自動生成
2. 無効なcontext_idが指定された場合 → 新規生成
3. 有効なcontext_idが指定された場合 → 会話を継続

### AIAvatarKitの処理フロー
```python
# STSPipeline内部の処理
if request.context_id:
    if last_created_at == datetime.min.replace(tzinfo=timezone.utc):
        # 無効なcontext_id
        request.context_id = None

if not request.context_id:
    # 新規生成
    request.context_id = str(uuid4())
```

## 3. 実装パターン

### パターン1: 新規会話開始
```json
// Request
{
    "text": "こんにちは",
    "session_id": "dock_20240120_001",
    "user_id": "user",
    "context_id": null  // または省略
}

// Response (SSE)
data: {"type": "start", "context_id": "newly-generated-context-id", ...}
```

### パターン2: 会話継続
```json
// Request
{
    "text": "前の話の続きですが",
    "session_id": "dock_20240120_001",
    "user_id": "user",
    "context_id": "existing-context-id"  // 前回取得したID
}

// Response (SSE)
data: {"type": "start", "context_id": "existing-context-id", ...}
```

### パターン3: セッション変更・コンテキスト継続
```json
// Request（アプリ再起動後など）
{
    "text": "さっきの話ですが",
    "session_id": "dock_20240120_002",  // 新しいセッション
    "user_id": "user",
    "context_id": "existing-context-id"  // 同じコンテキスト
}

// 会話は継続される
```

## 4. ライフサイクル

### session_idのライフサイクル
```
[CocoroDock起動]
    ↓
[session_id生成] → [メッセージ送信] → [5分間活動なし] → [タイムアウト]
    ↓                    ↓
[アプリ終了]         [継続使用]
```

### context_idのライフサイクル
```
[初回メッセージ]
    ↓
[context_id生成] → [会話継続] → [新規会話ボタン] → [context_id破棄]
                      ↓
                  [永続的に保持]
```

## 5. ChatMemoryとの連携

### セッションタイムアウト時
- SessionManagerが5分間のタイムアウトを検出
- ChatMemoryに要約生成を依頼
- context_idは引き続き有効

### 会話履歴の保存
```python
# CocoroCoreでの処理
await memory_client.save_history(
    user_id=request.user_id or "default_user",
    session_id=request.session_id,
    channel="cocoro_ai"
)
```

## 6. ベストプラクティス

### DO ✅
1. session_idは起動時に生成し、アプリ終了まで保持
2. context_idはSSEレスポンスから取得して保存
3. 新規会話時はcontext_idをnullにする
4. エラー時もsession_idは維持する

### DON'T ❌
1. context_idを独自に生成しない
2. session_idを頻繁に変更しない
3. 他のユーザーのcontext_idを使用しない
4. context_idの形式を解析しない（不透明な文字列として扱う）

## 7. トラブルシューティング

### Q: context_idが返ってこない
A: SSEのstartイベントを確認。type="start"のデータに含まれています。

### Q: 会話が継続されない
A: context_idが正しく送信されているか確認。nullや空文字では新規会話になります。

### Q: セッションがすぐタイムアウトする
A: session_idが一定であることを確認。毎回変わると新規セッションになります。

### Q: 「Invalid context_id」のログが出る
A: 古いまたは無効なcontext_id。CocoroCoreが新規生成するので問題ありません。

## 8. 実装例

### CocoroDock (C#)
```csharp
private string? _currentSessionId;
private string? _currentContextId;

public async Task SendMessage(string text)
{
    _currentSessionId ??= GenerateSessionId();
    
    var request = new {
        text = text,
        session_id = _currentSessionId,
        user_id = "user",
        context_id = _currentContextId
    };
    
    // SSEレスポンス処理
    // context_idを保存
    _currentContextId = responseContextId;
}

public void StartNewConversation()
{
    _currentContextId = null;  // 新規会話
    // session_idは維持
}
```

### CocoroShell (Unity/C#)
```csharp
// 同様の実装パターン
```

---

このドキュメントは、CocoroCore v1.0.0の仕様に基づいています。
更新履歴はGitリポジトリを参照してください。