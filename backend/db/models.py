from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TokenModel(Base):
    __tablename__ = "tokens"
    __table_args__ = (UniqueConstraint("chain", "address", name="uq_token_chain_address"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    latest_scanned_at: Mapped[str] = mapped_column(String(64), index=True)
    latest_risk_score: Mapped[int] = mapped_column(Integer, index=True)
    latest_verdict: Mapped[str] = mapped_column(String(32), index=True)
    previous_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verdict_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    latest_confidence: Mapped[str] = mapped_column(String(16), default="high")
    latest_liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    latest_market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_pair_age_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_critical_flag: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    latest_report_json: Mapped[str] = mapped_column(Text)


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"), index=True)
    scanned_at: Mapped[str] = mapped_column(String(64), index=True)
    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(32))
    report_json: Mapped[str] = mapped_column(Text)


class ScoreModel(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[str] = mapped_column(String(16))
    contract_score: Mapped[int] = mapped_column(Integer)
    holders_score: Mapped[int] = mapped_column(Integer)
    volume_score: Mapped[int] = mapped_column(Integer)
    liquidity_score: Mapped[int] = mapped_column(Integer)
    social_score: Mapped[int] = mapped_column(Integer)


class FlagModel(Base):
    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(64))
    value_str: Mapped[str | None] = mapped_column(String(256), nullable=True)
    threshold_str: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source: Mapped[str] = mapped_column(String(64))


class WatchlistModel(Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("chain", "address", name="uq_watchlist_chain_address"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))
    added_at: Mapped[str] = mapped_column(String(64))
    alert_on_verdict_change: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_liquidity_drop_pct: Mapped[float] = mapped_column(Float, default=20.0)
    alert_on_top_holder_sell: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_authority_change: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertModel(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    message_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
