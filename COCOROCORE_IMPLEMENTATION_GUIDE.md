# CocoroCore 実装ガイド（理想的な実装）

## 1. 最小限のmain.py実装例

```python
import asyncio
import uvicorn
from fastapi import FastAPI
from aiavatar.adapter.http.server import AIAvatarHttpServer
from aiavatar.sts.pipeline import STSPipeline
from aiavatar.sts.llm.litellm import LiteLLMService
from aiavatar.sts.tts import SpeechSynthesizerDummy

from config_loader import load_config
from memory_tools import setup_memory_tools
from external_clients import setup_external_clients

def create_app(config_dir=None):
    # 設定読み込み
    config = load_config(config_dir)
    character = config["characterList"][config["currentCharacterIndex"]]
    
    # LLMサービスの初期化（キャラクター固有のプロンプト使用）
    llm = LiteLLMService(
        api_key=character["apiKey"],
        model=character["llmModel"],
        temperature=1.0,
        system_prompt=character.get("systemPrompt", "あなたは親切なアシスタントです。")
    )
    
    # STSパイプラインの初期化
    sts = STSPipeline(
        llm=llm,
        tts=SpeechSynthesizerDummy(),  # 音声合成はCocoroShell側
        voice_recorder_enabled=False
    )
    
    # ChatMemoryツールの設定（有効な場合のみ）
    if character.get("isEnableMemory", False):
        memory_client = setup_memory_tools(sts, config)
    
    # 外部クライアントの設定
    external_clients = setup_external_clients(config)
    
    # 応答完了時の処理
    @sts.on_finish
    async def handle_response(request, response):
        """AI応答を外部コンポーネントへ送信"""
        tasks = []
        
        # CocoroDockへの送信
        if external_clients.get("cocoro_dock") and response.text:
            tasks.append(
                external_clients["cocoro_dock"].send_chat_message(
                    role="assistant",
                    content=response.text
                )
            )
        
        # CocoroShellへの送信（音声合成）
        if external_clients.get("cocoro_shell") and response.text:
            voice_params = {
                "speaker_id": character.get("voiceSpeakerId", 1),
                "speed": character.get("voiceSpeed", 1.0),
                "pitch": character.get("voicePitch", 0.0),
                "volume": character.get("voiceVolume", 1.0)
            }
            tasks.append(
                external_clients["cocoro_shell"].send_chat_for_speech(
                    content=response.text,
                    voice_params=voice_params,
                    character_name=character.get("name")
                )
            )
        
        # 並列実行
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # AIAvatarHttpServerの作成
    aiavatar_app = AIAvatarHttpServer(sts=sts, debug=False)
    
    # FastAPIアプリの設定
    app = FastAPI()
    app.include_router(aiavatar_app.get_api_router())
    
    # ヘルスチェックエンドポイント（管理用）
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "character": character.get("name", "unknown")
        }
    
    return app, config.get("cocoroCorePort", 55601)

if __name__ == "__main__":
    app, port = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
```

## 2. メタデータを活用した通知処理

```python
# 通知を含むリクエストの例
{
    "text": "",  # 空でも可
    "session_id": "session-123",
    "user_id": "user-456",
    "metadata": {
        "notification": {
            "from": "Calendar",
            "message": "会議が5分後に始まります",
            "priority": "high"
        }
    }
}

# STSパイプラインでの処理
@sts.on_before_llm
async def process_metadata(request):
    """メタデータから通知を検出して処理"""
    if request.metadata and "notification" in request.metadata:
        notification = request.metadata["notification"]
        # 通知をユーザーメッセージとして扱う
        request.text = (
            f"アプリ「{notification['from']}」から"
            f"通知が届きました：「{notification['message']}」"
        )
```

## 3. LLMツールによる拡張

```python
def setup_memory_tools(sts, config):
    """ChatMemoryとの統合をツールで実現"""
    memory_client = ChatMemoryClient(
        f"http://localhost:{config['cocoroMemoryPort']}"
    )
    
    # 記憶検索ツール
    search_memory_spec = {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "過去の会話や記憶から情報を検索します",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索クエリ"
                    }
                },
                "required": ["query"]
            }
        }
    }
    
    @sts.llm.tool(search_memory_spec)
    async def search_memory(query: str, metadata: dict = None):
        user_id = metadata.get("user_id", "default_user")
        result = await memory_client.search(user_id, query)
        return result or "関連する記憶が見つかりませんでした。"
    
    # その他のツールも同様に定義
    return memory_client
```

## 4. 動的な設定管理

```python
class DynamicConfigManager:
    """設定の動的リロードをサポート"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self._config = None
        self._last_modified = None
    
    def get_config(self):
        """設定を取得（変更があれば自動リロード）"""
        current_modified = os.path.getmtime(self.config_path)
        if self._last_modified != current_modified:
            self._config = load_config(self.config_path)
            self._last_modified = current_modified
        return self._config
    
    def get_current_character(self):
        """現在のキャラクター設定を取得"""
        config = self.get_config()
        return config["characterList"][config["currentCharacterIndex"]]
```

## 5. エラーハンドリングとフォールバック

```python
class ResilientExternalClient:
    """外部サービスとの通信を堅牢に"""
    
    def __init__(self, base_url, service_name):
        self.base_url = base_url
        self.service_name = service_name
        self.client = httpx.AsyncClient(timeout=5.0)
        self._is_healthy = True
    
    async def send_message(self, endpoint, data):
        """エラー時は静かに失敗"""
        try:
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                json=data
            )
            response.raise_for_status()
            self._is_healthy = True
            return True
        except Exception as e:
            if self._is_healthy:
                # 初回エラー時のみログ出力
                logger.warning(
                    f"{self.service_name}への送信に失敗しました: {e}"
                )
                self._is_healthy = False
            return False
```

## 6. パフォーマンス最適化

```python
# 応答の並列送信
@sts.on_finish
async def optimized_response_handler(request, response):
    """複数の宛先への並列送信"""
    # 送信タスクを作成
    tasks = []
    for client_name, client in external_clients.items():
        if client and response.text:
            task = client.send_async(response)
            tasks.append(task)
    
    # すべて並列実行（エラーは無視）
    if tasks:
        results = await asyncio.gather(
            *tasks, 
            return_exceptions=True
        )
        # エラーのみログ出力
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.debug(f"送信エラー: {result}")
```

## 7. テスト可能な設計

```python
# 依存性注入を活用
def create_app(
    config_loader=None,
    llm_service=None,
    memory_client=None,
    external_clients=None
):
    """テスト時にモックを注入可能"""
    config_loader = config_loader or load_config
    config = config_loader()
    
    # 各コンポーネントをオプショナルに
    llm = llm_service or create_llm_service(config)
    memory = memory_client or create_memory_client(config)
    clients = external_clients or create_external_clients(config)
    
    # ... rest of initialization
```

## まとめ

この実装ガイドは、AIAvatarKitの設計思想に従いながら、CocoroAIの要件を満たす最小限でエレガントな実装を示しています。

**キーポイント：**
1. 標準的なAIAvatarKitの使い方を優先
2. カスタマイズはメタデータ、ツール、フックで実現
3. 外部サービスとの通信は堅牢に
4. 設定は動的に管理
5. テスト可能な設計

この設計により、保守性、拡張性、パフォーマンスのバランスが取れた実装が可能になります。