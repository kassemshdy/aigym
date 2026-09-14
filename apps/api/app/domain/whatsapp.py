"""Mirrors apps/web/src/lib/whatsapp.ts exactly: no WhatsApp Business API, no
per-message cost, no Meta approval (decision 4). The server composes the
text and hands back a wa.me link; a human at the front desk taps send."""

from urllib.parse import quote


def wa_link(phone: str, message: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(message)}"
