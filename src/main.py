import argparse
import asyncio
import signal
import sys
import time
import traceback

import uvicorn

from cocoro_core import create_app, get_log_config


# シャットダウンフラグ
shutdown_event = asyncio.Event()


def signal_handler(signum, frame):
    """シグナルハンドラー"""
    print(f"\nシグナル {signum} を受信しました。サーバーを終了します...")
    shutdown_event.set()


def main():
    """CocoroCore AI アシスタントサーバーのメインエントリポイント"""
    # シグナルハンドラーを設定
    if sys.platform == "win32":
        # Windowsの場合、SIGTERMはサポートされていないため、SIGINTとSIGBREAKを使用
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGBREAK, signal_handler)
    else:
        # Unix系の場合
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    # コマンドライン引数を解析
    parser = argparse.ArgumentParser(description="CocoroCore AI Assistant Server")
    parser.add_argument("folder_path", nargs="?", help="設定ファイルのフォルダパス（省略可）")
    parser.add_argument("--config-dir", "-c", help="設定ファイルのディレクトリパス")
    args = parser.parse_args()

    # フォルダパスが位置引数で渡された場合は--config-dirより優先
    if args.folder_path:
        args.config_dir = args.folder_path

    # アプリケーションを作成
    app, port = create_app(args.config_dir if hasattr(args, "config_dir") else None)

    # 設定情報のログ出力
    print("CocoroCore を起動します")
    config_dir = (
        "(デフォルト)"
        if not hasattr(args, "config_dir") or not args.config_dir
        else args.config_dir
    )
    print(f"設定ディレクトリ: {config_dir}")
    print(f"使用ポート: {port}")

    # ログ設定を取得
    log_config = get_log_config()

    # サーバー起動
    try:
        # Uvicornサーバーの設定
        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_config=log_config, loop="asyncio"
        )
        server = uvicorn.Server(config)

        # 非同期でサーバーを起動
        asyncio.run(run_server(server))

    except Exception as e:
        print(f"サーバー起動エラー: {e}")
        traceback.print_exc()
        try:
            input("Enterキーを押すと終了します...")
        except RuntimeError:
            # EXE実行時にsys.stdinが利用できない場合
            print("5秒後に自動終了します...")
            time.sleep(5)


async def run_server(server):
    """非同期でサーバーを実行し、シャットダウンシグナルを監視"""
    # サーバー起動タスク
    server_task = asyncio.create_task(server.serve())

    # シャットダウンシグナル監視タスク
    shutdown_task = asyncio.create_task(wait_for_shutdown())

    # どちらかのタスクが完了するまで待機
    done, pending = await asyncio.wait(
        {server_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED
    )

    # シャットダウンシグナルを受信した場合
    if shutdown_task in done:
        print("サーバーをシャットダウンしています...")
        server.should_exit = True
        await server_task

    # 残りのタスクをキャンセル
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def wait_for_shutdown():
    """シャットダウンイベントを待機"""
    await shutdown_event.wait()


if __name__ == "__main__":
    main()
