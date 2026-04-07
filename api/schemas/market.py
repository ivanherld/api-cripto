from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# OHLCV
# ─────────────────────────────────────────────

class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class OHLCVResponse(BaseModel):
    symbol: str
    timeframe: str
    limit: int
    candles: list[Candle]


# ─────────────────────────────────────────────
# RÉGIMEN DE MERCADO
# ─────────────────────────────────────────────

class Voto(BaseModel):
    resultado: str  # BULL | BEAR | NEUTRAL | N/A
    detalle: str


class SenialCambioRegimen(BaseModel):
    senial: str = Field(..., alias="señal")
    titulo: str
    detalle: str
    fuente: str

    model_config = {"populate_by_name": True}


class RegimenResponse(BaseModel):
    symbol: str
    regimen: str           # BULL | BEAR | LATERAL | INDEFINIDO
    score: int
    score_anterior: int
    votos: dict[str, Voto]
    cambio: Optional[str]
    senial_cambio: Optional[SenialCambioRegimen] = Field(None, alias="señal_cambio")
    precio_diario: float
    ema200: Optional[float]

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────
# CONTEXTO MACRO BTC
# ─────────────────────────────────────────────

class MacroResponse(BaseModel):
    symbol: str
    aplica: bool
    dias_desde_halving: Optional[int] = None
    dias_para_halving: Optional[int] = None
    porcentaje_ciclo: Optional[float] = None
    fase: Optional[str] = None
    recompensa_bloque: Optional[float] = None
    s2f_aproximado: Optional[float] = None
    num_halvings: Optional[int] = None


# ─────────────────────────────────────────────
# SEÑALES DE INDICADORES
# ─────────────────────────────────────────────

class Senial(BaseModel):
    senial: str        # BUY | SELL | --
    descripcion: str
    fuente: str


class PatronVela(BaseModel):
    patron: str
    senial: str
    fuerza: str
    fuente: str


class PatronChartista(BaseModel):
    nombre: str
    senial: str
    objetivo: Optional[float] = None
    nota: Optional[str] = None
    fuente: str


class PatronArmonico(BaseModel):
    patron: str
    senial: str
    punto_d: Optional[float] = None
    fuente: str


class SenialVolumen(BaseModel):
    tipo: str = ""
    senial: str
    fuerza: str = ""
    descripcion: str
    fuente: str


class Divergencia(BaseModel):
    senial: str
    descripcion: str
    fuente: str


# ─────────────────────────────────────────────
# FIBONACCI
# ─────────────────────────────────────────────

class FibonacciResponse(BaseModel):
    swing_high: float
    swing_low: float
    swing_alcista: bool
    precio_actual: float
    retrocesos: dict[str, float]
    proyecciones: dict[str, float]
    nivel_cercano: Optional[float] = None
    distancia_pct: Optional[float] = None


# ─────────────────────────────────────────────
# STOP LOSS / TAKE PROFIT
# ─────────────────────────────────────────────

class SLTP(BaseModel):
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    multiplicador: float


# ─────────────────────────────────────────────
# ANÁLISIS COMPLETO
# ─────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    precio: float
    regimen: str
    score: int
    direccion: str          # BUY | SELL | NEUTRO
    indicadores: list[Senial]
    velas_japonesas: list[PatronVela]
    chartismo: list[PatronChartista]
    volumen: list[SenialVolumen]
    divergencias: list[Divergencia]
    armonicos: list[PatronArmonico]
    fibonacci: Optional[FibonacciResponse]
    sl_tp: Optional[SLTP]
    timestamp: datetime


# ─────────────────────────────────────────────
# METADATOS / CATÁLOGO
# ─────────────────────────────────────────────

class SymbolInfo(BaseModel):
    ticker: str
    pair: str


class SymbolsResponse(BaseModel):
    symbols: list[SymbolInfo]


class TimeframesResponse(BaseModel):
    timeframes: dict[str, list[str]]
