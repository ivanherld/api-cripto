"""
Wrapper asíncrono sobre crypto_analyzer.py.

Las funciones del motor son síncronas (ccxt + pandas); las ejecutamos en
un thread pool para no bloquear el event loop de FastAPI.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial
from typing import Any, Optional

import pandas as pd

import api.engine.crypto_analyzer as ca

from api.schemas.market import (
    AnalysisResponse,
    Candle,
    Divergencia,
    FibonacciResponse,
    MacroResponse,
    OHLCVResponse,
    PatronArmonico,
    PatronChartista,
    PatronVela,
    RegimenResponse,
    Senial,
    SenialVolumen,
    SLTP,
    Voto,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _run_sync(fn, *args, **kwargs):
    """Ejecuta una función síncrona en el thread pool por defecto del loop."""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, partial(fn, *args, **kwargs))


def _to_candles(df: pd.DataFrame) -> list[Candle]:
    candles = []
    for ts, row in df.iterrows():
        candles.append(Candle(
            timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        ))
    return candles


def _parse_regimen(symbol: str, data: dict) -> RegimenResponse:
    votos: dict[str, Voto] = {}
    for indicador, valor in data.get("votos", {}).items():
        resultado, detalle = valor
        votos[indicador] = Voto(resultado=resultado, detalle=detalle)

    raw_sc = data.get("señal_cambio")
    senial_cambio = None
    if raw_sc:
        senial_cambio = {
            "señal": raw_sc.get("señal", "--"),
            "titulo": raw_sc.get("titulo", ""),
            "detalle": raw_sc.get("detalle", ""),
            "fuente": raw_sc.get("fuente", ""),
        }

    return RegimenResponse(
        symbol=symbol,
        regimen=data.get("regimen", "INDEFINIDO"),
        score=data.get("score", 0),
        score_anterior=data.get("score_anterior", 0),
        votos=votos,
        cambio=data.get("cambio"),
        **{"señal_cambio": senial_cambio},
        precio_diario=float(data.get("precio_diario", 0) or 0),
        ema200=float(data["ema200"]) if data.get("ema200") is not None else None,
    )


def _parse_macro(symbol: str, data: dict) -> MacroResponse:
    if not data:
        return MacroResponse(symbol=symbol, aplica=False)
    return MacroResponse(
        symbol=symbol,
        aplica=True,
        dias_desde_halving=data.get("dias_desde_halving"),
        dias_para_halving=data.get("dias_para_halving"),
        porcentaje_ciclo=data.get("porcentaje_ciclo"),
        fase=data.get("fase"),
        recompensa_bloque=data.get("recompensa_bloque"),
        s2f_aproximado=data.get("s2f_aproximado"),
        num_halvings=data.get("num_halvings"),
    )


def _parse_indicadores(raw: list[tuple[str, str, str]]) -> list[Senial]:
    return [Senial(senial=s, descripcion=d, fuente=f) for s, d, f in raw]


def _parse_velas(raw: list[dict]) -> list[PatronVela]:
    return [
        PatronVela(
            patron=v.get("patron", ""),
            senial=v.get("señal", "--"),
            fuerza=v.get("fuerza", ""),
            fuente=v.get("fuente", ""),
        )
        for v in raw
    ]


def _parse_chartismo(raw: list[dict]) -> list[PatronChartista]:
    result = []
    for p in raw:
        nombre = p.get("patron") or p.get("tipo", "Patrón")
        result.append(PatronChartista(
            nombre=nombre,
            senial=p.get("señal", "--"),
            objetivo=float(p["objetivo"]) if p.get("objetivo") is not None else None,
            nota=p.get("nota"),
            fuente=p.get("fuente", ""),
        ))
    return result


def _parse_volumen(raw: list[dict]) -> list[SenialVolumen]:
    return [
        SenialVolumen(
            tipo=v.get("tipo", ""),
            senial=v.get("señal", "--"),
            fuerza=v.get("fuerza", ""),
            descripcion=v.get("descripcion", v.get("descripción", v.get("detalle", ""))),
            fuente=v.get("fuente", "Murphy 1999"),
        )
        for v in raw
    ]


def _parse_divergencias(raw: list[dict]) -> list[Divergencia]:
    return [
        Divergencia(
            senial=d.get("señal", "--"),
            descripcion=d.get("descripcion", d.get("descripción", d.get("detalle", ""))),
            fuente=d.get("fuente", ""),
        )
        for d in raw
    ]


def _parse_armonicos(raw: list[dict]) -> list[PatronArmonico]:
    return [
        PatronArmonico(
            patron=a.get("patron", ""),
            senial=a.get("señal", "--"),
            punto_d=float(a["punto_d"]) if a.get("punto_d") is not None else None,
            fuente=a.get("fuente", "Sanchez Guillen 2018"),
        )
        for a in raw
    ]


def _parse_fibonacci(raw: Optional[dict]) -> Optional[FibonacciResponse]:
    if not raw:
        return None
    return FibonacciResponse(
        swing_high=float(raw["swing_high"]),
        swing_low=float(raw["swing_low"]),
        swing_alcista=bool(raw.get("swing_alcista", False)),
        precio_actual=float(raw["precio_actual"]),
        retrocesos={k: float(v) for k, v in raw.get("retrocesos", {}).items()},
        proyecciones={k: float(v) for k, v in raw.get("proyecciones", {}).items()},
        nivel_cercano=float(raw["nivel_cercano"]) if raw.get("nivel_cercano") is not None else None,
        distancia_pct=float(raw["distancia_pct"]) if raw.get("distancia_pct") is not None else None,
    )


def _parse_sltp(raw: Optional[dict]) -> Optional[SLTP]:
    if not raw:
        return None
    return SLTP(
        stop_loss=float(raw["stop_loss"]),
        take_profit_1=float(raw["take_profit_1"]),
        take_profit_2=float(raw["take_profit_2"]),
        multiplicador=float(raw["multiplicador"]),
    )


# ─────────────────────────────────────────────
# Servicio público
# ─────────────────────────────────────────────

async def get_ohlcv(symbol: str, timeframe: str, limit: int) -> OHLCVResponse:
    df: Optional[pd.DataFrame] = await _run_sync(ca.obtener_velas, symbol, timeframe, limit)
    if df is None or df.empty:
        raise ValueError(f"No se pudieron obtener velas para {symbol} {timeframe}")
    return OHLCVResponse(
        symbol=symbol,
        timeframe=timeframe,
        limit=len(df),
        candles=_to_candles(df),
    )


async def get_regime(symbol: str) -> RegimenResponse:
    data: dict = await _run_sync(ca.clasificar_regimen, symbol)
    if "error" in data:
        raise ValueError(data["error"])
    return _parse_regimen(symbol, data)


async def get_macro(symbol: str) -> MacroResponse:
    data: dict = await _run_sync(ca.contexto_macro_btc, symbol)
    return _parse_macro(symbol, data)


async def get_analysis(symbol: str, timeframe: str, regimen_override: Optional[str] = None) -> AnalysisResponse:
    """
    Análisis completo de un par en un timeframe.
    Descarga velas, calcula todos los indicadores/patrones y devuelve el resultado.
    Si regimen_override es None, no se filtra por régimen (se muestra todo).
    """
    def _compute():
        df = ca.obtener_velas(symbol, timeframe)
        if df is None or len(df) < 50:
            raise ValueError(f"Datos insuficientes para {symbol} {timeframe}")

        df = ca.calcular_indicadores(df)
        señales_ind  = ca.analizar_indicadores(df, timeframe)
        patrones     = ca.analizar_chartismo(df)
        velas        = ca.detectar_velas_japonesas(df)
        volumen      = ca.analizar_volumen(df)
        divergencias = ca.detectar_divergencias(df)
        armonicos    = ca.detectar_patrones_armonicos(df)
        fib_raw      = ca.calcular_fibonacci(df)
        precio       = float(df["close"].iloc[-1])

        # Score sobre todas las fuentes
        score, direccion = ca.calcular_score(
            señales_ind,
            patrones
            + [{"señal": v["señal"]} for v in velas       if v["señal"] != "--"]
            + [{"señal": vol["señal"]} for vol in volumen  if vol["señal"] != "--"]
            + [{"señal": d["señal"]} for d in divergencias if d["señal"] != "--"]
            + [{"señal": a["señal"]} for a in armonicos    if a["señal"] != "--"],
        )

        sl_tp_raw = ca.calcular_sl_tp(df, direccion, symbol) if direccion in ("BUY", "SELL") else None

        return {
            "df": df,
            "señales_ind": señales_ind,
            "patrones": patrones,
            "velas": velas,
            "volumen": volumen,
            "divergencias": divergencias,
            "armonicos": armonicos,
            "fib_raw": fib_raw,
            "precio": precio,
            "score": score,
            "direccion": direccion,
            "sl_tp_raw": sl_tp_raw,
        }

    result = await _run_sync(_compute)

    regimen = regimen_override or "INDEFINIDO"

    # Enriquecer fib_raw con precio_actual si existe
    fib_raw = result["fib_raw"]
    if fib_raw and "precio_actual" not in fib_raw:
        fib_raw["precio_actual"] = result["precio"]

    return AnalysisResponse(
        symbol=symbol,
        timeframe=timeframe,
        precio=result["precio"],
        regimen=regimen,
        score=result["score"],
        direccion=result["direccion"],
        indicadores=_parse_indicadores(result["señales_ind"]),
        velas_japonesas=_parse_velas(result["velas"]),
        chartismo=_parse_chartismo(result["patrones"]),
        volumen=_parse_volumen(result["volumen"]),
        divergencias=_parse_divergencias(result["divergencias"]),
        armonicos=_parse_armonicos(result["armonicos"]),
        fibonacci=_parse_fibonacci(fib_raw),
        sl_tp=_parse_sltp(result["sl_tp_raw"]),
        timestamp=datetime.now(timezone.utc),
    )
