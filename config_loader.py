import json
import os
import sys
import argparse


def parse_args():
    """
    コマンドライン引数を解析する

    Returns:
        argparse.Namespace: パースされた引数
    """
    parser = argparse.ArgumentParser(description="CocoroCore設定ローダー")
    parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
    return parser.parse_args()


def load_config(custom_config_dir=None):
    """
    setting.jsonファイルから設定を読み込む

    Args:
        custom_config_dir (str, optional): 設定ファイルのディレクトリパス。指定がない場合は自動的に検索する

    Returns:
        dict: 読み込まれた設定データ
    """
    try:
        # カスタムディレクトリが指定されている場合はそれを使用
        if custom_config_dir:
            config_path = os.path.join(custom_config_dir, "setting.json")
        else:
            # 実行ファイルのディレクトリを起点にsetting.jsonを探す
            if getattr(sys, "frozen", False):
                # PyInstallerなどで固められたexeの場合
                base_dir = os.path.dirname(sys.executable)
            else:
                # 通常のPythonスクリプトとして実行された場合
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            config_path = os.path.join(base_dir, "UserData", "setting.json")

            # 基本ディレクトリに設定ファイルがない場合は親ディレクトリを確認
            if not os.path.exists(config_path):
                parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                config_path = os.path.join(parent_dir, "UserData", "setting.json")

                # 親ディレクトリに設定ファイルがない場合は親の親ディレクトリを確認
                if not os.path.exists(config_path):
                    grandparent_dir = os.path.dirname(parent_dir)
                    config_path = os.path.join(
                        grandparent_dir, "UserData", "setting.json"
                    )

        # 設定ファイルが見つからない場合
        if not os.path.exists(config_path):
            print(f"設定ファイルが見つかりません: {config_path}")
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"設定ファイルを読み込みました: {config_path}")
        return config
    except Exception as e:
        print(f"設定ファイルの読み込みに失敗しました: {e}")
        # 設定の読み込みに失敗した場合は空の辞書を返す
        return {}


if __name__ == "__main__":
    # スクリプトとして直接実行された場合、コマンドライン引数を解析して設定を読み込む
    args = parse_args()
    config = load_config(args.config_dir)
    print(json.dumps(config, indent=2, ensure_ascii=False))
