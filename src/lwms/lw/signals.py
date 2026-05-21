"""Setup dataclass — the canonical signal shape across LW detectors.

Every detector in this package returns zero or more ``Setup`` instances.
Composition functions (``signals.compose``) take a base setup, run it
through filters and risk math, and either return the enriched setup or
``None`` if any filter rejected it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["BUY", "SELL"]
Pattern = Literal[
    # structure
    "short_term_swing",
    "intermediate_swing",
    "long_term_swing",
    # patterns
    "consecutive_closes",
    "uptrend_pullback",
    "outside_day_down",
    "smash_day",
    "hidden_smash_day",
    # volatility
    "volatility_breakout",
]


@dataclass(slots=True)
class Setup:
    """A single trade setup produced by a Larry Williams detector.

    Fields are populated progressively by composition layers:

    1. The detector populates ``symbol``, ``timeframe``, ``direction``,
       ``pattern``, ``trigger_index``, ``trigger_time``, and at minimum a
       reference price (``trigger_price``).
    2. The volatility layer (when used) sets ``entry`` and ``range_basis``.
    3. The risk layer sets ``sl``, ``tp``, ``rr``, ``volume`` (if sizing is
       requested).
    4. Filters may set ``rejected_by`` and ``rejection_reason`` rather than
       removing the setup entirely.
    """

    symbol: str
    timeframe: str
    direction: Direction
    pattern: Pattern
    trigger_index: int
    trigger_time: int

    # Reference price — usually the close of the trigger bar.
    trigger_price: float

    # Populated by volatility / risk layers (None until set).
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    rr: float | None = None
    volume: float | None = None

    # The "working range" used for projections and stop math.
    # For Smash/Hidden Smash this is the smash bar range; for breakout
    # patterns it's yesterday's range or the swing-based dominant range.
    range_basis: float | None = None

    # Optional metadata.
    confidence: float | None = None
    reason: str = ""

    # Filter outcome.
    rejected_by: str | None = None
    rejection_reason: str | None = None

    extras: dict[str, Any] = field(default_factory=dict)

    def with_(
        self,
        **changes: Any,
    ) -> Setup:
        """Return a copy with the given fields replaced. Useful for
        chaining without mutating the original."""
        from dataclasses import replace

        return replace(self, **changes)

    def is_rejected(self) -> bool:
        return self.rejected_by is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for MCP / JSON consumption."""
        out: dict[str, Any] = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "pattern": self.pattern,
            "trigger_index": self.trigger_index,
            "trigger_time": self.trigger_time,
            "trigger_price": round(self.trigger_price, 5),
        }
        if self.entry is not None:
            out["entry"] = round(self.entry, 5)
        if self.sl is not None:
            out["sl"] = round(self.sl, 5)
        if self.tp is not None:
            out["tp"] = round(self.tp, 5)
        if self.rr is not None:
            out["rr"] = round(self.rr, 4)
        if self.volume is not None:
            out["volume"] = round(self.volume, 4)
        if self.range_basis is not None:
            out["range_basis"] = round(self.range_basis, 5)
        if self.confidence is not None:
            out["confidence"] = round(self.confidence, 4)
        if self.reason:
            out["reason"] = self.reason
        if self.rejected_by is not None:
            out["rejected_by"] = self.rejected_by
            out["rejection_reason"] = self.rejection_reason
        if self.extras:
            out["extras"] = self.extras
        return out
