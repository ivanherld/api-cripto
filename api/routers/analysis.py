from fastapi import APIRouter, HTTPException, Query

from api.core.config import ALL_TIMEFRAMES, CRYPTOS_DISPONIBLES
from api.schemas.market import AnalysisResponse
from api.services import analyzer

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get(
    "/{symbol}/{timeframe}",
    response_model=AnalysisResponse,
    summary="Análisis técnico completo",
    description=(
        "Devuelve el análisis completo de un par en un timeframe: "
        "indicadores (RSI, MACD, BB, EMAs, Estocástico, OBV), "
        "velas japonesas, patrones chartistas, volumen, divergencias, "
        "patrones armónicos (Bat/Gartley), Fibonacci y niveles SL/TP."
    ),
)
async def get_analysis(
    symbol: str,
    timeframe: str,
    include_regime: bool = Query(
        True,
        description="Si True, obtiene el régimen macro (llamada extra a Binance diario)",
    ),
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

    # Obtener régimen para enriquecer la respuesta
    regimen_str = "INDEFINIDO"
    if include_regime:
        try:
            regime_data = await analyzer.get_regime(pair)
            regimen_str = regime_data.regimen
        except ValueError:
            pass  # No bloqueamos el análisis si el régimen falla

    try:
        return await analyzer.get_analysis(pair, timeframe, regimen_override=regimen_str)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
