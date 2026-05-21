"""Backtest Larry Williams Smash Day + Hidden Smash Day on 29 months of XAUUSD data.

Reads M5 candles from ``data/history/xauusd-m5/*.json``, resamples to
H1 / H4 / D1, runs both detectors with default thresholds, and writes
an aggregate JSON report to ``data/backtests/lw-29m-summary.json``.

Run:
    uv run python scripts/backtest_lw.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Ensure src/ is importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lwms.lw import backtest, resample  # noqa: E402

DATA_DIR = ROOT / "data" / "history" / "xauusd-m5"
OUT_DIR = ROOT / "data" / "backtests"
OUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("lw-backtest")


def load_all_m5() -> list[dict[str, Any]]:
    """Load every monthly M5 JSON in chronological order."""
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"no M5 cache files in {DATA_DIR}")
    log.info("loading %d monthly files from %s", len(files), DATA_DIR)
    out: list[dict[str, Any]] = []
    for fp in files:
        rows = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"{fp.name} is not a JSON array")
        out.extend(rows)
    out.sort(key=lambda c: int(c["time"]))
    log.info("total M5 candles: %d", len(out))
    return out


SCENARIOS: list[dict[str, Any]] = [
    {"label": "smash-day-h1-rr3", "fn": "smash", "tf": "H1", "rr": 3.0, "hold": 30},
    {"label": "smash-day-h4-rr3", "fn": "smash", "tf": "H4", "rr": 3.0, "hold": 20},
    {"label": "smash-day-d1-rr3", "fn": "smash", "tf": "D1", "rr": 3.0, "hold": 10},
    {"label": "hidden-smash-h1-rr3", "fn": "hidden", "tf": "H1", "rr": 3.0, "hold": 30},
    {"label": "hidden-smash-h4-rr3", "fn": "hidden", "tf": "H4", "rr": 3.0, "hold": 20},
    {"label": "hidden-smash-d1-rr3", "fn": "hidden", "tf": "D1", "rr": 3.0, "hold": 10},
    # RR=2 sanity passes — smaller targets, expect higher win rate.
    {"label": "smash-day-d1-rr2", "fn": "smash", "tf": "D1", "rr": 2.0, "hold": 10},
    {"label": "hidden-smash-d1-rr2", "fn": "hidden", "tf": "D1", "rr": 2.0, "hold": 10},
]


def main() -> int:
    started = time.perf_counter()
    m5 = load_all_m5()
    log.info(
        "M5 range: %s .. %s",
        time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(m5[0]["time"]))),
        time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(m5[-1]["time"]))),
    )

    by_tf: dict[str, list[dict[str, Any]]] = {}
    for tf in {s["tf"] for s in SCENARIOS}:
        candles = resample.resample(m5, tf)
        log.info("resampled %s: %d bars", tf, len(candles))
        by_tf[tf] = candles

    summaries: list[dict[str, Any]] = []
    for sc in SCENARIOS:
        candles = by_tf[sc["tf"]]
        if sc["fn"] == "smash":
            res = backtest.backtest_smash_day(
                candles,
                label=sc["label"],
                symbol="XAUUSD",
                timeframe=sc["tf"],
                rr=sc["rr"],
                hold_bars=sc["hold"],
            )
        else:
            res = backtest.backtest_hidden_smash_day(
                candles,
                label=sc["label"],
                symbol="XAUUSD",
                timeframe=sc["tf"],
                rr=sc["rr"],
                hold_bars=sc["hold"],
            )
        stats = res.stats()
        log.info(
            "%-22s setups=%-5d trades=%-4d wr=%6.2f%% pf=%6.2f total_r=%+7.2f exp=%+6.3f",
            sc["label"],
            res.setup_count,
            stats["trades"],
            stats["win_rate"] * 100,
            stats["profit_factor"]
            if stats["profit_factor"] != float("inf")
            else -1,
            stats["total_r"],
            stats["expectancy_r"],
        )
        # Per-scenario detailed dump (with trades).
        per_scenario_path = OUT_DIR / f"lw-{sc['label']}.json"
        per_scenario_path.write_text(
            json.dumps(res.to_dict(include_trades=True), indent=2),
            encoding="utf-8",
        )
        summaries.append(res.to_dict(include_trades=False))

    summary_path = OUT_DIR / "lw-29m-summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "generated_at": int(time.time()),
                "symbol": "XAUUSD",
                "source": "data/history/xauusd-m5/*.json",
                "m5_candles": len(m5),
                "m5_first_time": int(m5[0]["time"]),
                "m5_last_time": int(m5[-1]["time"]),
                "scenarios": summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - started
    log.info("wrote %s (%d scenarios) in %.1fs", summary_path, len(summaries), elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
