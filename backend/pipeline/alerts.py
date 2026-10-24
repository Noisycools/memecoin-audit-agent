from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from backend.config import AppConfig
from backend.db.repository import AlertRecord, AuditRepository, PreviousSnapshotDelta
from backend.schemas.token_report import TokenAuditReport


async def evaluate_alerts_for_transition(
    repo: AuditRepository,
    report: TokenAuditReport,
    delta: PreviousSnapshotDelta,
    config: AppConfig,
    notifier_cb: Callable[[AlertRecord], Coroutine[Any, Any, Any]] | None = None,
) -> list[AlertRecord]:
    if delta.is_new_token:
        return []

    wl = await repo.get_watchlist_entry(report.token.chain, report.token.address)
    if wl is None:
        return []

    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    triggered: list[AlertRecord] = []

    if wl.alert_on_verdict_change and delta.verdict_changed:
        triggered.append(
            AlertRecord(
                chain=report.token.chain,
                address=report.token.address,
                symbol=report.token.symbol,
                alert_type="VERDICT_CHANGED",
                severity="warn" if report.verdict in ("WATCH", "HIGH RISK") else "critical",
                message_id=(
                    f"Verdict {report.token.symbol} berubah dari {delta.previous_verdict} "
                    f"menjadi {report.verdict} (Skor Risiko: {report.risk_score}/100)."
                ),
                created_at=now_iso,
            )
        )

    if (
        delta.liquidity_change_pct is not None
        and delta.liquidity_change_pct <= -abs(wl.alert_liquidity_drop_pct)
    ):
        triggered.append(
            AlertRecord(
                chain=report.token.chain,
                address=report.token.address,
                symbol=report.token.symbol,
                alert_type="LIQUIDITY_DROP",
                severity="critical",
                message_id=(
                    f"Likuiditas {report.token.symbol} turun {abs(delta.liquidity_change_pct):.1f}% "
                    f"(batas alert: {wl.alert_liquidity_drop_pct:.0f}%)."
                ),
                created_at=now_iso,
            )
        )

    curr_top10 = report.holder_metrics.get("top10_pct_ex_lp")
    if (
        wl.alert_on_top_holder_sell
        and isinstance(delta.previous_top10_pct, (int, float))
        and isinstance(curr_top10, (int, float))
        and (delta.previous_top10_pct - curr_top10) >= 5.0
    ):
        triggered.append(
            AlertRecord(
                chain=report.token.chain,
                address=report.token.address,
                symbol=report.token.symbol,
                alert_type="TOP_HOLDER_SELL",
                severity="warn",
                message_id=(
                    f"Kepemilikan Top 10 {report.token.symbol} turun signifikan dari "
                    f"{delta.previous_top10_pct:.1f}% ke {curr_top10:.1f}%."
                ),
                created_at=now_iso,
            )
        )

    if wl.alert_on_authority_change and delta.authority_changed:
        triggered.append(
            AlertRecord(
                chain=report.token.chain,
                address=report.token.address,
                symbol=report.token.symbol,
                alert_type="AUTHORITY_CHANGED",
                severity="critical",
                message_id=f"Status mint/freeze authority pada kontrak {report.token.symbol} berubah.",
                created_at=now_iso,
            )
        )

    saved_alerts: list[AlertRecord] = []
    for al in triggered:
        saved = await repo.save_alert(al)
        saved_alerts.append(saved)
        if notifier_cb is not None:
            try:
                await notifier_cb(saved)
            except Exception:
                pass

    return saved_alerts
