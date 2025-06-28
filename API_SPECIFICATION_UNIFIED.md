# 統一API仕様書

## 概要

この文書は、CocoroCore、CocoroDock、CocoroShell間のREST API通信仕様を統一するための正式な仕様書です。
各コンポーネントの実装者は、この仕様に厳密に従って実装してください。

## 1. CocoroDock API仕様（ポート: 55600）

### 1.1 POST /api/addChatUi

チャットメッセージをUIに表示します。
CocoroCoreが使います。

**リクエスト:**

```json
{
  "role": "user" | "assistant",
  "content": "メッセージ内容",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**エラーレスポンス (400/500):**

```json
{
  "status": "error",
  "message": "エラーの詳細",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 1.2 GET /api/config

現在の設定を取得します。

**レスポンス (200 OK):**

```json
{
    内容は ./UserData/defaultSetting.json 参照
}
```

### 1.3 PUT /api/config

設定を更新します。

**リクエスト:**

```json
{
  // getと同じ
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "message": "Configuration updated",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 1.4 POST /api/control

制御コマンドを実行します。

**リクエスト:**

```json
{
  "command": "shutdown" | "restart" | "reloadConfig",
  "params": {},
  "reason": "ユーザーリクエスト"  // optional
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "message": "Command executed",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 1.5 POST /api/status

ステータスバーの表示を更新します。
CocoroCoreが各処理状態を通知するために使用します。

**リクエスト:**

```json
{
  "message": "ステータスメッセージ",
  "statusType": "voice_waiting" | "voice_detected" | "amivoice_sending" | "amivoice_completed" | "llm_sending" | "llm_completed" | "memory_accessing" | "memory_accessed",  // optional
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**ステータスタイプの説明:**
- `voice_waiting`: 音声入力待機中
- `voice_detected`: 音声を検出
- `amivoice_sending`: 音声認識中（AmiVoice送信中）
- `amivoice_completed`: 音声認識完了
- `llm_sending`: AI処理中（LLM送信中）
- `llm_completed`: AI処理完了
- `memory_accessing`: 記憶機能アクセス中
- `memory_accessed`: 記憶機能アクセス完了

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "message": "Status updated",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 2. CocoroShell API仕様（ポート: 55605）

### 2.1 POST /api/chat

音声合成付きでチャットメッセージを表示します。

CocoroCoreが使います。


**リクエスト:**

```json
{
  "content": "音声合成するテキスト",
  "voiceParams": {
    "speaker_id": 1,
    "speed": 1.0,
    "pitch": 0.0,
    "volume": 1.0
  },
  "animation": "talk" | "idle" | null,
  "characterName": "Uni"  // optional
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 2.2 POST /api/animation

アニメーションを制御します。

CocoroDockが使います。

**リクエスト:**

```json
{
  "animationName": "アニメーション名",
  "loop": false,  // optional
  "duration": 0.0  // optional
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 2.3 POST /api/control

制御コマンドを実行します。

CocoroDockが使います。

**リクエスト:**

```json
{
  "command": "shutdown" | "restart" | "reloadConfig" | "ttsControl" | "messageWindowControl",
  "params": {
    "enabled": true  // ttsControl、messageWindowControlの場合のみ
  }
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "message": "Command executed",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### TTSコントロール仕様
`ttsControl`コマンドは、TTSの有効/無効を制御します。

**リクエスト例:**
```json
{
  "command": "ttsControl",
  "params": {
    "enabled": false
  }
}
```

#### メッセージウィンドウコントロール仕様
`messageWindowControl`コマンドは、キャラクターのメッセージウィンドウ（吹き出し）の表示/非表示を制御します。

**リクエスト例:**
```json
{
  "command": "messageWindowControl",
  "params": {
    "enabled": true
  }
}
```

**パラメータ:**
- `enabled` (boolean): `true`でメッセージウィンドウ表示、`false`で非表示
- 設定は`setting.json`の`showMessageWindow`フィールドに保存され、アプリケーション再起動後も維持されます

**レスポンス:**
```json
{
  "status": "success",
  "message": "Message window enabled" | "Message window disabled",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 2.4 GET /api/status

現在のステータスを取得します。

CocoroDockが使います。

**レスポンス (200 OK):**

```json
{
  "status": "running",
  "currentCharacter": "キャラクター名",
  "isSpeaking": false,
  "availableAnimations": ["アニメーション名のリスト"],
  "voiceEngine": "voicevox" | "windows",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 3. CocoroCore API仕様（ポート: 55601）

### 3.1 GET /health

ヘルスチェックエンドポイント。

**レスポンス (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "character": "キャラクター名",
  "memory_enabled": true,
  "llm_model": "LLMモデル名",
  "active_sessions": 0
}
```

### 3.2 POST /api/control

制御コマンドを実行します。

CocoroDockが使います。

**リクエスト:**

```json
{
  "command": "shutdown" | "restart" | "reloadConfig" | "sttControl",
  "params": {
    "enabled": true  // sttControlの場合のみ
  }
}
```

**レスポンス (200 OK):**

```json
{
  "status": "success",
  "message": "Command executed",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### STTコントロール仕様
`sttControl`コマンドは、STT（音声認識）の有効/無効を制御します。

**リクエスト例:**
```json
{
  "command": "sttControl",
  "params": {
    "enabled": true
  }
}
```

### 3.3 POST /chat

ユーザーからのチャットメッセージを受信し、LLM処理を行います。（AIAvatarKit仕様準拠）

CocoroDockが使います。

**リクエスト:**

```json
{
  "type": "invoke" | "text",
  "session_id": "dock_20240101000000_12345678",
  "user_id": "user",
  "context_id": null,
  "text": "ユーザーからのメッセージ",
  "audio_data": null,
  "files": [
    {
      "type": "image",
      "url": "data:image/png;base64,..."
    }
  ],  // optional
  "system_prompt_params": null,
  "metadata": {
    "source": "CocoroDock" | "notification",
    "character_name": "Uni",
    "monitoring_type": "desktop"  // デスクトップモニタリングの場合
  }
}
```

**レスポンス (200 OK):**
Server-Sent Events (SSE) ストリーミングレスポンス

```
data: {"type": "chunk", "content": "AIの応答テキスト", "role": "assistant", "session_id": "...", "context_id": "..."}
data: [DONE]
```

#### 特殊用途
- **デスクトップモニタリング**: `text`フィールドに`<cocoro-desktop-monitoring>`、`files`に画像データ
- **通知処理**: `text`フィールドに`<cocoro-notification>\nFrom: 送信者\nMessage: 内容\n</cocoro-notification>`

**注意:** CocoroCoreはAIAvatarKitの標準HTTPサーバーを使用しているため、`/chat`エンドポイントはAIAvatarKitの内部実装により提供されます。通知処理も同じエンドポイントを使用します。

## 4. Notification API仕様（ポート: 55604）

### 4.1 POST /api/v1/notification

外部アプリケーションからの通知を受信します。（変更なし）

## 5. 共通仕様

### 5.1 HTTPステータスコード

- 200 OK: 成功
- 400 Bad Request: リクエスト形式エラー
- 404 Not Found: エンドポイントが存在しない
- 500 Internal Server Error: サーバー内部エラー

### 5.2 Content-Type

- すべてのリクエスト/レスポンス: `application/json; charset=utf-8`

### 5.3 タイムアウト

- デフォルト: 30秒

### 5.4 エラーレスポンス形式

```json
{
  "status": "error",
  "message": "エラーの詳細説明",
  "errorCode": "ERROR_CODE",  // optional
  "timestamp": "2024-01-01T00:00:00Z"
}
```
