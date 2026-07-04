from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAIMS_CONFIG = ROOT / "config" / "public_claims.yml"


def _section_text(text: str, section: str) -> str:
    start = text.index(f"{section}:")
    next_starts = [
        text.index(f"\n{name}:")
        for name in [
            "product_positioning",
            "allowed_public_claims",
            "required_boundary_claims",
            "blocked_public_claims",
            "public_payload_forbidden",
            "handling_policy",
        ]
        if f"\n{name}:" in text and text.index(f"\n{name}:") > start
    ]
    end = min(next_starts) if next_starts else len(text)
    return text[start:end]


def test_public_claims_config_exists_and_freezes_positioning():
    text = CLAIMS_CONFIG.read_text(encoding="utf-8")

    assert "version: gotra.public_claims.v1" in text
    assert "可审计 AI 金融研究发布账本" in text
    assert "Auditable AI financial research publication ledger" in text
    assert "Alaya 仅指 repo 内部" in text


def test_public_claims_allowlist_does_not_promote_trading_or_performance_claims():
    text = CLAIMS_CONFIG.read_text(encoding="utf-8")
    allowed = _section_text(text, "allowed_public_claims")

    forbidden_fragments = [
        "荐股",
        "交易信号",
        "买入建议",
        "卖出建议",
        "目标价",
        "仓位建议",
        "收益承诺",
        "稳定 alpha",
        "自动交易",
        "hedge fund",
        "业绩证明",
        "科学或公共有效性证明",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in allowed


def test_public_claims_blocklist_and_boundary_cover_stage_zero_terms():
    text = CLAIMS_CONFIG.read_text(encoding="utf-8")
    blocked = _section_text(text, "blocked_public_claims")
    boundary = _section_text(text, "required_boundary_claims")

    for fragment in ["荐股", "交易信号", "买入建议", "目标价", "收益承诺", "自动交易", "AI hedge fund"]:
        assert fragment in blocked

    for fragment in ["不是投资建议", "不是交易信号", "不提供目标价", "不承诺收益"]:
        assert fragment in boundary


def test_public_claims_forbid_secrets_and_raw_provider_io_in_public_payloads():
    text = CLAIMS_CONFIG.read_text(encoding="utf-8")
    public_payload_forbidden = _section_text(text, "public_payload_forbidden")

    for fragment in ["API key", "Authorization", "Bearer token", "raw provider I/O", "完整内部 prompt", "私有路径"]:
        assert fragment in public_payload_forbidden
