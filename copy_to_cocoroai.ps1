# CocoroCore デプロイスクリプト

Write-Host "CocoroCore デプロイスクリプト" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# デプロイ先のディレクトリ
$destDir = "..\CocoroAI\CocoroCore"

# ソースディレクトリ
$sourceDir = "dist\CocoroCore"

# 存在確認
if (-not (Test-Path $sourceDir)) {
    Write-Host "エラー: $sourceDir が存在しません。" -ForegroundColor Red
    Write-Host "ビルドを実行してください: .\build.bat" -ForegroundColor Yellow
    exit 1
}

# デプロイ先ディレクトリの作成（存在しない場合）
if (-not (Test-Path $destDir)) {
    Write-Host "デプロイ先ディレクトリを作成します: $destDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}

# デプロイ先ディレクトリの内容を削除
Write-Host "`nデプロイ先ディレクトリをクリーンアップしています..." -ForegroundColor Yellow
if (Test-Path "$destDir\*") {
    Remove-Item -Path "$destDir\*" -Recurse -Force -ErrorAction SilentlyContinue
}

# dist\CocoroCore の内容をコピー
Write-Host "`nファイルをコピーしています..." -ForegroundColor Yellow
try {
    Copy-Item -Path "$sourceDir\*" -Destination $destDir -Recurse -Force
    Write-Host "ファイルのコピーが完了しました" -ForegroundColor Green
} catch {
    Write-Host "エラー: ファイルのコピーに失敗しました" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# LICENSE.txt をコピー
if (Test-Path "LICENSE.txt") {
    try {
        Copy-Item -Path "LICENSE.txt" -Destination $destDir -Force
        Write-Host "LICENSE.txt をコピーしました" -ForegroundColor Green
    } catch {
        Write-Host "警告: LICENSE.txt のコピーに失敗しました" -ForegroundColor Yellow
    }
} else {
    Write-Host "警告: LICENSE.txt が見つかりません" -ForegroundColor Yellow
}

Write-Host "`nデプロイが完了しました！" -ForegroundColor Green
Write-Host "デプロイ先: $destDir" -ForegroundColor Cyan

# デプロイ結果の確認
$fileCount = (Get-ChildItem -Path $destDir -Recurse -File).Count
Write-Host "コピーされたファイル数: $fileCount" -ForegroundColor Cyan