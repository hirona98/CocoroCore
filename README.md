# CocoroCore

CocoroCore は デスクトップマスコット CocoroAI のバックエンドです

CocoroAI
https://alice-encoder.booth.pm/items/6821221

## フレームワーク
aiavatarkit
https://github.com/uezo/aiavatarkit

## 環境構築手順
```
py -3.10 -m venv venv
.\venv\Scripts\Activate
pip install aiavatar
```

## ビルド方法
`build_config.py` で設定をしたあとに `build_windows.bat` を実行する

## 実行方法
-c オプションで設定ファイルの場所を指定する
```
.\dist\CocoroCore.exe -c ..\CocoroAI\UserData
```
