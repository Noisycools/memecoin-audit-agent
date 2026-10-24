from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import delete, desc, select
from backend.db.session import AsyncSessionFactory

from backend.db.models import (
    AlertModel,
    FlagModel,
    ScoreModel,
    SnapshotModel,
    TokenModel,
    WatchlistModel,
)
from backend.schemas.token_report import TokenAuditReport


class PreviousSnapshotDelta(BaseModel):
    is_new_token: bool = True
    verdict_changed: bool = False
    previous_verdict: str | None = None
    previous_liquidity_usd: float | None = None
    liquidity_change_pct: float | None = None
    previous_top10_pct: float | None = None
    authority_changed: bool = False


class TokenFilterParams(BaseModel):
    verdict: str | None = None
    chain: str | None = None
    min_liquidity_usd: float | None = None
    min_age_minutes: int | None = None
    max_age_minutes: int | None = None
    hide_critical: bool = False
    limit: int = 100


class WatchlistItemRecord(BaseModel):
    chain: str
    address: str
    symbol: str
    name: str
    added_at: str
    alert_on_verdict_change: bool = True
    alert_liquidity_drop_pct: float = 20.0
    alert_on_top_holder_sell: bool = True
    alert_on_authority_change: bool = True
    latest_report: TokenAuditReport | None = None


class AlertRecord(BaseModel):
    id: int | None = None
    chain: str
    address: str
    symbol: str
    alert_type: str
    severity: str
    message_id: str
    created_at: str
    acknowledged: bool = False


class TokenDetailView(BaseModel):
    report: TokenAuditReport
    verdict_changed: bool = False
    previous_verdict: str | None = None
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    is_watchlisted: bool = False


class AuditRepository:
    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self.session_factory = session_factory

    async def save_audit_report(self, report: TokenAuditReport) -> PreviousSnapshotDelta:
        report_json_str = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
        has_crit = any(f.severity == "critical" for f in report.flags)

        async with self.session_factory() as session:
            stmt = select(TokenModel).where(
                TokenModel.chain == report.token.chain,
                TokenModel.address == report.token.address,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()

            delta = PreviousSnapshotDelta()
            if existing is None:
                token_row = TokenModel(
                    chain=report.token.chain,
                    address=report.token.address,
                    symbol=report.token.symbol,
                    name=report.token.name,
                    logo_url=report.token.logo_url,
                    latest_scanned_at=report.scanned_at,
                    latest_risk_score=report.risk_score,
                    latest_verdict=report.verdict,
                    previous_verdict=None,
                    verdict_changed=False,
                    latest_confidence=report.confidence,
                    latest_liquidity_usd=report.market.liquidity_usd,
                    latest_market_cap=report.market.market_cap,
                    latest_volume_24h=report.market.volume_24h,
                    latest_pair_age_minutes=report.market.pair_age_minutes,
                    has_critical_flag=has_crit,
                    latest_report_json=report_json_str,
                )
                session.add(token_row)
                await session.flush()
            else:
                prev_report_dict = json.loads(existing.latest_report_json)
                prev_verdict = existing.latest_verdict
                prev_liq = existing.latest_liquidity_usd
                v_changed = prev_verdict != report.verdict

                liq_change_pct: float | None = None
                if prev_liq and prev_liq > 0 and report.market.liquidity_usd is not None:
                    liq_change_pct = round(
                        ((report.market.liquidity_usd - prev_liq) / prev_liq) * 100.0, 2
                    )

                prev_flags = {
                    f.get("code")
                    for f in prev_report_dict.get("flags", [])
                    if isinstance(f, dict)
                }
                curr_flags = {f.code for f in report.flags}
                auth_codes = {"MINT_AUTHORITY_ACTIVE", "FREEZE_AUTHORITY_ACTIVE"}
                auth_changed = (prev_flags & auth_codes) != (curr_flags & auth_codes)

                delta = PreviousSnapshotDelta(
                    is_new_token=False,
                    verdict_changed=v_changed,
                    previous_verdict=prev_verdict,
                    previous_liquidity_usd=prev_liq,
                    liquidity_change_pct=liq_change_pct,
                    previous_top10_pct=(prev_report_dict.get("holder_metrics") or {}).get("top10_pct_ex_lp"),
                    authority_changed=auth_changed,
                )

                existing.symbol = report.token.symbol
                existing.name = report.token.name
                existing.logo_url = report.token.logo_url or existing.logo_url
                existing.latest_scanned_at = report.scanned_at
                existing.latest_risk_score = report.risk_score
                existing.previous_verdict = prev_verdict if v_changed else existing.previous_verdict
                existing.latest_verdict = report.verdict
                existing.verdict_changed = v_changed
                existing.latest_confidence = report.confidence
                existing.latest_liquidity_usd = report.market.liquidity_usd
                existing.latest_market_cap = report.market.market_cap
                existing.latest_volume_24h = report.market.volume_24h
                existing.latest_pair_age_minutes = report.market.pair_age_minutes
                existing.has_critical_flag = has_crit
                existing.latest_report_json = report_json_str
                token_row = existing

            snap = SnapshotModel(
                token_id=token_row.id,
                scanned_at=report.scanned_at,
                price_usd=report.market.price_usd,
                liquidity_usd=report.market.liquidity_usd,
                market_cap=report.market.market_cap,
                volume_24h=report.market.volume_24h,
                risk_score=report.risk_score,
                verdict=report.verdict,
                report_json=report_json_str,
            )
            session.add(snap)
            await session.flush()

            score_row = ScoreModel(
                snapshot_id=snap.id,
                risk_score=report.risk_score,
                verdict=report.verdict,
                confidence=report.confidence,
                contract_score=report.breakdown.contract,
                holders_score=report.breakdown.holders,
                volume_score=report.breakdown.volume_integrity,
                liquidity_score=report.breakdown.liquidity,
                social_score=report.breakdown.social,
            )
            session.add(score_row)

            for fl in report.flags:
                session.add(
                    FlagModel(
                        snapshot_id=snap.id,
                        category=fl.category,
                        severity=fl.severity,
                        code=fl.code,
                        value_str=str(fl.value) if fl.value is not None else None,
                        threshold_str=str(fl.threshold) if fl.threshold is not None else None,
                        source=fl.source,
                    )
                )

            await session.commit()
            return delta

    async def list_tokens(self, filters: TokenFilterParams | None = None) -> list[TokenAuditReport]:
        f = filters or TokenFilterParams()
        async with self.session_factory() as session:
            stmt = select(TokenModel).order_by(desc(TokenModel.latest_scanned_at))
            if f.verdict:
                stmt = stmt.where(TokenModel.latest_verdict == f.verdict.upper())
            if f.chain:
                stmt = stmt.where(TokenModel.chain == f.chain.lower())
            if f.min_liquidity_usd is not None:
                stmt = stmt.where(TokenModel.latest_liquidity_usd >= f.min_liquidity_usd)
            if f.min_age_minutes is not None:
                stmt = stmt.where(TokenModel.latest_pair_age_minutes >= f.min_age_minutes)
            if f.max_age_minutes is not None:
                stmt = stmt.where(TokenModel.latest_pair_age_minutes <= f.max_age_minutes)
            if f.hide_critical:
                stmt = stmt.where(TokenModel.has_critical_flag.is_(False))
            stmt = stmt.limit(f.limit)

            rows = (await session.execute(stmt)).scalars().all()
            return [
                TokenAuditReport.model_validate(json.loads(r.latest_report_json))
                for r in rows
            ]

    async def list_rescan_candidates(self, limit: int = 25) -> list[tuple[str, str]]:
        async with self.session_factory() as session:
            stmt = (
                select(TokenModel.chain, TokenModel.address)
                .where(TokenModel.latest_verdict.in_(["PROMISING", "WATCH"]))
                .order_by(desc(TokenModel.latest_scanned_at))
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
            wl_stmt = select(WatchlistModel.chain, WatchlistModel.address)
            wl_rows = (await session.execute(wl_stmt)).all()

            seen: set[tuple[str, str]] = set()
            combined: list[tuple[str, str]] = []
            for ch, addr in list(wl_rows) + list(rows):
                key = (ch, addr)
                if key not in seen:
                    seen.add(key)
                    combined.append(key)
            return combined[:limit]

    async def get_recent_snapshots(
        self,
        chain: str,
        address: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            tok_stmt = select(TokenModel.id).where(
                TokenModel.chain == chain.lower(),
                TokenModel.address == address,
            )
            tok_id = (await session.execute(tok_stmt)).scalar_one_or_none()
            if tok_id is None:
                return []
            snap_stmt = (
                select(SnapshotModel)
                .where(SnapshotModel.token_id == tok_id)
                .order_by(desc(SnapshotModel.id))
                .limit(limit)
            )
            snaps = (await session.execute(snap_stmt)).scalars().all()
            return [
                {
                    "scanned_at": s.scanned_at,
                    "price_usd": s.price_usd,
                    "liquidity_usd": s.liquidity_usd,
                    "market_cap": s.market_cap,
                    "volume_24h": s.volume_24h,
                    "risk_score": s.risk_score,
                    "verdict": s.verdict,
                }
                for s in reversed(snaps)
            ]

    async def get_token_detail(self, chain: str, address: str) -> TokenDetailView | None:
        async with self.session_factory() as session:
            stmt = select(TokenModel).where(
                TokenModel.chain == chain.lower(),
                TokenModel.address == address,
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

            wl_stmt = select(WatchlistModel.id).where(
                WatchlistModel.chain == chain.lower(),
                WatchlistModel.address == address,
            )
            is_wl = (await session.execute(wl_stmt)).scalar_one_or_none() is not None

        snaps = await self.get_recent_snapshots(chain, address, limit=30)
        report = TokenAuditReport.model_validate(json.loads(row.latest_report_json))
        return TokenDetailView(
            report=report,
            verdict_changed=row.verdict_changed,
            previous_verdict=row.previous_verdict,
            snapshots=snaps,
            is_watchlisted=is_wl,
        )

    async def add_to_watchlist(
        self,
        chain: str,
        address: str,
        symbol: str = "UNKNOWN",
        name: str = "Unknown Token",
        alert_on_verdict_change: bool = True,
        alert_liquidity_drop_pct: float = 20.0,
        alert_on_top_holder_sell: bool = True,
        alert_on_authority_change: bool = True,
    ) -> WatchlistItemRecord:
        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        async with self.session_factory() as session:
            stmt = select(WatchlistModel).where(
                WatchlistModel.chain == chain.lower(),
                WatchlistModel.address == address,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                wl = WatchlistModel(
                    chain=chain.lower(),
                    address=address,
                    symbol=symbol,
                    name=name,
                    added_at=now_iso,
                    alert_on_verdict_change=alert_on_verdict_change,
                    alert_liquidity_drop_pct=alert_liquidity_drop_pct,
                    alert_on_top_holder_sell=alert_on_top_holder_sell,
                    alert_on_authority_change=alert_on_authority_change,
                )
                session.add(wl)
            else:
                existing.symbol = symbol or existing.symbol
                existing.name = name or existing.name
                existing.alert_on_verdict_change = alert_on_verdict_change
                existing.alert_liquidity_drop_pct = alert_liquidity_drop_pct
                existing.alert_on_top_holder_sell = alert_on_top_holder_sell
                existing.alert_on_authority_change = alert_on_authority_change
                wl = existing
            await session.commit()
            return WatchlistItemRecord(
                chain=wl.chain,
                address=wl.address,
                symbol=wl.symbol,
                name=wl.name,
                added_at=wl.added_at,
                alert_on_verdict_change=wl.alert_on_verdict_change,
                alert_liquidity_drop_pct=wl.alert_liquidity_drop_pct,
                alert_on_top_holder_sell=wl.alert_on_top_holder_sell,
                alert_on_authority_change=wl.alert_on_authority_change,
            )

    async def remove_from_watchlist(self, chain: str, address: str) -> bool:
        async with self.session_factory() as session:
            stmt = delete(WatchlistModel).where(
                WatchlistModel.chain == chain.lower(),
                WatchlistModel.address == address,
            )
            res = await session.execute(stmt)
            await session.commit()
            return (res.rowcount or 0) > 0

    async def get_watchlist_entry(self, chain: str, address: str) -> WatchlistItemRecord | None:
        async with self.session_factory() as session:
            stmt = select(WatchlistModel).where(
                WatchlistModel.chain == chain.lower(),
                WatchlistModel.address == address,
            )
            wl = (await session.execute(stmt)).scalar_one_or_none()
            if wl is None:
                return None
            return WatchlistItemRecord(
                chain=wl.chain,
                address=wl.address,
                symbol=wl.symbol,
                name=wl.name,
                added_at=wl.added_at,
                alert_on_verdict_change=wl.alert_on_verdict_change,
                alert_liquidity_drop_pct=wl.alert_liquidity_drop_pct,
                alert_on_top_holder_sell=wl.alert_on_top_holder_sell,
                alert_on_authority_change=wl.alert_on_authority_change,
            )

    async def list_watchlist(self) -> list[WatchlistItemRecord]:
        async with self.session_factory() as session:
            wl_rows = (
                await session.execute(select(WatchlistModel).order_by(desc(WatchlistModel.added_at)))
            ).scalars().all()
            items: list[WatchlistItemRecord] = []
            for wl in wl_rows:
                tok_stmt = select(TokenModel).where(
                    TokenModel.chain == wl.chain,
                    TokenModel.address == wl.address,
                )
                tok = (await session.execute(tok_stmt)).scalar_one_or_none()
                latest_rep = (
                    TokenAuditReport.model_validate(json.loads(tok.latest_report_json))
                    if tok is not None
                    else None
                )
                items.append(
                    WatchlistItemRecord(
                        chain=wl.chain,
                        address=wl.address,
                        symbol=tok.symbol if tok else wl.symbol,
                        name=tok.name if tok else wl.name,
                        added_at=wl.added_at,
                        alert_on_verdict_change=wl.alert_on_verdict_change,
                        alert_liquidity_drop_pct=wl.alert_liquidity_drop_pct,
                        alert_on_top_holder_sell=wl.alert_on_top_holder_sell,
                        alert_on_authority_change=wl.alert_on_authority_change,
                        latest_report=latest_rep,
                    )
                )
            return items

    async def save_alert(self, alert: AlertRecord) -> AlertRecord:
        async with self.session_factory() as session:
            row = AlertModel(
                chain=alert.chain.lower(),
                address=alert.address,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                severity=alert.severity,
                message_id=alert.message_id,
                created_at=alert.created_at,
                acknowledged=alert.acknowledged,
            )
            session.add(row)
            await session.commit()
            alert.id = row.id
            return alert

    async def list_alerts(self, limit: int = 50) -> list[AlertRecord]:
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(AlertModel).order_by(desc(AlertModel.id)).limit(limit)
                )
            ).scalars().all()
            return [
                AlertRecord(
                    id=r.id,
                    chain=r.chain,
                    address=r.address,
                    symbol=r.symbol,
                    alert_type=r.alert_type,
                    severity=r.severity,
                    message_id=r.message_id,
                    created_at=r.created_at,
                    acknowledged=r.acknowledged,
                )
                for r in rows
            ]
