# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CocoroCore is the backend server for CocoroAI, a desktop mascot application. It uses AIAvatarKit (v0.7.2) to provide AI-based conversational avatar functionality through a FastAPI HTTP server.

## Essential Commands

### Development Setup
本プロジェクトは、Windowsを対象にしているが、コードの編集はWSL経由で君に手伝ってもらっている。
参考までに、Windows上でのセットアップ方法を記載する。
君が powershell 経由で起動してもいいよ。

```powershell
# Create and activate virtual environment (PowerShell)
py -3.10 -m venv .venv
.\.venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt
```

### Build and Run
```powershell
# Build standalone executable
.\build.bat

# Run with config directory
.\dist\CocoroCore.exe -c ..\CocoroAI\UserData

# Development run
python src/main.py -c ../CocoroAI/UserData

# Deploy to CocoroAI
.\copy_to_cocoroai.ps1
```

### Code Quality
```powershell
# Format and lint with Ruff
ruff format .
ruff check . --fix

## Architecture

The application follows a Speech-to-Speech (STS) pipeline architecture:

1. **HTTP API Layer** (`cocoro_core.py`): FastAPI server exposing endpoints for the desktop app
2. **Configuration** (`config_loader.py`): Loads settings from `setting.json` in UserData directory
3. **LLM Integration**: Uses LiteLLM to support 100+ AI models (OpenAI, Anthropic, Google, etc.)
4. **Dummy Components** (`dummy_db.py`): Lightweight implementations to avoid unnecessary file creation

Key design decisions:
- Default port: 55601 (configurable)
- Uses AIAvatarKit's ChatMemory for conversation context
- Implements custom logging to reduce console noise
- Build process creates Windows executable using PyInstaller
- Asyncio-based concurrent processing with proper signal handling

## Important Notes

- Always use PowerShell for development commands
- Virtual environment should be `.venv` (not `venv`)
- The codebase is intentionally "rough" and will be rewritten as AI technology evolves
- When modifying build process, update both `build.bat` and `build_cocoro.py`
- Build outputs a folder (`dist/CocoroCore/`), not a single executable

## ユーザーとのコミュニケーション

ユーザーとは日本語でコミュニケーションを取ること
コメントの言語は日本語にすること
