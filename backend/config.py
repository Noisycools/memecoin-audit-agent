from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_THRESHOLDS_PATH = ROOT_DIR / "config" / "thresholds.yaml"
DEFAULT_WEIGHTS_PATH = ROOT_DIR / "config" / "weights.yaml"


class PrefilterThresholds(BaseModel):
    min_liquidity_usd: float = 5000.0
    min_pair_age_minutes: int = 5
    max_pair_age_minutes: int = 10080


class WashTradeThresholds(BaseModel):
    vol_liq_warn: float = 50.0
    vol_liq_critical: float = 200.0
    uniform_txns_min_h1: int = 200
    uniform_buy_ratio_low: float = 0.48
    uniform_buy_ratio_high: float = 0.52
    flat_price_min_txns_m5: int = 100
    flat_price_min_txns_h1: int = 400
    flat_price_max_change_m5_pct: float = 1.0
    flat_price_max_change_h1_pct: float = 2.0
    vol_spike_multiplier: float = 3.0


class HoldersThresholds(BaseModel):
    top10_warn: float = 0.30
    top10_critical: float = 0.50
    top1_warn: float = 0.10
    top1_critical: float = 0.15
    insider_cluster_warn: float = 0.10
    insider_cluster_critical: float = 0.25
    creator_holdings_warn: float = 0.05


class ContractThresholds(BaseModel):
    lp_locked_min_pct: float = 80.0
    max_transfer_fee_warn_bps: int = 500


class VerdictRulesThresholds(BaseModel):
    promising_min_liquidity_usd: float = 25000.0
    low_confidence_unknown_ratio: float = 0.30
    medium_confidence_unknown_ratio: float = 0.10


class ScannerConfig(BaseModel):
    discovery_interval_seconds: int = 60
    rescan_interval_seconds: int = 180
    max_concurrency: int = 5
    active_chains: list[str] = Field(default_factory=lambda: ["solana"])


class ThresholdsConfig(BaseModel):
    prefilter: PrefilterThresholds = Field(default_factory=PrefilterThresholds)
    wash_trade: WashTradeThresholds = Field(default_factory=WashTradeThresholds)
    holders: HoldersThresholds = Field(default_factory=HoldersThresholds)
    contract: ContractThresholds = Field(default_factory=ContractThresholds)
    verdict_rules: VerdictRulesThresholds = Field(default_factory=VerdictRulesThresholds)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)


class WeightsConfig(BaseModel):
    contract: int = 30
    holders: int = 25
    volume_integrity: int = 20
    liquidity: int = 15
    social: int = 10


class AIConfig(BaseModel):
    base_url: str = Field(
        default_factory=lambda: os.getenv("NINEROUTER_BASE_URL", "http://localhost:20128/v1")
    )
    model: str = Field(
        default_factory=lambda: os.getenv("NINEROUTER_MODEL", "gemini-3.8-flash-high")
    )
    api_key: str = Field(
        default_factory=lambda: os.getenv("NINEROUTER_API_KEY", "local-9router")
    )
    timeout_seconds: float = 25.0


class AppConfig(BaseModel):
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    weights: WeightsConfig = Field(default_factory=WeightsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    host: str = Field(default_factory=lambda: os.getenv("BACKEND_HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8004")))
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{ROOT_DIR / 'memecoin_audit.db'}")
    )
    rugcheck_api_key: str | None = Field(
        default_factory=lambda: os.getenv("RUGCHECK_API_KEY") or None
    )
    solana_rpc_url: str | None = Field(
        default_factory=lambda: os.getenv("SOLANA_RPC_URL")
        or (
            f"https://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_API_KEY')}"
            if os.getenv("HELIUS_API_KEY")
            else None
        )
    )
    telegram_bot_token: str | None = Field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN") or None
    )
    telegram_chat_id: str | None = Field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID") or None
    )


def load_config(
    thresholds_path: Path | None = None,
    weights_path: Path | None = None,
) -> AppConfig:
    t_path = thresholds_path or DEFAULT_THRESHOLDS_PATH
    w_path = weights_path or DEFAULT_WEIGHTS_PATH

    t_data: dict[str, Any] = {}
    if t_path.exists():
        with t_path.open("r", encoding="utf-8") as fh:
            t_data = yaml.safe_load(fh) or {}

    w_data: dict[str, Any] = {}
    if w_path.exists():
        with w_path.open("r", encoding="utf-8") as fh:
            w_data = yaml.safe_load(fh) or {}

    return AppConfig(
        thresholds=ThresholdsConfig.model_validate(t_data),
        weights=WeightsConfig.model_validate(w_data),
    )


def save_config(
    config: AppConfig,
    thresholds_path: Path | None = None,
    weights_path: Path | None = None,
) -> None:
    t_path = thresholds_path or DEFAULT_THRESHOLDS_PATH
    w_path = weights_path or DEFAULT_WEIGHTS_PATH
    t_path.parent.mkdir(parents=True, exist_ok=True)
    w_path.parent.mkdir(parents=True, exist_ok=True)
    with t_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config.thresholds.model_dump(mode="json"), fh, sort_keys=False)
    with w_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config.weights.model_dump(mode="json"), fh, sort_keys=False)
