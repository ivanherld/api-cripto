# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dependencies** (from project root `Api - finanzas/`):
```bash
pip install -r requirements.txt
```

**Run the API** (from project root):
```bash
    uvicorn api.main:app --reload 
  


```

The API is available at `http://localhost:8000`. Interactive docs at `/docs`, health check at `/health`.

## Architecture

Layered FastAPI application for cryptocurrency technical analysis. Data is fetched live from Binance via CCXT on every request — there is no database or caching.

```
routers/ → services/ → engine/ → (Binance via CCXT)
```

- **`routers/`** — HTTP endpoints; validates input, delegates to services, returns Pydantic-serialized responses.
- **`schemas/`** — Pydantic v2 models for all request/response shapes.
- **`services/analyzer.py`** — Async wrapper: runs the synchronous engine functions in a thread pool via `run_in_executor` so they don't block the FastAPI event loop.
- **`engine/crypto_analyzer.py`** — 2200+ line synchronous analysis engine. All technical indicator logic, pattern detection, and market regime calculations live here. Uses CCXT to fetch OHLCV candles from Binance and Pandas/Pandas-TA to compute indicators.
- **`core/config.py`** — Pydantic-Settings configuration. Reads from `.env` if present. Defines supported symbols (BTC/ETH/BNB/SOL/XRP/ADA mapped to USDT pairs) and timeframes grouped by strategy (scalping: 5m/15m, swing: 1h/4h, position: 1d/1w).

## Key Design Points

- **No API key required**: Binance public endpoints only.
- **Stateless**: Every request fetches fresh data; no session or cross-request state.
- **Sync engine in async app**: Any new engine code must remain synchronous; call it through `run_in_executor` in services.
- **Spanish naming**: Comments and some variable names are in Spanish — maintain that convention when editing engine code.
- **CORS**: Configured for `localhost:3000` and `localhost:5173` (frontend dev servers).
