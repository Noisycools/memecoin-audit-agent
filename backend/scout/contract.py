from __future__ import annotations

from backend.adapters.base import EnrichedTokenData
from backend.config import AppConfig
from backend.schemas.token_report import ScoutFlag


def evaluate_contract(
    data: EnrichedTokenData,
    config: AppConfig,
) -> tuple[list[ScoutFlag], int, int]:
    flags: list[ScoutFlag] = []
    rug = data.rugcheck
    ct = config.thresholds.contract

    if rug is None:
        return flags, 5, 5

    evaluated = 5
    unknown = 0

    # 1. Mint authority active
    if rug.mint_authority:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="MINT_AUTHORITY_ACTIVE",
                value=rug.mint_authority,
                threshold=None,
                source="rugcheck",
                detail_id="Mint authority masih aktif; suplai token baru dapat dicetak kapan saja.",
            )
        )

    # 2. Freeze authority active
    if rug.freeze_authority:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="FREEZE_AUTHORITY_ACTIVE",
                value=rug.freeze_authority,
                threshold=None,
                source="rugcheck",
                detail_id="Freeze authority masih aktif; wallet pembeli dapat dibekukan.",
            )
        )

    # 3. Token-2022 extensions / mutable metadata
    if rug.permanent_delegate:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="DANGEROUS_TOKEN_EXTENSION",
                value="PermanentDelegate",
                threshold=None,
                source="rugcheck",
                detail_id="Ekstensi PermanentDelegate aktif; token pengguna dapat dipindahkan paksa.",
            )
        )
    elif rug.transfer_fee_bps is not None and rug.transfer_fee_bps > ct.max_transfer_fee_warn_bps:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="DANGEROUS_TOKEN_EXTENSION",
                value=rug.transfer_fee_bps,
                threshold=ct.max_transfer_fee_warn_bps,
                source="rugcheck",
                detail_id=f"Pajak transfer Token-2022 tinggi ({rug.transfer_fee_bps / 100:.1f}%).",
            )
        )
    elif rug.mutable_metadata is True:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="warn",
                code="MUTABLE_METADATA",
                value=True,
                threshold=False,
                source="rugcheck",
                detail_id="Metadata token masih dapat diubah oleh pemilik kontrak.",
            )
        )

    # 4. LP lock / burn status
    if rug.lp_locked_pct is None:
        unknown += 1
    elif rug.lp_locked_pct < 10.0:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="LP_UNLOCKED_OR_SHORT",
                value=rug.lp_locked_pct,
                threshold=ct.lp_locked_min_pct,
                source="rugcheck",
                detail_id=f"Likuiditas (LP) tidak dikunci ({rug.lp_locked_pct:.1f}% terkunci).",
            )
        )
    elif rug.lp_locked_pct < ct.lp_locked_min_pct:
        flags.append(
            ScoutFlag(
                category="contract",
                severity="warn",
                code="LP_UNLOCKED_OR_SHORT",
                value=rug.lp_locked_pct,
                threshold=ct.lp_locked_min_pct,
                source="rugcheck",
                detail_id=f"Porsi likuiditas terkunci di bawah standar ({rug.lp_locked_pct:.1f}% < {ct.lp_locked_min_pct:.0f}%).",
            )
        )

    # 5. RugCheck rugged flag or danger risk level
    danger_risks = [r for r in rug.risks if r.level == "danger"]
    if rug.rugged or danger_risks:
        reason_name = "Token ditandai RUGGED" if rug.rugged else danger_risks[0].name
        flags.append(
            ScoutFlag(
                category="contract",
                severity="critical",
                code="RUGCHECK_DANGER_OR_RUGGED",
                value=reason_name,
                threshold="none",
                source="rugcheck",
                detail_id=f"Bahaya kritis dari RugCheck: {reason_name}.",
            )
        )

    return flags, evaluated, unknown
