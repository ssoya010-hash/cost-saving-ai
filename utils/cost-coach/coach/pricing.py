"""Cache-aware pricing for Claude usage records. Stdlib only.

Prices are USD per million tokens (Anthropic list prices, 2026-11). Amazon Bedrock bills Claude
at its own published rates; if your AWS contract differs, override per model in
~/.cost-coach/config.json -> "prices": {"<model substring>": {"in": .., "out": .., "read": ..}}
and/or set "price_multiplier" (e.g. 0.9 for a 10% private-offer discount).

Cache writes: 5-minute TTL = 1.25 x input, 1-hour TTL = 2 x input.
"""

# substring of model id -> (input, output, cache_read) $/MTok. First match wins, so order matters.
LIST_PRICES = [
    ("fable-5-2", (8.0, 40.0, 0.20)),
    ("mythos-5-2", (8.0, 40.0, 0.20)),
    ("fable-5-1", (10.0, 50.0, 1.00)),
    ("fable-5", (10.0, 50.0, 1.00)),
    ("opus-5-5", (4.0, 20.0, 0.20)),
    ("opus-5", (5.0, 25.0, 0.50)),
    ("opus-4-8", (5.0, 25.0, 0.50)),
    ("opus-4-7", (5.0, 25.0, 0.50)),
    ("opus-4-6", (5.0, 25.0, 0.50)),
    ("sonnet-5-5", (2.0, 10.0, 0.10)),
    ("sonnet-5", (2.0, 10.0, 0.20)),
    ("sonnet-4-6", (3.0, 15.0, 0.30)),
    ("sonnet-4", (3.0, 15.0, 0.30)),
    ("haiku-5-5", (0.10, 0.50, 0.01)),
    ("haiku-4-5", (1.0, 5.0, 0.10)),
]
DEFAULT = (4.0, 20.0, 0.20)  # unknown model -> Opus 5.5 rates


def rates(model: str, cfg: dict = None):
    cfg = cfg or {}
    m = (model or "").lower()
    for key, v in (cfg.get("prices") or {}).items():
        if key.lower() in m:
            return (v["in"], v["out"], v.get("read", v["in"] * 0.1))
    for key, v in LIST_PRICES:
        if key in m:
            return v
    return DEFAULT


def cost(usage: dict, model: str, cfg: dict = None) -> dict:
    """Price one API response's `usage` block. Returns a dict of $ parts and token parts."""
    cin, cout, cread = rates(model, cfg)
    mult = float((cfg or {}).get("price_multiplier", 1.0))
    u = usage or {}
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens")
    w5m = cc.get("ephemeral_5m_input_tokens")
    wtotal = u.get("cache_creation_input_tokens", 0) or 0
    if w1h is None and w5m is None:
        w5m, w1h = wtotal, 0
    w1h, w5m = w1h or 0, w5m or 0
    inp = u.get("input_tokens", 0) or 0
    read = u.get("cache_read_input_tokens", 0) or 0
    out = u.get("output_tokens", 0) or 0
    parts = {
        "uncached_in": inp * cin,
        "cache_write": w5m * cin * 1.25 + w1h * cin * 2.0,
        "cache_read": read * cread,
        "output": out * cout,
    }
    parts = {k: v / 1e6 * mult for k, v in parts.items()}
    return {
        "usd": sum(parts.values()), "parts": parts,
        "tokens": {"uncached_in": inp, "cache_write": w5m + w1h, "cache_read": read, "output": out},
        # what the same tokens would cost with no caching (input at full price)
        "usd_no_cache": ((inp + w5m + w1h + read) * cin + out * cout) / 1e6 * mult,
    }
