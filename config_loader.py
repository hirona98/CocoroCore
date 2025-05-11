import json
import os


def load_config():
    """
    setting.jsonファイルから設定を読み込む
    """
    try:
        # 親ディレクトリのUserDataフォルダからsetting.jsonを探す
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(parent_dir, "UserData", "setting.json")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")
        # 設定の読み込みに失敗した場合は空の辞書を返す
        return {}
