"""アプリケーション初期化処理モジュール"""

import logging
from typing import Dict, Optional, Tuple, Any

from config_loader import load_config
from config_validator import validate_config

logger = logging.getLogger(__name__)


def initialize_config(config_dir: Optional[str] = None) -> Dict:
    """設定ファイルの読み込みと検証
    
    Args:
        config_dir: 設定ディレクトリのパス
        
    Returns:
        読み込まれた設定辞書
    """
    # 設定ファイルを読み込む
    config = load_config(config_dir)
    
    # 設定の検証
    config_warnings = validate_config(config)
    for warning in config_warnings:
        logger.warning(f"設定警告: {warning}")
    
    return config


def initialize_dock_log_handler(config: Dict) -> Optional[Any]:
    """CocoroDock用ログハンドラーの初期化
    
    Args:
        config: 設定辞書
        
    Returns:
        初期化されたログハンドラー（失敗時はNone）
    """
    try:
        from log_handler import CocoroDockLogHandler
        
        # 設定からCocoroDockのポート番号を取得
        dock_port = config.get("cocoroDockPort", 55600)
        dock_url = f"http://127.0.0.1:{dock_port}"
        dock_log_handler = CocoroDockLogHandler(dock_url=dock_url, component_name="CocoroCore")
        dock_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        dock_log_handler.setLevel(logging.DEBUG)  # すべてのレベルのログを受け取る
        
        # ルートロガーに追加して、すべてのライブラリのログを取得
        root_logger = logging.getLogger()
        root_logger.addHandler(dock_log_handler)
        logger.info("CocoroDock用ログハンドラーを初期化しました")
        
        return dock_log_handler
    except Exception as e:
        logger.warning(f"CocoroDock用ログハンドラーの初期化に失敗: {e}")
        return None


def setup_debug_mode(config: Dict) -> bool:
    """デバッグモードの設定
    
    Args:
        config: 設定辞書
        
    Returns:
        デバッグモードのフラグ
    """
    debug_mode = config.get("debug", False)
    if debug_mode:
        logger.setLevel(logging.DEBUG)
    return debug_mode


def get_character_config(config: Dict) -> Dict:
    """現在のキャラクター設定を取得
    
    Args:
        config: 設定辞書
        
    Returns:
        現在のキャラクター設定辞書
    """
    character_list = config.get("characterList", [])
    current_index = config.get("currentCharacterIndex", 0)
    if not character_list or current_index >= len(character_list):
        raise ValueError("有効なキャラクター設定が見つかりません")
    
    return character_list[current_index]


def extract_llm_config(config: Dict, current_char: Dict, current_index: int) -> Tuple[str, str, str, str, str]:
    """LLM設定を抽出
    
    Args:
        config: 設定辞書
        current_char: 現在のキャラクター設定
        current_index: 現在のキャラクターインデックス
        
    Returns:
        (llm_api_key, llm_model, system_prompt, base_url, user_id)
    """
    import os
    from time_utils import create_time_guidelines
    
    # LLM設定を取得（環境変数を優先）
    env_api_key = os.environ.get(f"LLM_API_KEY_{current_index}") or os.environ.get("LLM_API_KEY")
    llm_api_key = env_api_key or current_char.get("apiKey")
    llm_model = current_char.get("llmModel")
    system_prompt = current_char.get("systemPrompt", "あなたは親切なアシスタントです。")
    
    # ベースURL設定を取得（ローカルLLM対応）
    base_url = current_char.get("localLLMBaseUrl", "")
    
    # 時間感覚ガイドラインをシステムプロンプトに追加
    system_prompt += create_time_guidelines()
    
    # ユーザーID設定を取得
    user_id = current_char.get("userId", "default_user")
    logger.info(f"設定から読み込んだユーザーID: {user_id}")
    
    if base_url:
        logger.info(f"ローカルLLM BaseURL設定: {base_url}")
    
    return llm_api_key, llm_model, system_prompt, base_url, user_id


def extract_port_config(config: Dict) -> int:
    """ポート設定を取得
    
    Args:
        config: 設定辞書
        
    Returns:
        ポート番号
    """
    return config.get("cocoroCorePort", 55601)


def extract_stt_config(current_char: Dict, config: Dict) -> Tuple[bool, str, str, str, str, bool, float]:
    """STT（音声認識）設定を抽出
    
    Args:
        current_char: 現在のキャラクター設定
        config: 設定辞書
        
    Returns:
        (is_use_stt, stt_engine, stt_wake_word, stt_api_key, stt_language, 
         vad_auto_adjustment, vad_threshold)
    """
    # STT（音声認識）設定
    is_use_stt = current_char.get("isUseSTT", False)
    stt_engine = current_char.get("sttEngine", "amivoice").lower()  # デフォルトはAmiVoice
    stt_wake_word = current_char.get("sttWakeWord", "")
    stt_api_key = current_char.get("sttApiKey", "")
    stt_language = current_char.get("sttLanguage", "ja")  # OpenAI用の言語設定

    # VAD（音声活動検出）設定
    microphone_settings = config.get("microphoneSettings", {})
    vad_auto_adjustment = microphone_settings.get("autoAdjustment", True)  # デフォルトは自動調整ON
    vad_threshold = microphone_settings.get("inputThreshold", -45.0)  # デフォルト閾値は-45dB
    
    return (is_use_stt, stt_engine, stt_wake_word, stt_api_key, stt_language,
            vad_auto_adjustment, vad_threshold)