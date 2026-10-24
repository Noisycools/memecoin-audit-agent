import json
import pytest
import httpx
from backend.clients.telegram import TelegramNotifier


@pytest.mark.asyncio
async def test_telegram_notifier_skips_when_unconfigured_and_sends_when_configured():
    unconfigured = TelegramNotifier(bot_token=None, chat_id=None)
    assert await unconfigured.send_message("Test alert") is False

    sent_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent_payload.update(json.loads(request.content.decode()))
        return httpx.Response(200, json={"ok": True})

    configured = TelegramNotifier(
        bot_token="123:ABC",
        chat_id="999",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await configured.send_message("Alert: Verdict berubah") is True
    assert sent_payload["chat_id"] == "999"
