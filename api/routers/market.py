from fastapi import APIRouter, HTTPException, Query

from api.core.config import ALL_TIMEFRAMES, CRYPTOS_DISPONIBLES, TIMEFRAMES, settings
from api.schemas.market import MacroResponse, OHLCVResponse, RegimenResponse, SymbolInfo, SymbolsResponse, TimeframesResponse
from api.services import analyzer

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/symbols", response_model=SymbolsResponse, summary="Lista de criptos disponibles")
async def list_symbols():
    return SymbolsResponse(
        symbols=[SymbolInfo(ticker=ticker, pair=pair) for ticker, pair in CRYPTOS_DISPONIBLES.items()]
    )


@router.get("/timeframes", response_model=TimeframesResponse, summary="Timeframes disponibles por estrategia")
async def list_timeframes():
    return TimeframesResponse(timeframes=TIMEFRAMES)


@router.get(
    "/ohlcv/{symbol}",
    response_model=OHLCVResponse,
    summary="Velas OHLCV",
    description="Descarga velas OHLCV desde Binance vía ccxt.",
)
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe: 5m, 15m, 1h, 4h, 1d, 1w"),
    limit: int = Query(200, ge=10, le=500, description="Número de velas (10-500)"),
):
    symbol_upper = symbol.upper()
    pair = CRYPTOS_DISPONIBLES.get(symbol_upper)
    if not pair:
        raise HTTPException(
            status_code=404,
            detail=f"Símbolo '{symbol_upper}' no disponible. Usa: {list(CRYPTOS_DISPONIBLES.keys())}",
        )
    if timeframe not in ALL_TIMEFRAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Timeframe '{timeframe}' no válido. Usa: {ALL_TIMEFRAMES}",
        )
    try:
        return await analyzer.get_ohlcv(pair, timeframe, limit)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/regime/{symbol}",
    response_model=RegimenResponse,
    summary="Régimen de mercado (BULL / BEAR / LATERAL)",
    description=(
        "Clasifica el régimen macro del activo usando EMA50/200, RSI diario, "
        "OBV y ciclo de halving (solo BTC). Score -5 a +5."
    ),
)
async def get_regime(symbol: str):
    symbol_upper = symbol.upper()
    pair = CRYPTOS_DISPONIBLES.get(symbol_upper)
    if not pair:
        raise HTTPException(
            status_code=404,
            detail=f"Símbolo '{symbol_upper}' no disponible. Usa: {list(CRYPTOS_DISPONIBLES.keys())}",
        )
    try:
        return await analyzer.get_regime(pair)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/macro/{symbol}",
    response_model=MacroResponse,
    summary="Contexto macro Bitcoin (halvings, S2F, ciclo)",
    description="Solo aplica a BTC. Para otros activos devuelve aplica=false.",
)
async def get_macro(symbol: str):
    symbol_upper = symbol.upper()
    pair = CRYPTOS_DISPONIBLES.get(symbol_upper)
    if not pair:
        raise HTTPException(
            status_code=404,
            detail=f"Símbolo '{symbol_upper}' no disponible. Usa: {list(CRYPTOS_DISPONIBLES.keys())}",
        )
    return await analyzer.get_macro(pair)
