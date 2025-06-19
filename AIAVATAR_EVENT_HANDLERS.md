# AIAvatarKit STSPipeline イベントハンドラー調査結果 by Claude Code

## 利用可能なイベントハンドラー（デコレーター）

### 1. STSPipeline クラスのイベント

#### @sts.on_before_llm
- **用途**: LLM処理の前に実行される
- **引数**: `async def handler(request: STSRequest)`
- **使用例**: 
```python
@sts.on_before_llm
async def preprocess_notification(request):
    # リクエストのテキストを前処理
    if request.text:
        request.text = preprocess_text(request.text)
```

#### @sts.on_before_tts
- **用途**: 音声合成（TTS）処理の前に実行される
- **引数**: `async def handler(request: STSRequest)`
- **使用例**:
```python
@sts.on_before_tts
async def before_tts(request):
    # TTS前の処理
    logger.info("Starting TTS")
```

#### @sts.on_finish
- **用途**: パイプライン処理完了時に実行される
- **引数**: `async def handler(request: STSRequest, response: STSResponse)`
- **使用例**:
```python
@sts.on_finish
async def on_response_complete(request, response):
    # 応答完了後の処理
    logger.info(f"Response completed: {response.text}")
```

#### @sts.process_llm_chunk
- **用途**: LLMのストリーミングレスポンスの各チャンクを処理
- **引数**: `async def handler(response: STSResponse) -> dict`
- **戻り値**: 解析された情報（例: `{"language": "ja"}`）
- **使用例**:
```python
@sts.process_llm_chunk
async def process_chunk(llm_stream_chunk):
    # 言語情報などを解析
    return {"language": detect_language(llm_stream_chunk.text)}
```

### 2. VAD（音声アクティビティ検出）のイベント

#### @vad.on_speech_detected
- **用途**: 音声が検出されたときに実行される
- **引数**: `async def handler(data: bytes, recorded_duration: float, session_id: str)`
- **注意**: このイベントはVADインスタンスに対して設定する
- **デフォルト動作**: STSPipelineが自動的に音声データをパイプラインに渡す

### 3. 音声認識結果の取得方法

**重要**: `@sts.on_speech_recognized` というイベントハンドラーは存在しません。

音声認識結果は以下の方法で取得できます：

1. **on_before_llm内でrequest.textを確認**
```python
@sts.on_before_llm
async def check_speech_recognition(request):
    if request.text:
        logger.info(f"認識されたテキスト: {request.text}")
        # ウェイクワード検出など
        if "ココロ" in request.text:
            logger.info("ウェイクワード検出!")
```

2. **on_finishでresponseのmetadataを確認**
```python
@sts.on_finish
async def check_request_text(request, response):
    # リクエストのテキスト（音声認識結果）にアクセス
    if request.text:
        logger.info(f"ユーザー入力: {request.text}")
```

## ウェイクワード機能

STSPipelineには組み込みのウェイクワード機能があります：

```python
sts = STSPipeline(
    wakewords=["ココロ", "ねえココロ"],  # ウェイクワードのリスト
    wakeword_timeout=60.0,  # タイムアウト（秒）
    # ... 他の設定
)
```

- ウェイクワードが設定されている場合、タイムアウト後はウェイクワードが含まれるリクエストのみ処理されます
- `is_awake()` メソッドで内部的に判定されます

## 推奨される実装パターン

```python
# 音声認識とウェイクワード検出の実装例
@sts.on_before_llm
async def handle_speech_input(request):
    if request.text:
        logger.info(f"音声認識結果: '{request.text}'")
        
        # カスタムウェイクワード処理が必要な場合
        wakewords = ["ココロ", "ねえココロ"]
        for wakeword in wakewords:
            if wakeword in request.text:
                logger.info(f"ウェイクワード '{wakeword}' を検出しました")
                # 特別な処理を実行
                break

# 応答完了時の処理
@sts.on_finish
async def on_complete(request, response):
    logger.info(f"ユーザー: {request.text}")
    logger.info(f"アシスタント: {response.text}")
```

## 実装済みの修正内容

現在のcocoro_core.pyでは、以下のように修正済みです：

### 音声認識が有効な場合
```python
@sts.on_before_llm
async def handle_speech_and_notification(request):
    # 音声認識結果のログ出力とウェイクワード検出
    if request.text:
        logger.info(f"音声認識結果: '{request.text}'")
        if wakewords:
            for wakeword in wakewords:
                if wakeword.lower() in request.text.lower():
                    logger.info(f"ウェイクワード検出: '{wakeword}'")
    
    # 通知タグの処理も統合
    if request.text and "<cocoro-notification>" in request.text:
        # 通知処理...
```

### 音声認識が無効な場合
```python
@sts.on_before_llm
async def preprocess_notification(request):
    # 通知タグの処理のみ
    if request.text and "<cocoro-notification>" in request.text:
        # 通知処理...
```

この実装により、音声認識の有無に関わらず、適切にイベントハンドリングが行われます。