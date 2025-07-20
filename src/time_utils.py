"""時間関連のユーティリティモジュール"""

import locale
from datetime import datetime, timedelta, timezone


def generate_current_time_info() -> str:
    """現在時刻の情報を生成
    
    Returns:
        現在の日時情報を含む文字列
    """
    # 日本語ロケールの設定（Windows環境対応）
    try:
        locale.setlocale(locale.LC_TIME, "ja_JP.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, "Japanese_Japan.932")
        except locale.Error:
            pass  # ロケール設定に失敗してもフォールバック

    # UTC時間を取得してから日本時間に変換
    now_utc = datetime.now(timezone.utc)
    # 日本時間に変換（UTC+9）
    jst_offset = timezone(timedelta(hours=9))
    now = now_utc.astimezone(jst_offset)
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    weekday_jp = weekdays[now.weekday()]

    # 時間帯の判定
    hour = now.hour
    if 5 <= hour < 12:
        time_period = "朝"
    elif 12 <= hour < 17:
        time_period = "昼"
    elif 17 <= hour < 22:
        time_period = "夕方"
    else:
        time_period = "夜"

    return f"現在の日時: {now.year}年{now.month}月{now.day}日({weekday_jp}) {now.hour}時{now.minute}分 ({time_period})"


def create_time_guidelines() -> str:
    """時間感覚ガイドラインのテキストを生成
    
    Returns:
        システムプロンプトに追加する時間感覚ガイドライン
    """
    return (
        "\n\n時間感覚ガイドライン:\n"
        "- 挨拶は時間帯に応じて自然に変化させてください（朝：おはよう、昼：こんにちは、夕方：お疲れ様、夜：こんばんは）\n"
        "- 時間の経過を意識した会話を心がけてください\n"
        "- 時間に関する質問には、現在時刻の情報を活用して答えてください\n"
        "- 現在時刻はリクエスト処理時に動的に提供されます\n"
    )