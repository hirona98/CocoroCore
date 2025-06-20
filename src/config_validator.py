"""設定の検証ユーティリティ"""


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
        
        # STT設定のチェック
        if char.get("isUseSTT"):
            if not char.get("sttApiKey"):
                warnings.append(f"キャラクター{i}: STTが有効ですがAPIキーが設定されていません")
            
            stt_engine = char.get("sttEngine", "amivoice").lower()
            if stt_engine not in ["amivoice", "openai"]:
                warnings.append(f"キャラクター{i}: 不正なSTTエンジン '{stt_engine}' (有効値: amivoice, openai)")
    
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