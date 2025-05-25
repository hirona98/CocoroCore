@echo off
chcp 65001 > nul
echo CocoroCore ビルドツール

REM 仮想環境を有効化
echo 仮想環境を有効化しています...
call .\.venv\Scripts\activate

REM Pythonバージョン確認
python -c "import sys; print(f'Python {sys.version}')"

REM 簡略化ビルドスクリプト実行
echo ビルドスクリプトを実行中...
python build_cocoro.py

REM 仮想環境を終了
call deactivate

echo.
echo 処理が完了しました。何かキーを押すと終了します。
pause
