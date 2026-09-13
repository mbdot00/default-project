"""
perf_tracker.py — Per-strategy performance tracking.
Uses actual deal profit from MT5 (accurate, includes volume).
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json

TERMINAL = r"C:\Program Files\XM Global MT5\terminal64.exe"

ok = mt5.initialize(path=TERMINAL)
if not ok:
    print(json.dumps({"error": f"MT5 init failed: {mt5.last_error()}"}))
    exit(1)

info = mt5.account_info()
result = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "equity": info.equity,
    "balance": info.balance,
    "margin": info.margin,
    "free_margin": info.margin_free,
    "strategies": []
}

# Known strategies
strategies = {
    920902: {"name": "psar_inv_mart", "symbol": "JP225Cash"},
    920903: {"name": "psar_inv_mart_btc", "symbol": "BTCUSD"},
}

# Get deals from last 7 days
deals = mt5.history_deals_get(datetime.now() - timedelta(days=7), datetime.now())

# Get open positions
positions = mt5.positions_get()

for magic, meta in strategies.items():
    strat = {
        "magic": magic,
        "name": meta["name"],
        "symbol": meta["symbol"],
        "open_position": None,
        "stats": {}
    }
    
    # Find open position for this strategy
    for p in positions:
        if p.magic == magic:
            side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            strat["open_position"] = {
                "side": side,
                "volume": p.volume,
                "entry_price": round(p.price_open, 2),
                "current_price": round(p.price_current, 2),
                "pnl": round(p.profit, 2),
                "swap": round(p.swap, 2),
                "ticket": p.ticket
            }
    
    # Calculate stats from actual deal profit
    magic_deals = [d for d in deals if d.magic == magic]
    
    if magic_deals:
        # Sum actual profit from MT5 (includes volume, swap, commission)
        total_profit = sum(d.profit + d.swap + d.commission for d in magic_deals)
        
        # Count winning/losing deals (profit != 0)
        winning = [d for d in magic_deals if (d.profit + d.swap + d.commission) > 0]
        losing = [d for d in magic_deals if (d.profit + d.swap + d.commission) < 0]
        
        # Max drawdown from deal sequence
        peak = 0
        max_dd = 0
        running = 0
        for d in magic_deals:
            running += d.profit + d.swap + d.commission
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd
        
        # Max single deal win/loss
        deal_pnls = [d.profit + d.swap + d.commission for d in magic_deals]
        
        # Current streak
        last_deal_pnl = magic_deals[-1].profit + magic_deals[-1].swap + magic_deals[-1].commission
        streak = "win" if last_deal_pnl > 0 else "loss"
        
        strat["stats"] = {
            "total_deals": len(magic_deals),
            "total_pnl": round(total_profit, 2),
            "avg_pnl": round(total_profit / len(magic_deals), 2) if magic_deals else 0,
            "winning_deals": len(winning),
            "losing_deals": len(losing),
            "win_rate": round(len(winning) / len(magic_deals) * 100, 1) if magic_deals else 0,
            "max_deal_win": round(max(deal_pnls), 2) if deal_pnls else 0,
            "max_deal_loss": round(min(deal_pnls), 2) if deal_pnls else 0,
            "max_drawdown": round(max_dd, 2),
            "current_streak": streak
        }
    else:
        strat["stats"] = {
            "total_deals": 0,
            "total_pnl": 0,
            "avg_pnl": 0,
            "winning_deals": 0,
            "losing_deals": 0,
            "win_rate": 0,
            "max_deal_win": 0,
            "max_deal_loss": 0,
            "max_drawdown": 0,
            "current_streak": "none"
        }
    
    result["strategies"].append(strat)

# Combined
all_deals = [d for d in deals if d.magic in strategies]
if all_deals:
    combined_pnl = sum(d.profit + d.swap + d.commission for d in all_deals)
    combined_wins = len([d for d in all_deals if (d.profit + d.swap + d.commission) > 0])
    result["combined"] = {
        "total_deals": len(all_deals),
        "total_pnl": round(combined_pnl, 2),
        "avg_pnl": round(combined_pnl / len(all_deals), 2),
        "winning_deals": combined_wins,
        "losing_deals": len(all_deals) - combined_wins,
        "win_rate": round(combined_wins / len(all_deals) * 100, 1)
    }
else:
    result["combined"] = {
        "total_deals": 0,
        "total_pnl": 0,
        "avg_pnl": 0,
        "winning_deals": 0,
        "losing_deals": 0,
        "win_rate": 0
    }

mt5.shutdown()

print(json.dumps(result, indent=2))
