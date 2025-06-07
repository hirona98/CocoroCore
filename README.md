# CocoroCore

CocoroCore は デスクトップマスコット CocoroAI のバックエンドです

CocoroAI
https://alice-encoder.booth.pm/items/6821221

----

AIの進化に合わせてそのうち作り直すと思うので、かな～り雑に作ってます

Python良く知らないので、おかしな部分もあると思います

プルリクしたい場合はお気軽にどうぞ！

全体構成は CocoroAI全体構成.drawio を参照
----

## フレームワーク
aiavatarkit
https://github.com/uezo/aiavatarkit

## 環境構築手順
```
py -3.10 -m venv .venv
.\.venv\Scripts\Activate
pip install aiavatar
```

## ビルド方法

同梱の `build_simple.bat` を実行します。
これにより次の処理が行われます:
 - 仮想環境の有効化
 - PyInstallerの確認とインストール
 - PyInstallerによるバイナリのビルド

ビルドが成功すると以下のファイルが生成されます:
 - `dist/CocoroCore.exe`: 実行可能ファイル

## 実行方法
-c オプションで設定ファイルの場所を指定する
```
.\dist\CocoroCore.exe -c ..\CocoroAI\UserData
```

## トラブルシューティング

ビルドに失敗した場合:

1. 仮想環境が正しく作成されているか確認
2. コンソールオプションを有効にしてエラーメッセージを確認 (`console: True`)
