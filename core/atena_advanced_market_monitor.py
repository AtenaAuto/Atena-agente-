#!/usr/bin/env python3
"""
ATENA Advanced Market Monitor (CLI)

Script avançado para monitoramento de criptoativos:
- coleta cotações em tempo real (CoinGecko)
- calcula EMA por ativo
- calcula volatilidade de retornos
- emite sinal de tendência (BULLISH/BEARISH/NEUTRAL)
"""

from __future__ import annotations

import argparse
import statistics
import time
from dataclasses import dataclass, field

import requests


COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


@dataclass
class AssetState:
    symbol: str
    prices: list[float] = field(default_factory=list)
    ema: float | None = None

    def update(self, price: float, alpha: float) -> None:
        self.prices.append(price)
        self.ema = price if self.ema is None else alpha * price + (1 - alpha) * self.ema

    def volatility(self) -> float:
        if len(self.prices) < 3:
            return 0.0
        returns = []
        for i in range(1, len(self.prices)):
            prev = self.prices[i - 1]
            if prev == 0:
                continue
            returns.append((self.prices[i] - prev) / prev)
        return statistics.stdev(returns) if len(returns) >= 2 else 0.0

    def trend_signal(self, threshold: float = 0.01) -> str:
        if self.ema is None or not self.prices:
            return "N/A"
        current = self.prices[-1]
        delta = (current - self.ema) / self.ema if self.ema else 0.0
        if delta > threshold:
            return "BULLISH"
        if delta < -threshold:
            return "BEARISH"
        return "NEUTRAL"


def fetch_prices(symbols: list[str], vs_currency: str = "usd") -> dict[str, float]:
    params = {"ids": ",".join(symbols), "vs_currencies": vs_currency}
    resp = requests.get(COINGECKO_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return {s: float(data[s][vs_currency]) for s in symbols if s in data and vs_currency in data[s]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="atena_advanced_market_monitor",
        description="Monitor quant com EMA + volatilidade.",
    )
    parser.add_argument("--assets", default="bitcoin,ethereum,solana")
    parser.add_argument("--currency", default="usd")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=0.25)
    return parser.parse_args()


def run_monitor(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.assets.split(",") if s.strip()]
    if not symbols:
        print("❌ Nenhum ativo válido informado.")
        return 2

    states = {s: AssetState(symbol=s) for s in symbols}
    print(f"🚀 Monitor ATENA | ativos={symbols} | currency={args.currency}")
    print("-" * 90)
    print("ativo       preço_atual      ema            volatilidade      sinal")
    print("-" * 90)

    for cycle in range(1, args.cycles + 1):
        try:
            prices = fetch_prices(symbols, vs_currency=args.currency)
        except Exception as exc:
            print(f"⚠️ Falha na coleta ciclo {cycle}/{args.cycles}: {exc}")
            time.sleep(args.interval)
            continue

        for symbol in symbols:
            if symbol not in prices:
                print(f"{symbol:<10} sem_dado")
                continue
            price = prices[symbol]
            state = states[symbol]
            state.update(price, alpha=args.alpha)
            print(
                f"{symbol:<10} {price:<14.4f} {state.ema:<14.4f} "
                f"{state.volatility():<16.6f} {state.trend_signal()}"
            )
        if cycle < args.cycles:
            time.sleep(args.interval)

    print("-" * 90)
    print("✅ Monitoramento concluído.")
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(run_monitor(args))


if __name__ == "__main__":
    main()
