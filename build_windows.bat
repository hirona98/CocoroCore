@echo off
REM ビルドスクリプト実行用バッチファイル
echo CocoroCore Windowsバイナリビルドを開始します

REM 仮想環境を有効化
echo 仮想環境を有効化しています...
call .\venv\Scripts\activate

REM 必要なパッケージがインストールされているか確認
echo 必要なパッケージを確認しています...
python -c "import sys; print(f'Python {sys.version}')"

REM ビルドスクリプトを実行
echo ビルドスクリプトを実行しています...
python build.py

REM 仮想環境を終了
echo 仮想環境を終了しています...
call deactivate

echo 処理が完了しました。何かキーを押すと終了します。
pause
