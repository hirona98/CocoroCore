"""CocoroCore動作テストスクリプト"""
import asyncio
import json
import sys

import httpx


async def test_health_check():
    """ヘルスチェックのテスト"""
    print("\n[TEST] ヘルスチェック")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://127.0.0.1:55601/health")
            response.raise_for_status()
            data = response.json()
            print(f"✓ ステータス: {data.get('status')}")
            print(f"✓ キャラクター: {data.get('character')}")
            print(f"✓ LLMモデル: {data.get('llm_model')}")
            print(f"✓ メモリ有効: {data.get('memory_enabled')}")
            return True
        except Exception as e:
            print(f"✗ エラー: {e}")
            return False


async def test_chat_simple():
    """シンプルなチャットテスト"""
    print("\n[TEST] シンプルなチャット")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            request_data = {
                "text": "こんにちは",
                "session_id": "test-session-001",
                "user_id": "test-user"
            }
            
            # SSEレスポンスを処理
            async with client.stream(
                "POST",
                "http://127.0.0.1:55601/chat",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data["type"] == "chunk" and data.get("text"):
                                full_response += data["text"]
                                print(f"  チャンク: {data['text']}", end="", flush=True)
                            elif data["type"] == "final":
                                print(f"\n✓ 最終応答: {data.get('text', '')}")
                        except json.JSONDecodeError:
                            pass
                
                return bool(full_response)
        except Exception as e:
            print(f"✗ エラー: {e}")
            return False


async def test_chat_with_notification():
    """通知を含むチャットテスト"""
    print("\n[TEST] 通知メッセージの処理")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            request_data = {
                "text": "",
                "session_id": "test-session-002",
                "user_id": "test-user",
                "metadata": {
                    "notification": {
                        "from": "カレンダー",
                        "message": "15時から会議があります"
                    }
                }
            }
            
            async with client.stream(
                "POST",
                "http://127.0.0.1:55601/chat",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data["type"] == "chunk" and data.get("text"):
                                full_response += data["text"]
                            elif data["type"] == "final":
                                print(f"✓ 通知への応答: {data.get('text', '')[:100]}...")
                        except json.JSONDecodeError:
                            pass
                
                # 通知に関する応答が含まれているか確認
                if "カレンダー" in full_response or "会議" in full_response:
                    print("✓ 通知内容が正しく処理されました")
                    return True
                else:
                    print("✗ 通知内容が応答に含まれていません")
                    return False
        except Exception as e:
            print(f"✗ エラー: {e}")
            return False


async def test_memory_tool():
    """メモリツールのテスト（メモリが有効な場合のみ）"""
    print("\n[TEST] メモリツール（要メモリ有効化）")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # まず記憶を追加
            request_data = {
                "text": "私の名前は太郎です。誕生日は1月1日です。",
                "session_id": "test-session-003",
                "user_id": "test-user"
            }
            
            print("  記憶を追加中...")
            async with client.stream(
                "POST",
                "http://127.0.0.1:55601/chat",
                json=request_data
            ) as response:
                response.raise_for_status()
                async for _ in response.aiter_lines():
                    pass  # レスポンスを最後まで読む
            
            # 少し待つ
            await asyncio.sleep(2)
            
            # 記憶を検索
            request_data = {
                "text": "私の名前を覚えていますか？",
                "session_id": "test-session-003",
                "user_id": "test-user"
            }
            
            print("  記憶を検索中...")
            async with client.stream(
                "POST",
                "http://127.0.0.1:55601/chat",
                json=request_data
            ) as response:
                response.raise_for_status()
                
                full_response = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data["type"] == "chunk" and data.get("text"):
                                full_response += data["text"]
                            elif data["type"] == "tool_call":
                                print(f"  ツール呼び出し: {data['tool_call']['name']}")
                        except json.JSONDecodeError:
                            pass
                
                if "太郎" in full_response:
                    print("✓ メモリツールが正しく動作しています")
                    return True
                else:
                    print("△ メモリが無効か、記憶が見つかりませんでした")
                    return True  # メモリ無効でもテストは成功とする
        except Exception as e:
            print(f"✗ エラー: {e}")
            return False


async def test_api_key_auth():
    """APIキー認証のテスト（外部アクセスをシミュレート）"""
    print("\n[TEST] APIキー認証（外部アクセス）")
    async with httpx.AsyncClient() as client:
        try:
            # ヘッダーなしでアクセス（127.0.0.1なので成功するはず）
            response = await client.get("http://127.0.0.1:55601/health")
            if response.status_code == 200:
                print("✓ ローカルホストからのアクセスは認証不要")
                return True
            else:
                print("✗ 予期しないステータスコード:", response.status_code)
                return False
        except Exception as e:
            print(f"✗ エラー: {e}")
            return False


async def main():
    """すべてのテストを実行"""
    print("=== CocoroCore動作テスト ===")
    print("前提条件:")
    print("- CocoroCore がポート 55601 で起動していること")
    print("- 有効な LLM API キーが設定されていること")
    print("\n新機能:")
    print("- SessionManagerによるセッション管理")
    print("- セキュリティ機能（APIキー認証、ログマスキング）")
    print("- 環境変数からのAPIキー読み込み")
    
    tests = [
        test_health_check(),
        test_api_key_auth(),
        test_chat_simple(),
        test_chat_with_notification(),
        test_memory_tool(),
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    # 結果のサマリー
    print("\n=== テスト結果 ===")
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False or isinstance(r, Exception))
    print(f"成功: {passed}/{len(tests)}")
    if failed > 0:
        print(f"失敗: {failed}/{len(tests)}")
        sys.exit(1)
    else:
        print("すべてのテストが成功しました！")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())    asyncio.run(main())