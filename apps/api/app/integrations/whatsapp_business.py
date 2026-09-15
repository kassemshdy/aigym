"""Automated WhatsApp delivery via Meta's Cloud API.

This is decision 20's narrow, documented exception to decision 4 (every
other WhatsApp message in this product is a wa.me link a human taps —
no Business API, no per-message cost, no template approval). It exists
only for POST /auth/staff/pin/reset, where automation is the point: a
staff member locked out of their own login has no front desk to hand a
link to.

Both settings are unset by default. In that state this always returns
False rather than raising — a misconfigured or not-yet-configured
deployment degrades to "no message sent", not a 500.
"""

import httpx

from app.settings import get_settings


async def send_whatsapp_text(*, to: str, body: str) -> bool:
    settings = get_settings()
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        return False

    digits = "".join(ch for ch in to if ch.isdigit())
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": digits,
        "type": "text",
        "text": {"body": body},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError:
        return False

    return response.status_code == 200
