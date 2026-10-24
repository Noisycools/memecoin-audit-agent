from __future__ import annotations

import httpx
from backend.db.repository import AlertRecord


class TelegramNotifier:
    """Optional Telegram alert sender."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._client = http_client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send_message(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            resp = await self._client.post(
                url,
                json={"chat_id": self.chat_id, "text": text},
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False

    async def send_alert(self, alert: AlertRecord) -> bool:
        msg = (
            f"🚨 [MEMECOIN AUDIT ALERT - {alert.severity.upper()}]\n"
            f"Token: ${alert.symbol} ({alert.chain.upper()})\n"
            f"Tipe: {alert.alert_type}\n"
            f"Pesan: {alert.message_id}"
        )
        return await self.send_message(msg)
