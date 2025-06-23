# CocoroCore

CocoroCore は デスクトップマスコット CocoroAI のバックエンドです

CocoroAI: https://alice-encoder.booth.pm/items/6821221

いろいろテキトーです

あまり人に見せるように作ってなくてすみません

----

全体構成は CocoroAI全体構成.drawio を参照

## フレームワーク
aiavatarkit
https://github.com/uezo/aiavatarkit

## 環境構築手順
```
py -3.10 -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

## ビルド方法

```bash
build.bat  # または python build_cocoro.py
```

ビルドが成功すると `dist/CocoroCore.exe` が生成されます。

## 実行方法

```bash
# 基本実行
.\dist\CocoroCore.exe

# 設定ディレクトリ指定(例)
.\dist\CocoroCore.exe -c ..\CocoroAI\UserData
```
