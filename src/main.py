import argparse
import time
import traceback
import uvicorn

from cocoro_core import create_app, get_log_config


def main():
    """CocoroCore AI アシスタントサーバーのメインエントリポイント"""
    
    # コマンドライン引数を解析
    parser = argparse.ArgumentParser(description="CocoroCore AI Assistant Server")
    parser.add_argument(
        "folder_path", nargs="?", help="設定ファイルのフォルダパス（省略可）"
    )
    parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
    args = parser.parse_args()

    # フォルダパスが位置引数で渡された場合は--config-dirより優先
    if args.folder_path:
        args.config_dir = args.folder_path

    # アプリケーションを作成
    app, port = create_app(args.config_dir if hasattr(args, "config_dir") else None)

    # 設定情報のログ出力
    print("CocoroCore を起動します")
    print(
        f"設定ディレクトリ: {args.config_dir if hasattr(args, 'config_dir') and args.config_dir else '(デフォルト)'}"
    )
    print(f"使用ポート: {port}")

    # ログ設定を取得
    log_config = get_log_config()

    # サーバー起動
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_config=log_config)
    except Exception as e:
        print(f"サーバー起動エラー: {e}")
        traceback.print_exc()
        try:
            input("Enterキーを押すと終了します...")
        except RuntimeError:
            # EXE実行時にsys.stdinが利用できない場合
            print("5秒後に自動終了します...")
            time.sleep(5)


if __name__ == "__main__":
    main()
