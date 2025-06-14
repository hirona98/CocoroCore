"""セキュリティ関連のユーティリティ"""
import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


class SimpleAPIKeyAuth(HTTPBearer):
    """シンプルなAPIキー認証"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(auto_error=True)
        # APIキーが設定されていない場合は、環境変数から取得するか生成
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get("COCOROCORE_API_KEY")
            if not self.api_key:
                # 開発環境用に警告を出してランダムキーを生成
                self.api_key = secrets.token_urlsafe(32)
                print(f"警告: APIキーが設定されていません。一時的なキーを生成しました: {self.api_key}")
                print("本番環境では環境変数 COCOROCORE_API_KEY を設定してください。")
    
    async def __call__(self, request: Request) -> str:
        # ローカルホストからのアクセスは許可（開発用）
        if request.client.host in ["127.0.0.1", "localhost", "::1"]:
            return "localhost"
        
        # 認証ヘッダーをチェック
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not self.verify_api_key(credentials.credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return credentials.credentials
    
    def verify_api_key(self, api_key: str) -> bool:
        """APIキーを検証（タイミング攻撃対策）"""
        return hmac.compare_digest(api_key, self.api_key)


def mask_sensitive_data(text: str, patterns: list = None) -> str:
    """機密情報をマスクする
    
    Args:
        text: マスク対象のテキスト
        patterns: マスクするパターンのリスト（正規表現）
    
    Returns:
        マスクされたテキスト
    """
    if patterns is None:
        patterns = [
            # 一般的なAPIキーパターン
            r'(?i)(api[_-]?key|apikey|api_secret|secret[_-]?key)\s*[:=]\s*["\']?([^"\'\\s]+)',
            # メールアドレス
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            # 電話番号（日本）
            r'0\d{1,4}-\d{1,4}-\d{4}',
            r'0\d{9,10}',
            # クレジットカード番号風の数字列
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        ]
    
    import re
    masked_text = text
    
    for pattern in patterns:
        # パターンにマッチする部分を***でマスク
        masked_text = re.sub(pattern, lambda m: '*' * len(m.group(0)), masked_text)
    
    return masked_text


def validate_config(config: dict) -> list:
    """設定の検証とセキュリティチェック
    
    Args:
        config: 検証する設定辞書
    
    Returns:
        警告メッセージのリスト
    """
    warnings = []
    
    # 必須フィールドのチェック
    if not config.get("characterList"):
        warnings.append("characterListが設定されていません")
    
    # APIキーのチェック
    for i, char in enumerate(config.get("characterList", [])):
        if char.get("isUseLLM") and not char.get("apiKey"):
            warnings.append(f"キャラクター{i}: LLMが有効ですがAPIキーが設定されていません")
        
        # APIキーが平文で保存されている警告
        if char.get("apiKey") and not char.get("apiKey").startswith("${"):
            warnings.append(f"キャラクター{i}: APIキーが平文で保存されています。環境変数の使用を推奨します")
    
    # ポート番号の妥当性チェック
    ports = [
        ("cocoroCorePort", 55601),
        ("cocoroDockPort", 55600),
        ("cocoroMemoryPort", 55602),
        ("cocoroShellPort", 55605),
    ]
    
    for port_name, default_port in ports:
        port = config.get(port_name, default_port)
        if not isinstance(port, int) or port < 1024 or port > 65535:
            warnings.append(f"{port_name}: 無効なポート番号 ({port})")
    
    return warnings


class RateLimiter:
    """シンプルなレート制限"""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Args:
            max_requests: 時間枠内の最大リクエスト数
            time_window: 時間枠（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """レート制限をチェック
        
        Args:
            client_id: クライアント識別子
            
        Returns:
            制限内ならTrue、超過ならFalse
        """
        import time
        current_time = time.time()
        
        # 古いエントリを削除
        self.requests = {
            cid: times for cid, times in self.requests.items()
            if any(t > current_time - self.time_window for t in times)
        }
        
        # クライアントのリクエスト履歴を取得
        client_requests = self.requests.get(client_id, [])
        
        # 時間枠内のリクエストをフィルタ
        recent_requests = [t for t in client_requests if t > current_time - self.time_window]
        
        # 制限チェック
        if len(recent_requests) >= self.max_requests:
            return False
        
        # リクエストを記録
        recent_requests.append(current_time)
        self.requests[client_id] = recent_requests
        
        return True