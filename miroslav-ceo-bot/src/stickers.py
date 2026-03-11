def sticker_to_text(sticker) -> str:
    emoji = getattr(sticker, "emoji", None)
    if emoji:
        return f"[стикер: {emoji}]"
    return "[стикер: неизвестный]"
