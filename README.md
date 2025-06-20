# CocoroCore

CocoroCore は デスクトップマスコット CocoroAI のバックエンドです

CocoroAI: https://alice-encoder.booth.pm/items/6821221

## 機能概要

- **LLM との対話処理**: AIAvatarKit をベースにした STS パイプライン
- **記憶機能**: ChatMemory との連携による長期記憶
- **通知処理**: 外部アプリからの通知への感情的な反応
- **REST API 通信**: CocoroDock/CocoroShell との連携

## ドキュメント

- [統一API仕様書](../API_SPECIFICATION_UNIFIED.md) - 全コンポーネントのAPI仕様
- [REST API移行計画書](REST_API_MIGRATION_PLAN.md) - 実装の詳細ガイド
- [CLAUDE.md](CLAUDE.md) - Claude Code 向けガイド

全体構成は CocoroAI全体構成.drawio を参照

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

```bash
build.bat  # または python build_cocoro.py
```

ビルドが成功すると `dist/CocoroCore.exe` が生成されます。

## 実行方法

```bash
# 基本実行
.\dist\CocoroCore.exe

# 設定ディレクトリ指定
.\dist\CocoroCore.exe -c ..\CocoroAI\UserData
```

## ポート構成

- **55601**: CocoroCore (HTTP/SSE)
- **55602**: ChatMemory
- **55604**: Notification API
- **55600**: CocoroDock
- **55605**: CocoroShell

## 設定項目

### 必須設定 (setting.json)

```json
{
  "characterList": [{
    "apiKey": "LLM APIキー",
    "llmModel": "LLMモデル名",
    "isEnableMemory": true,
    "voiceSpeakerId": 1,
    "voiceSpeed": 1.0,
    "voicePitch": 0.0,
    "voiceVolume": 1.0,
    "isUseSTT": false,
    "sttWakeWord": "リスティ",
    "sttApiKey": "AmiVoice APIキー"
  }],
  "currentCharacterIndex": 0,
  "cocoroCorePort": 55601,
  "cocoroDockPort": 55600,
  "cocoroShellPort": 55605,
  "cocoroMemoryPort": 55602,
  "enableCocoroDock": true,
  "enableCocoroShell": true,
  略
}
```

### 音声認識（STT）設定

音声認識機能を有効にするには、キャラクター設定に以下のフィールドを追加します：

- **isUseSTT**: 音声認識機能の有効/無効（デフォルト: false）
- **sttWakeWord**: ウェイクワード（音声認識を開始するキーワード）
- **sttApiKey**: AmiVoice APIキー

#### AmiVoice APIキーの取得方法
1. [AmiVoice Cloud Platform](https://acp.amivoice.com/) にアクセス
2. アカウントを作成してログイン
3. APIキーを発行

#### 音声認識の動作
- **マイクから直接音声入力**: PyAudioを使用してマイクから音声を取得
- **音声アクティビティ検出（VAD）**: 話し始めと終わりを自動検出
- **ウェイクワード対応**: 設定されたキーワードで音声認識を開始
- **AmiVoice認識**: 日本語に特化した高精度な音声認識
- 音声記録は `./voice_records` ディレクトリに保存されます（デバッグモード時のみ）

#### 注意事項
- 音声認識を使用するにはマイクデバイスが必要です
- 初回起動時にマイクへのアクセス許可が必要な場合があります
- Windows環境では、デフォルトの録音デバイスが使用されます

## トラブルシューティング

### ビルドエラー
1. Python 3.10 がインストールされているか確認
2. 仮想環境が正しく作成されているか確認
3. `requirements.txt` の依存関係を確認

### 実行時エラー
1. ポートが使用中でないか確認
2. 設定ファイル (setting.json) が存在するか確認
3. LLM APIキーが正しく設定されているか確認

## コントリビュート

プルリクエストは歓迎です！お気軽にどうぞ。

## ライセンス

[LICENSE.txt](LICENSE.txt) を参照してください。
