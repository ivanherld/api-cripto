"""
Crypto Analyzer — Señales técnicas + chartismo + contexto macro Bitcoin
=======================================================================
Fuentes bibliográficas:
  - Gallofré, F. (2014). Manual de Chartismo. bolsaytrading.com
  - Wilder, J.W. (1978). New Concepts in Technical Trading Systems.
  - Murphy, J.J. (1999). Technical Analysis of the Financial Markets.
      → EMAs y cruces: golden cross, death cross (cap. 9)
      → Volumen e interés abierto (cap. 7, p.193-216):
          · OBV/VTA (On Balance Volume): divergencia vs precio anticipa cambios
          · Reglas precio/volumen: 4 combinaciones de confirmación/contradicción
          · Climax de volumen: agotamiento en máximos y mínimos de tendencia
  - Appel, G. (1979). Technical Analysis: Power Tools for Active Investors.
  - Bollinger, J. (2001). Bollinger on Bollinger Bands.
  - Ammous, S. (2019). El Patrón Bitcoin. Deusto.
      → Stock-to-Flow: ratio existencias/flujo como medida de escasez monetaria
      → Halving: reducción programada de emisión cada ~210.000 bloques (~4 años)
      → Volatilidad estructural: BTC ~7x más volátil que oro (Ammous, tabla 10)
      → Oferta inelástica: el precio no puede inducir más producción (cap. 8)
  - IG Group (2023). 16 patrones de velas japonesas.
  - Sanchez Guillen, P.A. (2018). Guía para Elaborar Patrones Armónicos.
      → Patrones XABCD con ratios Fibonacci específicos por figura
      → Bat (Carney, 2001): AB=38.2–50% XA, CD=88.6% XA
      → Gartley (1935): AB=61.8% XA, CD=78.6% XA
  - Acción del Precio (2018). Velas, soportes, divergencias.
      → Estocástico: cruce %K/%D en zona extrema como señal de entrada
      → Divergencias: divergencia precio/oscilador como señal de agotamiento

Datos: Binance REST API via ccxt (gratuito, sin API key)
"""

import ccxt
import pandas as pd
import pandas_ta as ta
import sys
from colorama import Fore, Style, init
from datetime import datetime, timezone

init(autoreset=True)

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
EXCHANGE = ccxt.binance()

CRYPTOS_DISPONIBLES = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "BNB": "BNB/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "ADA": "ADA/USDT",
}

TIMEFRAMES = {
    "scalping":  ["5m",  "15m"],
    "swing":     ["1h",  "4h"],
    "position":  ["1d",  "1w"],
}

# Tolerancia para detectar máximos/mínimos similares (Gallofré)
TOLERANCIA_PATRON = 0.025   # 2.5%
VELAS_ANALISIS    = 200

# ─────────────────────────────────────────────
# CONTEXTO MACRO BITCOIN (Ammous, 2019)
# ─────────────────────────────────────────────
# Halvings históricos y próximos de BTC
# Fuente: Ammous (2019, cap. 8) — "cada cuatro años la recompensa cae a la mitad"
# La emisión cae exactamente cada 210.000 bloques (~4 años a 10 min/bloque)
HALVINGS_BTC = [
    datetime(2009,  1,  3, tzinfo=timezone.utc),   # Génesis
    datetime(2012, 11, 28, tzinfo=timezone.utc),   # 50 → 25 BTC/bloque
    datetime(2016,  7,  9, tzinfo=timezone.utc),   # 25 → 12.5 BTC/bloque
    datetime(2020,  5, 11, tzinfo=timezone.utc),   # 12.5 → 6.25 BTC/bloque
    datetime(2024,  4, 19, tzinfo=timezone.utc),   # 6.25 → 3.125 BTC/bloque
    datetime(2028,  4,  1, tzinfo=timezone.utc),   # 3.125 → 1.5625 (estimado)
]

# Ajuste ATR para BTC/ETH por volatilidad estructural
# Ammous (2019, tabla 10): BTC tiene desv. estándar ~7x mayor que divisas fiat
# y ~5x mayor que el oro → multiplicador de ATR más conservador
ATR_MULTIPLICADOR_CRYPTO = {
    "BTC": 2.0,   # más líquido, algo menos volátil que altcoins
    "ETH": 2.2,
    "BNB": 2.5,
    "DEFAULT": 2.8,
}


def contexto_macro_btc(symbol: str) -> dict:
    """
    Calcula el contexto macro de Bitcoin basado en el ciclo de halvings.
    Fuente: Ammous (2019, cap. 8) — Stock-to-Flow y ciclos de emisión.

    Retorna:
        - ciclo_actual: número de halving en curso
        - dias_desde_halving: días transcurridos desde el último halving
        - dias_para_halving: días para el próximo halving
        - porcentaje_ciclo: % del ciclo de 4 años transcurrido (0-100)
        - fase: "acumulación temprana" / "expansión" / "euforia" / "corrección"
        - recompensa_actual: BTC por bloque actualmente
        - s2f_aproximado: stock-to-flow estimado (Ammous, 2019, p.405)
    """
    # Solo aplica a BTC; para otras cryptos retorna contexto vacío
    base = symbol.split("/")[0].upper()
    if base != "BTC":
        return {}

    ahora = datetime.now(timezone.utc)

    # Encontrar el último y próximo halving
    ultimo_halving = HALVINGS_BTC[0]
    proximo_halving = HALVINGS_BTC[-1]
    for i, h in enumerate(HALVINGS_BTC):
        if h <= ahora:
            ultimo_halving = h
            if i + 1 < len(HALVINGS_BTC):
                proximo_halving = HALVINGS_BTC[i + 1]

    dias_desde = (ahora - ultimo_halving).days
    dias_para   = (proximo_halving - ahora).days
    ciclo_total = (proximo_halving - ultimo_halving).days
    pct_ciclo   = min(100, round(dias_desde / ciclo_total * 100, 1))

    # Fase del ciclo — basado en comportamiento histórico post-halving
    # Históricamente: acumulación 0-12m, expansión 12-24m, euforia 24-30m, corrección 30-48m
    meses = dias_desde / 30
    if meses < 6:
        fase = "acumulación temprana (oferta recién reducida)"
    elif meses < 18:
        fase = "expansión (fase alcista histórica)"
    elif meses < 30:
        fase = "euforia potencial (máximos históricos frecuentes aquí)"
    else:
        fase = "corrección / distribución (ciclo maduro)"

    # Recompensa actual por bloque
    # Génesis: 50 BTC → mitad en cada halving
    num_halvings = sum(1 for h in HALVINGS_BTC[1:] if h <= ahora)
    recompensa = 50 / (2 ** num_halvings)

    # Stock-to-Flow aproximado
    # S2F = stock / flujo = oferta_circulante / emisión_anual
    # Ammous (2019, p.405): "ratio existencias/flujo es indicador de escasez monetaria"
    # Emision anual aprox = recompensa * 6 bloques/hora * 24h * 365 días
    emision_anual = recompensa * 6 * 24 * 365
    # Oferta circulante aproximada (a 2024: ~19.7M BTC)
    oferta_aprox = 19_700_000 + (dias_desde * recompensa * 6 * 24)
    s2f = round(oferta_aprox / emision_anual, 1)

    return {
        "dias_desde_halving": dias_desde,
        "dias_para_halving":  max(0, dias_para),
        "porcentaje_ciclo":   pct_ciclo,
        "fase":               fase,
        "recompensa_bloque":  recompensa,
        "s2f_aproximado":     s2f,
        "num_halvings":       num_halvings,
    }


def imprimir_contexto_macro(symbol: str):
    """Imprime el contexto macro Bitcoin si aplica."""
    ctx = contexto_macro_btc(symbol)
    if not ctx:
        return

    print(f"\n  {Fore.CYAN}╔══ CONTEXTO MACRO BTC (Ammous, 2019) ══════════════════╗{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  Halving: {ctx['dias_desde_halving']} días atrás  |  "
          f"Próximo: {ctx['dias_para_halving']} días")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  Ciclo actual: {ctx['porcentaje_ciclo']}% completado")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  Fase histórica: {ctx['fase']}")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  Emisión actual: {ctx['recompensa_bloque']} BTC/bloque")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  Stock-to-Flow aprox.: {ctx['s2f_aproximado']}x  "
          f"(Ammous 2019, p.405)")
    print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.LIGHTBLACK_EX}Nota: S2F mide escasez monetaria. Oro ≈ 60x. "
          f"Cuanto mayor, más escaso.{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}╚═══════════════════════════════════════════════════════╝{Style.RESET_ALL}")


# ─────────────────────────────────────────────
# CLASIFICADOR DE RÉGIMEN DE MERCADO
# ─────────────────────────────────────────────
def clasificar_regimen(symbol: str) -> dict:
    """
    Determina si el mercado está en tendencia BULL, BEAR o LATERAL
    analizando datos diarios con los indicadores ya implementados.

    Opera sobre el timeframe '1d' con 200 velas para tener suficiente
    historia para la EMA200 y el OBV. El régimen es una propiedad
    macro/estructural, no de corto plazo.

    Sistema de votación (0-5 puntos hacia BULL):

      1. Precio vs EMA200  — Murphy (1999), cap.9
         Precio > EMA200 → +1 (tendencia alcista de largo plazo)
         Precio < EMA200 → -1 (tendencia bajista de largo plazo)

      2. EMA50 vs EMA200  — Murphy (1999), cap.9
         EMA50 > EMA200  → +1 (Golden Cross activo)
         EMA50 < EMA200  → -1 (Death Cross activo)

      3. RSI(14) diario   — Wilder (1978)
         RSI > 55         → +1 (momentum alcista)
         RSI < 45         → -1 (momentum bajista)
         45-55            →  0 (zona neutral)

      4. OBV — tendencia 50 velas  — Murphy (1999), cap.7
         OBV sube         → +1 (acumulación predominante)
         OBV baja         → -1 (distribución predominante)

      5. Ciclo halving BTC — Ammous (2019), cap.8
         Solo aplica a BTC. Fase acumulación/expansión → +1
         Fase euforia/corrección → -1. Para otros activos: 0

    Resultado (suma de votos, rango -5 a +5):
      >= +2  → BULL  🟢
      <= -2  → BEAR  🔴
      -1..+1 → LATERAL 🟡

    Retorna dict con régimen, score, votos individuales y contexto
    para ser mostrado al inicio y usado como filtro en los patrones.
    """
    # ── Descargar datos diarios (200 velas) ──────────────────────
    try:
        raw = EXCHANGE.fetch_ohlcv(symbol, "1d", limit=200)
        df  = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
    except Exception as e:
        return {
            "regimen": "INDEFINIDO",
            "score": 0,
            "score_anterior": 0,
            "votos": {},
            "cambio": None,
            "señal_cambio": None,
            "error": str(e),
        }

    if len(df) < 110:
        return {"regimen": "INDEFINIDO", "score": 0, "score_anterior": 0,
                "votos": {}, "cambio": None, "señal_cambio": None,
                "error": "Datos insuficientes (mínimo 110 velas diarias)"}

    # Calcular indicadores sobre el DataFrame completo
    df.ta.ema(length=50,  append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14,  append=True)
    df.ta.obv(append=True)

    def _calcular_score_en(fila_idx: int, df: pd.DataFrame,
                           obv_ref_idx: int, symbol: str) -> tuple:
        """
        Calcula el score de régimen en una fila del DataFrame.
        Retorna (score, votos_dict).
        obv_ref_idx: índice de referencia 50 velas atrás para OBV.
        """
        votos = {}
        score = 0
        fila  = df.iloc[fila_idx]
        precio = fila["close"]

        # Voto 1: Precio vs EMA200
        ema200 = fila.get("EMA_200", None)
        if ema200 and not pd.isna(ema200):
            if precio > ema200:
                votos["EMA200"] = ("BULL", f"Precio {precio:,.2f} > EMA200 {ema200:,.2f}")
                score += 1
            else:
                votos["EMA200"] = ("BEAR", f"Precio {precio:,.2f} < EMA200 {ema200:,.2f}")
                score -= 1
        else:
            votos["EMA200"] = ("N/A", "Datos insuficientes para EMA200")

        # Voto 2: EMA50 vs EMA200
        ema50 = fila.get("EMA_50", None)
        if ema50 and ema200 and not pd.isna(ema50) and not pd.isna(ema200):
            if ema50 > ema200:
                votos["EMA_cross"] = ("BULL",
                    f"EMA50 {ema50:,.2f} > EMA200 {ema200:,.2f} — Golden Cross activo")
                score += 1
            else:
                votos["EMA_cross"] = ("BEAR",
                    f"EMA50 {ema50:,.2f} < EMA200 {ema200:,.2f} — Death Cross activo")
                score -= 1
        else:
            votos["EMA_cross"] = ("N/A", "Datos insuficientes para cruce EMA")

        # Voto 3: RSI diario
        rsi = fila.get("RSI_14", None)
        if rsi and not pd.isna(rsi):
            if rsi > 55:
                votos["RSI"] = ("BULL", f"RSI diario {rsi:.1f} > 55 — momentum alcista")
                score += 1
            elif rsi < 45:
                votos["RSI"] = ("BEAR", f"RSI diario {rsi:.1f} < 45 — momentum bajista")
                score -= 1
            else:
                votos["RSI"] = ("NEUTRAL", f"RSI diario {rsi:.1f} en zona neutral (45-55)")
        else:
            votos["RSI"] = ("N/A", "RSI no disponible")

        # Voto 4: OBV — comparado 50 velas atrás desde fila_idx
        if "OBV" in df.columns and not df["OBV"].isna().all():
            obv_actual = df["OBV"].iloc[fila_idx]
            obv_ref = df["OBV"].iloc[obv_ref_idx] if abs(obv_ref_idx) < len(df) else None
            if (obv_ref is not None
                    and not pd.isna(obv_actual)
                    and not pd.isna(obv_ref)
                    and obv_ref != 0):
                cambio_pct = (obv_actual - obv_ref) / abs(obv_ref) * 100
                if cambio_pct > 5:
                    votos["OBV"] = ("BULL",
                        f"OBV sube {cambio_pct:.1f}% en 50 días — acumulación predominante")
                    score += 1
                elif cambio_pct < -5:
                    votos["OBV"] = ("BEAR",
                        f"OBV baja {cambio_pct:.1f}% en 50 días — distribución predominante")
                    score -= 1
                else:
                    votos["OBV"] = ("NEUTRAL",
                        f"OBV plano ({cambio_pct:.1f}%) — sin presión clara")
            else:
                votos["OBV"] = ("N/A", "OBV no calculable")
        else:
            votos["OBV"] = ("N/A", "OBV no disponible")

        # Voto 5: Ciclo halving BTC
        base = symbol.split("/")[0].upper()
        if base == "BTC":
            ctx  = contexto_macro_btc(symbol)
            fase = ctx.get("fase", "")
            if "acumulación" in fase or "expansión" in fase:
                votos["Halving"] = ("BULL", f"Ciclo halving: {fase}")
                score += 1
            elif "euforia" in fase or "corrección" in fase:
                votos["Halving"] = ("BEAR", f"Ciclo halving: {fase}")
                score -= 1
            else:
                votos["Halving"] = ("NEUTRAL", f"Ciclo halving: {fase}")
        else:
            votos["Halving"] = ("N/A",
                f"Ciclo halving solo aplica a BTC (activo: {base})")

        return score, votos

    # ── Score ACTUAL (últimas 50 velas) ──────────────────────────
    score_actual, votos_actual = _calcular_score_en(
        fila_idx=-1, df=df, obv_ref_idx=-50, symbol=symbol
    )

    # ── Score ANTERIOR (50 velas atrás, con referencia OBV 50 velas antes) ──
    score_anterior, _ = _calcular_score_en(
        fila_idx=-50, df=df, obv_ref_idx=-100, symbol=symbol
    )

    # ── Determinar régimen actual y anterior ─────────────────────
    def _a_regimen(s: int) -> str:
        if s >= 2:  return "BULL"
        if s <= -2: return "BEAR"
        return "LATERAL"

    regimen          = _a_regimen(score_actual)
    regimen_anterior = _a_regimen(score_anterior)

    # ── Detectar cambio de régimen y generar señal ───────────────
    # Un cambio es significativo solo si cruza una frontera real:
    # BEAR→BULL, BULL→BEAR, LATERAL→BULL, LATERAL→BEAR
    # BEAR↔LATERAL no se señala como BUY/SELL (aún no hay tendencia clara)
    cambio       = None
    señal_cambio = None

    if regimen_anterior != regimen:
        cambio = f"{regimen_anterior} → {regimen}"

        if regimen_anterior == "BEAR" and regimen == "BULL":
            señal_cambio = {
                "señal":   "BUY",
                "titulo":  "🔄 CAMBIO DE RÉGIMEN: BEAR → BULL",
                "detalle": (f"El score pasó de {score_anterior:+d} a {score_actual:+d}. "
                            f"Los 5 indicadores diarios ahora apuntan mayoritariamente al alza. "
                            f"Considerar posiciones largas en retrocesos."),
                "fuente":  "Murphy 1999 / Wilder 1978 / Ammous 2019",
            }
        elif regimen_anterior == "BULL" and regimen == "BEAR":
            señal_cambio = {
                "señal":   "SELL",
                "titulo":  "🔄 CAMBIO DE RÉGIMEN: BULL → BEAR",
                "detalle": (f"El score pasó de {score_anterior:+d} a {score_actual:+d}. "
                            f"Los indicadores diarios se giraron mayoritariamente a la baja. "
                            f"Considerar reducir exposición o posiciones cortas."),
                "fuente":  "Murphy 1999 / Wilder 1978 / Ammous 2019",
            }
        elif regimen_anterior == "LATERAL" and regimen == "BULL":
            señal_cambio = {
                "señal":   "BUY",
                "titulo":  "🔄 CAMBIO DE RÉGIMEN: LATERAL → BULL",
                "detalle": (f"El score pasó de {score_anterior:+d} a {score_actual:+d}. "
                            f"El mercado rompe lateralización con sesgo alcista. "
                            f"Vigilar confirmación en timeframes menores."),
                "fuente":  "Murphy 1999 / Wilder 1978 / Ammous 2019",
            }
        elif regimen_anterior == "LATERAL" and regimen == "BEAR":
            señal_cambio = {
                "señal":   "SELL",
                "titulo":  "🔄 CAMBIO DE RÉGIMEN: LATERAL → BEAR",
                "detalle": (f"El score pasó de {score_anterior:+d} a {score_actual:+d}. "
                            f"El mercado rompe lateralización con sesgo bajista. "
                            f"Vigilar confirmación en timeframes menores."),
                "fuente":  "Murphy 1999 / Wilder 1978 / Ammous 2019",
            }
        elif regimen in ("BULL", "BEAR"):
            # BULL→LATERAL o BEAR→LATERAL: el mercado se está enfriando
            señal_cambio = {
                "señal":   "--",
                "titulo":  f"🔄 CAMBIO DE RÉGIMEN: {regimen_anterior} → LATERAL",
                "detalle": (f"El score pasó de {score_anterior:+d} a {score_actual:+d}. "
                            f"La tendencia principal se está debilitando. Esperar confirmación."),
                "fuente":  "Murphy 1999 / Wilder 1978 / Ammous 2019",
            }

    ult    = df.iloc[-1]
    precio = ult["close"]
    ema200 = ult.get("EMA_200", None)

    return {
        "regimen":          regimen,
        "regimen_anterior": regimen_anterior,
        "score":            score_actual,
        "score_anterior":   score_anterior,
        "votos":            votos_actual,
        "cambio":           cambio,
        "señal_cambio":     señal_cambio,
        "precio_diario":    precio,
        "ema200":           ema200,
    }


def imprimir_regimen(regimen_data: dict):
    """Imprime el bloque de clasificación de régimen de mercado."""
    if not regimen_data or "error" in regimen_data:
        err = regimen_data.get("error", "desconocido") if regimen_data else "sin datos"
        print(f"\n  {Fore.LIGHTBLACK_EX}[Régimen] No disponible: {err}{Style.RESET_ALL}")
        return

    regimen          = regimen_data["regimen"]
    regimen_anterior = regimen_data.get("regimen_anterior", regimen)
    score            = regimen_data["score"]
    score_anterior   = regimen_data.get("score_anterior", score)
    votos            = regimen_data["votos"]
    cambio           = regimen_data.get("cambio")
    señal_cambio     = regimen_data.get("señal_cambio")

    # Color y etiqueta según régimen
    if regimen == "BULL":
        color = Fore.GREEN
        icono = "▲ BULL MARKET"
        borde = "╔══ RÉGIMEN: BULL MARKET ════════════════════════════════╗"
        pie   = "╚════════════════════════════════════════════════════════╝"
    elif regimen == "BEAR":
        color = Fore.RED
        icono = "▼ BEAR MARKET"
        borde = "╔══ RÉGIMEN: BEAR MARKET ════════════════════════════════╗"
        pie   = "╚════════════════════════════════════════════════════════╝"
    else:
        color = Fore.YELLOW
        icono = "◆ MERCADO LATERAL"
        borde = "╔══ RÉGIMEN: LATERAL / INDEFINIDO ═══════════════════════╗"
        pie   = "╚════════════════════════════════════════════════════════╝"

    print(f"\n  {color}{borde}{Style.RESET_ALL}")
    print(f"  {color}║{Style.RESET_ALL}  {icono}  —  Score actual: {score:+d}/5  |  "
          f"Score hace 50 días: {score_anterior:+d}/5")
    if cambio:
        print(f"  {color}║{Style.RESET_ALL}  Régimen anterior: {regimen_anterior}  →  Ahora: {regimen}")
    print(f"  {color}║{Style.RESET_ALL}")

    # Votos individuales
    for indicador, (resultado, detalle) in votos.items():
        if resultado == "BULL":
            simbolo = f"{Fore.GREEN}  ▲{Style.RESET_ALL}"
        elif resultado == "BEAR":
            simbolo = f"{Fore.RED}  ▼{Style.RESET_ALL}"
        elif resultado == "NEUTRAL":
            simbolo = f"{Fore.YELLOW}  ◆{Style.RESET_ALL}"
        else:
            simbolo = f"{Fore.LIGHTBLACK_EX}  ·{Style.RESET_ALL}"
        print(f"  {color}║{Style.RESET_ALL} {simbolo}  {indicador:12s}  {detalle}")

    print(f"  {color}║{Style.RESET_ALL}")

    # Señal de cambio de régimen — la parte nueva
    if señal_cambio:
        s = señal_cambio["señal"]
        if s == "BUY":
            sc = Fore.GREEN
            sb = "[▲ BUY]"
        elif s == "SELL":
            sc = Fore.RED
            sb = "[▼ SELL]"
        else:
            sc = Fore.YELLOW
            sb = "[◆ ATENCIÓN]"

        print(f"  {color}║{Style.RESET_ALL}  {sc}{'─' * 52}{Style.RESET_ALL}")
        print(f"  {color}║{Style.RESET_ALL}  {sc}{sb} {señal_cambio['titulo']}{Style.RESET_ALL}")
        print(f"  {color}║{Style.RESET_ALL}  {Fore.LIGHTBLACK_EX}{señal_cambio['detalle']}{Style.RESET_ALL}")
        print(f"  {color}║{Style.RESET_ALL}  {Fore.LIGHTBLACK_EX}Fuente: {señal_cambio['fuente']}{Style.RESET_ALL}")
        print(f"  {color}║{Style.RESET_ALL}  {sc}{'─' * 52}{Style.RESET_ALL}")
        print(f"  {color}║{Style.RESET_ALL}")

    # Línea interpretativa según régimen
    if regimen == "BULL":
        interp = "Patrones alcistas a favor del régimen ↑  |  Bajistas: operá con precaución"
    elif regimen == "BEAR":
        interp = "Patrones bajistas a favor del régimen ↓  |  Alcistas: operá con precaución"
    else:
        interp = "Sin tendencia clara — preferí señales con alta confluencia"

    print(f"  {color}║{Style.RESET_ALL}  {Fore.LIGHTBLACK_EX}{interp}{Style.RESET_ALL}")
    print(f"  {color}{pie}{Style.RESET_ALL}")


def etiqueta_regimen(señal_patron: str, regimen: str) -> str:
    """
    Devuelve una etiqueta corta que indica si un patrón va
    a favor o en contra del régimen de mercado detectado.
    Usada en la impresión de patrones armónicos y chartistas.
    """
    if regimen == "INDEFINIDO" or not regimen:
        return ""
    if (señal_patron == "BUY" and regimen == "BULL") or \
       (señal_patron == "SELL" and regimen == "BEAR"):
        return f"  {Fore.GREEN}[✓ a favor del régimen {regimen}]{Style.RESET_ALL}"
    elif (señal_patron == "BUY" and regimen == "BEAR") or \
         (señal_patron == "SELL" and regimen == "BULL"):
        return f"  {Fore.RED}[⚠ contra el régimen {regimen}]{Style.RESET_ALL}"
    return ""


# ─────────────────────────────────────────────
# UTILIDADES DE CONSOLA
# ─────────────────────────────────────────────
def titulo(texto):
    ancho = 60
    print(f"\n{Fore.CYAN}{'═' * ancho}")
    print(f"  {texto}")
    print(f"{'═' * ancho}{Style.RESET_ALL}")

def seccion(texto):
    print(f"\n{Fore.YELLOW}  ▸ {texto}{Style.RESET_ALL}")

def señal_buy(texto):
    print(f"  {Fore.GREEN}[BUY]  {texto}{Style.RESET_ALL}")

def señal_sell(texto):
    print(f"  {Fore.RED}[SELL] {texto}{Style.RESET_ALL}")

def neutro(texto):
    print(f"  {Fore.WHITE}[--]   {texto}{Style.RESET_ALL}")

def info(texto):
    print(f"         {Fore.LIGHTBLACK_EX}{texto}{Style.RESET_ALL}")


# ─────────────────────────────────────────────
# DESCARGA DE DATOS
# ─────────────────────────────────────────────
def obtener_velas(symbol, timeframe, limit=VELAS_ANALISIS):
    """Descarga velas OHLCV de Binance via ccxt (sin API key)."""
    try:
        raw = EXCHANGE.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        print(f"{Fore.RED}  Error descargando {symbol} {timeframe}: {e}{Style.RESET_ALL}")
        return None


# ─────────────────────────────────────────────
# INDICADORES TÉCNICOS
# ─────────────────────────────────────────────
def calcular_indicadores(df):
    """
    Calcula todos los indicadores sobre el DataFrame de velas.
    Fuentes: Wilder (RSI, ATR), Appel (MACD), Bollinger (BB),
             Murphy (EMAs), Hosoda (Ichimoku).
    """
    # RSI — Wilder (1978), período 14
    df.ta.rsi(length=14, append=True)

    # MACD — Appel (1979), parámetros 12/26/9
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    # Bollinger Bands — Bollinger (2001), 20 períodos, 2 desvíos
    df.ta.bbands(length=20, std=2, append=True)

    # EMAs — Murphy (1999): 9, 21, 50, 200
    df.ta.ema(length=9,   append=True)
    df.ta.ema(length=21,  append=True)
    df.ta.ema(length=50,  append=True)
    df.ta.ema(length=200, append=True)

    # ATR — Wilder (1978), para Stop Loss / Take Profit
    df.ta.atr(length=14, append=True)

    # Estocástico — Acción del Precio (2018), p.47; parámetros estándar 14/3/3
    # %K = posición del cierre dentro del rango de las últimas 14 velas
    # %D = media móvil de %K (señal de confirmación)
    df.ta.stoch(k=14, d=3, smooth_k=3, append=True)

    # OBV (On Balance Volume / Volumen Total Acumulativo) — Murphy (1999), cap.7, p.193
    # "El indicador de volumen más sencillo y más conocido" (Murphy, p.193)
    # Desarrollado por Granville (1963): suma volumen cuando cierra al alza,
    # resta cuando cierra a la baja. La dirección de la línea OBV confirma
    # o anticipa cambios de tendencia del precio.
    df.ta.obv(append=True)

    return df


# ─────────────────────────────────────────────
# SEÑALES DE INDICADORES
# ─────────────────────────────────────────────
def analizar_indicadores(df, timeframe):
    """
    Genera señales de compra/venta basadas en indicadores técnicos.
    Retorna lista de (señal, descripción, fuente).
    """
    señales = []
    ult = df.iloc[-1]
    prev = df.iloc[-2]

    precio = ult["close"]

    # ── RSI (Wilder, 1978) ──────────────────────
    rsi_col = "RSI_14"
    if rsi_col in df.columns:
        rsi = ult[rsi_col]
        rsi_prev = prev[rsi_col]
        if rsi < 30:
            señales.append(("BUY",  f"RSI={rsi:.1f} — zona de sobreventa (<30)", "Wilder 1978"))
        elif rsi > 70:
            señales.append(("SELL", f"RSI={rsi:.1f} — zona de sobrecompra (>70)", "Wilder 1978"))
        elif rsi_prev < 50 and rsi >= 50:
            señales.append(("BUY",  f"RSI={rsi:.1f} — cruce alcista de línea central (50)", "Wilder 1978"))
        elif rsi_prev > 50 and rsi <= 50:
            señales.append(("SELL", f"RSI={rsi:.1f} — cruce bajista de línea central (50)", "Wilder 1978"))

    # ── MACD (Appel, 1979) ─────────────────────
    macd_col   = "MACD_12_26_9"
    signal_col = "MACDs_12_26_9"
    hist_col   = "MACDh_12_26_9"
    if macd_col in df.columns:
        macd   = ult[macd_col]
        signal = ult[signal_col]
        hist   = ult[hist_col]
        hist_p = prev[hist_col]
        if hist_p < 0 and hist > 0:
            señales.append(("BUY",  f"MACD cruce alcista — histograma cambia a positivo", "Appel 1979"))
        elif hist_p > 0 and hist < 0:
            señales.append(("SELL", f"MACD cruce bajista — histograma cambia a negativo", "Appel 1979"))
        elif macd > 0 and signal > 0 and hist > 0:
            señales.append(("BUY",  f"MACD positivo y por encima de señal — tendencia alcista", "Appel 1979"))
        elif macd < 0 and signal < 0 and hist < 0:
            señales.append(("SELL", f"MACD negativo y por debajo de señal — tendencia bajista", "Appel 1979"))

    # ── Bollinger Bands (Bollinger, 2001) ───────
    bb_low  = "BBL_20_2.0"
    bb_mid  = "BBM_20_2.0"
    bb_high = "BBU_20_2.0"
    if bb_low in df.columns:
        bbl = ult[bb_low]
        bbh = ult[bb_high]
        bbm = ult[bb_mid]
        ancho_pct = ((bbh - bbl) / bbm) * 100
        if precio <= bbl:
            señales.append(("BUY",  f"Precio toca/rompe banda inferior BB — posible rebote", "Bollinger 2001"))
        elif precio >= bbh:
            señales.append(("SELL", f"Precio toca/rompe banda superior BB — posible corrección", "Bollinger 2001"))
        if ancho_pct < 2.0:
            señales.append(("--",   f"Bandas muy estrechas ({ancho_pct:.1f}%) — compresión, rotura inminente", "Bollinger 2001"))

    # ── EMAs (Murphy, 1999) ────────────────────
    ema9   = f"EMA_9"
    ema21  = f"EMA_21"
    ema50  = f"EMA_50"
    ema200 = f"EMA_200"
    if ema9 in df.columns and ema21 in df.columns:
        e9  = ult[ema9]
        e21 = ult[ema21]
        e9p = prev[ema9]
        e21p= prev[ema21]
        if e9p < e21p and e9 > e21:
            señales.append(("BUY",  f"Cruce dorado EMA9 > EMA21 — momentum alcista corto plazo", "Murphy 1999"))
        elif e9p > e21p and e9 < e21:
            señales.append(("SELL", f"Cruce de la muerte EMA9 < EMA21 — momentum bajista", "Murphy 1999"))

    if ema50 in df.columns and ema200 in df.columns:
        e50  = ult[ema50]
        e200 = ult[ema200]
        e50p = prev[ema50]
        e200p= prev[ema200]
        if e50p < e200p and e50 > e200:
            señales.append(("BUY",  f"Golden Cross EMA50 > EMA200 — señal alcista largo plazo", "Murphy 1999"))
        elif e50p > e200p and e50 < e200:
            señales.append(("SELL", f"Death Cross EMA50 < EMA200 — señal bajista largo plazo", "Murphy 1999"))

        if precio > e200:
            señales.append(("BUY",  f"Precio sobre EMA200 — tendencia alcista de largo plazo", "Murphy 1999"))
        else:
            señales.append(("SELL", f"Precio bajo EMA200 — tendencia bajista de largo plazo", "Murphy 1999"))

    # ── Estocástico (Acción del Precio, 2018) ──
    # Fuente: Acción del Precio (2018), p.47
    # Señal de entrada: %K cruza %D en zona extrema (<20 sobreventa, >80 sobrecompra)
    # "cuando las líneas se juntan por encima o debajo de la línea de puntos y son
    #  limpias, significa un buen momento de compra" (Acción del Precio, 2018, p.47)
    stoch_k = "STOCHk_14_3_3"
    stoch_d = "STOCHd_14_3_3"
    if stoch_k in df.columns and stoch_d in df.columns:
        sk  = ult[stoch_k]
        sd  = ult[stoch_d]
        skp = prev[stoch_k]
        sdp = prev[stoch_d]
        if not (pd.isna(sk) or pd.isna(sd) or pd.isna(skp) or pd.isna(sdp)):
            # Cruce alcista en zona de sobreventa
            if skp < sdp and sk > sd and sk < 25:
                señales.append(("BUY",
                    f"Estocástico: %K cruza %D al alza en sobreventa (%K={sk:.1f})",
                    "Acción del Precio 2018, p.47"))
            # Cruce bajista en zona de sobrecompra
            elif skp > sdp and sk < sd and sk > 75:
                señales.append(("SELL",
                    f"Estocástico: %K cruza %D a la baja en sobrecompra (%K={sk:.1f})",
                    "Acción del Precio 2018, p.47"))
            # Zona extrema sin cruce aún (señal de alerta)
            elif sk < 20 and sd < 20:
                señales.append(("BUY",
                    f"Estocástico en sobreventa extrema (%K={sk:.1f}, %D={sd:.1f})",
                    "Acción del Precio 2018, p.47"))
            elif sk > 80 and sd > 80:
                señales.append(("SELL",
                    f"Estocástico en sobrecompra extrema (%K={sk:.1f}, %D={sd:.1f})",
                    "Acción del Precio 2018, p.47"))

    return señales


# ─────────────────────────────────────────────
# ANÁLISIS DE VOLUMEN (Murphy, 1999)
# ─────────────────────────────────────────────
def analizar_volumen(df):
    """
    Genera señales basadas en la relación precio-volumen y el OBV.
    Fuente: Murphy, J.J. (1999). Análisis Técnico de los Mercados Financieros,
            cap. 7 "Volumen e interés abierto", p.193-216.

    REGLAS PRECIO/VOLUMEN (Murphy, p.198):
    Murphy establece cuatro combinaciones fundamentales:

      1. Precio ↑ + Volumen ↑  → señal ALCISTA  (tendencia confirmada por dinero nuevo)
      2. Precio ↑ + Volumen ↓  → señal BAJISTA  (subida sin convicción, probable corrección)
      3. Precio ↓ + Volumen ↑  → señal BAJISTA  (presión vendedora con convicción)
      4. Precio ↓ + Volumen ↓  → señal ALCISTA  (caída sin convicción, tendencia agotándose)

    "Los aumentos del volumen ayudan a confirmar la resolución de los
     patrones de precios o cualquier otro desarrollo gráfico significativo
     que anuncie el comienzo de una nueva tendencia." (Murphy, p.203)

    OBV — ON BALANCE VOLUME (Murphy, p.193-197):
    Desarrollado por Granville (1963). La línea OBV debería moverse en
    la misma dirección que el precio. Cuando divergen, el volumen está
    advirtiendo de un cambio inminente de tendencia.

    "La pérdida de presión al alza en una tendencia alcista, o de presión
     a la baja en una tendencia bajista, se refleja en la cifra de volumen
     antes de manifestarse en un cambio de tendencia." (Murphy, p.193)

    CLIMAX DE VOLUMEN (Murphy, p.203):
    Un volumen extraordinariamente alto tras una tendencia prolongada
    puede indicar agotamiento — "descarga" en máximos o "climax de
    ventas" en mínimos.
    """
    resultados = []

    if len(df) < 20:
        return resultados

    ult  = df.iloc[-1]
    prev = df.iloc[-2]

    precio_actual = ult["close"]
    precio_prev   = prev["close"]
    vol_actual    = ult["volume"]
    vol_prev      = prev["volume"]

    # Volumen promedio de las últimas 20 velas (excluye la actual)
    vol_promedio  = df["volume"].iloc[-21:-1].mean()

    if vol_promedio == 0 or pd.isna(vol_promedio):
        return resultados

    # Ratio volumen actual vs promedio
    vol_ratio = vol_actual / vol_promedio

    # Determinar dirección del precio y del volumen
    precio_sube   = precio_actual > precio_prev * 1.0005   # margen mínimo 0.05%
    precio_baja   = precio_actual < precio_prev * 0.9995
    vol_crece     = vol_actual > vol_prev * 1.05
    vol_decrece   = vol_actual < vol_prev * 0.95
    vol_alto      = vol_ratio > 1.5    # 50% sobre la media
    vol_muy_alto  = vol_ratio > 2.5    # 150% sobre la media

    # ── REGLA 1: Precio ↑ + Volumen ↑ (Murphy, p.198) ──────────────
    if precio_sube and vol_crece:
        resultados.append({
            "tipo":   "Precio ↑ con Volumen ↑",
            "señal":  "BUY",
            "fuerza": "fuerte" if vol_muy_alto else ("moderada" if vol_alto else "débil"),
            "descripcion": (f"Volumen {vol_ratio:.1f}x sobre la media — "
                        f"tendencia alcista confirmada por dinero nuevo"),
            "fuente": "Murphy 1999, cap.7 p.198",
        })

    # ── REGLA 2: Precio ↑ + Volumen ↓ (Murphy, p.198) ──────────────
    elif precio_sube and vol_decrece:
        resultados.append({
            "tipo":   "Precio ↑ con Volumen ↓",
            "señal":  "SELL",
            "fuerza": "moderada",
            "descripcion": (f"Volumen {vol_ratio:.1f}x sobre la media — "
                        f"subida sin convicción, probable corrección"),
            "fuente": "Murphy 1999, cap.7 p.198",
        })

    # ── REGLA 3: Precio ↓ + Volumen ↑ (Murphy, p.198) ──────────────
    elif precio_baja and vol_crece:
        resultados.append({
            "tipo":   "Precio ↓ con Volumen ↑",
            "señal":  "SELL",
            "fuerza": "fuerte" if vol_muy_alto else ("moderada" if vol_alto else "débil"),
            "descripcion": (f"Volumen {vol_ratio:.1f}x sobre la media — "
                        f"presión vendedora con convicción"),
            "fuente": "Murphy 1999, cap.7 p.198",
        })

    # ── REGLA 4: Precio ↓ + Volumen ↓ (Murphy, p.198) ──────────────
    elif precio_baja and vol_decrece:
        resultados.append({
            "tipo":   "Precio ↓ con Volumen ↓",
            "señal":  "BUY",
            "fuerza": "moderada",
            "descripcion": (f"Volumen {vol_ratio:.1f}x sobre la media — "
                        f"caída sin convicción, tendencia bajista agotándose"),
            "fuente": "Murphy 1999, cap.7 p.198",
        })

    # ── CLIMAX DE VOLUMEN (Murphy, p.203) ───────────────────────────
    # Volumen muy alto tras tendencia extendida: posible agotamiento
    if vol_muy_alto:
        # Verificar si hay tendencia extendida (últimas 10 velas)
        closes_10 = df["close"].iloc[-11:-1]
        tendencia_alcista_10 = closes_10.iloc[-1] > closes_10.iloc[0] * 1.02
        tendencia_bajista_10 = closes_10.iloc[-1] < closes_10.iloc[0] * 0.98

        if tendencia_alcista_10 and precio_sube:
            resultados.append({
                "tipo":   "Posible climax de volumen (máximo)",
                "señal":  "SELL",
                "fuerza": "moderada",
                "descripcion": (f"Volumen {vol_ratio:.1f}x la media tras tendencia alcista — "
                            f"posible 'descarga' o agotamiento de compradores"),
                "fuente": "Murphy 1999, cap.7 p.203",
            })
        elif tendencia_bajista_10 and precio_baja:
            resultados.append({
                "tipo":   "Posible climax de ventas (mínimo)",
                "señal":  "BUY",
                "fuerza": "moderada",
                "descripcion": (f"Volumen {vol_ratio:.1f}x la media tras tendencia bajista — "
                            f"posible capitulación, agotamiento de vendedores"),
                "fuente": "Murphy 1999, cap.7 p.203",
            })

    # ── OBV — DIVERGENCIA CON PRECIO (Murphy, p.193-197) ────────────
    obv_col = "OBV"
    if obv_col in df.columns and not df[obv_col].isna().all():
        # Comparar tendencia del OBV vs tendencia del precio en últimas 20 velas
        ventana_obv = 20
        seg = df.iloc[-ventana_obv:]

        precio_inicio = seg["close"].iloc[0]
        precio_fin    = seg["close"].iloc[-1]
        obv_inicio    = seg[obv_col].iloc[0]
        obv_fin       = seg[obv_col].iloc[-1]

        precio_tendencia_alza = precio_fin > precio_inicio * 1.003
        precio_tendencia_baja = precio_fin < precio_inicio * 0.997
        obv_tendencia_alza    = obv_fin > obv_inicio * 1.001
        obv_tendencia_baja    = obv_fin < obv_inicio * 0.999

        # Divergencia alcista OBV: precio baja pero OBV sube
        if precio_tendencia_baja and obv_tendencia_alza:
            resultados.append({
                "tipo":   "Divergencia alcista OBV",
                "señal":  "BUY",
                "fuerza": "fuerte",
                "descripcion": (f"Precio ↓ en {ventana_obv} velas pero OBV ↑ — "
                            f"acumulación oculta, el volumen anticipa rebote"),
                "fuente": "Murphy 1999, cap.7 p.193",
            })

        # Divergencia bajista OBV: precio sube pero OBV baja
        elif precio_tendencia_alza and obv_tendencia_baja:
            resultados.append({
                "tipo":   "Divergencia bajista OBV",
                "señal":  "SELL",
                "fuerza": "fuerte",
                "descripcion": (f"Precio ↑ en {ventana_obv} velas pero OBV ↓ — "
                            f"distribución oculta, el volumen anticipa corrección"),
                "fuente": "Murphy 1999, cap.7 p.193",
            })

        # Confirmación OBV alineado con tendencia
        elif precio_tendencia_alza and obv_tendencia_alza:
            resultados.append({
                "tipo":   "OBV confirma tendencia alcista",
                "señal":  "BUY",
                "fuerza": "moderada",
                "descripcion": f"Precio ↑ y OBV ↑ alineados en {ventana_obv} velas — tendencia con convicción",
                "fuente": "Murphy 1999, cap.7 p.193",
            })
        elif precio_tendencia_baja and obv_tendencia_baja:
            resultados.append({
                "tipo":   "OBV confirma tendencia bajista",
                "señal":  "SELL",
                "fuerza": "moderada",
                "descripcion": f"Precio ↓ y OBV ↓ alineados en {ventana_obv} velas — tendencia con convicción",
                "fuente": "Murphy 1999, cap.7 p.193",
            })

    return resultados


# ─────────────────────────────────────────────
# DIVERGENCIAS RSI / MACD  (Acción del Precio, 2018)
# ─────────────────────────────────────────────
def detectar_divergencias(df):
    """
    Detecta divergencias entre precio y osciladores (RSI y MACD).
    Fuente: Acción del Precio (2018), p.50

    "Una divergencia es un fallo entre el precio y los indicadores,
     por lo que el precio tiende a corregirse en las próximas velas."
     (Acción del Precio, 2018, p.50)

    Divergencia ALCISTA (bullish): precio hace mínimo más bajo, pero el
    oscilador hace mínimo más alto → agotamiento bajista, posible rebote.

    Divergencia BAJISTA (bearish): precio hace máximo más alto, pero el
    oscilador hace máximo más bajo → agotamiento alcista, posible corrección.

    Metodología: compara los dos últimos valles/picos del precio contra
    los correspondientes en RSI/MACD, en una ventana de las últimas 50 velas.
    """
    resultados = []

    if len(df) < 20:
        return resultados

    ventana = min(50, len(df))
    seg = df.iloc[-ventana:]

    # ── Detectar picos y valles locales del precio (ventana 5) ──
    def picos_locales(serie, ventana_local=5):
        """Retorna índices y valores de los últimos 2 picos locales."""
        picos = []
        for i in range(ventana_local, len(serie) - ventana_local):
            if serie.iloc[i] == serie.iloc[i - ventana_local: i + ventana_local + 1].max():
                picos.append((i, serie.iloc[i]))
        return picos[-2:] if len(picos) >= 2 else []

    def valles_locales(serie, ventana_local=5):
        """Retorna índices y valores de los últimos 2 valles locales."""
        valles = []
        for i in range(ventana_local, len(serie) - ventana_local):
            if serie.iloc[i] == serie.iloc[i - ventana_local: i + ventana_local + 1].min():
                valles.append((i, serie.iloc[i]))
        return valles[-2:] if len(valles) >= 2 else []

    precio_serie = seg["close"]

    # ── Divergencias con RSI ──────────────────────────────────
    rsi_col = "RSI_14"
    if rsi_col in seg.columns and not seg[rsi_col].isna().all():
        rsi_serie = seg[rsi_col].dropna()
        # Alinear por índice posicional
        precio_aligned = precio_serie.iloc[-len(rsi_serie):]

        valles_precio = valles_locales(precio_aligned)
        valles_rsi    = valles_locales(rsi_serie)
        picos_precio  = picos_locales(precio_aligned)
        picos_rsi     = picos_locales(rsi_serie)

        # Divergencia alcista RSI: precio baja, RSI sube en los mínimos
        if len(valles_precio) == 2 and len(valles_rsi) == 2:
            p1_px, p1_v = valles_precio[0][0], valles_precio[0][1]
            p2_px, p2_v = valles_precio[1][0], valles_precio[1][1]
            p1_rsi = valles_rsi[0][1]
            p2_rsi = valles_rsi[1][1]
            # Precio hace mínimo más bajo Y RSI hace mínimo más alto
            if p2_v < p1_v * 0.998 and p2_rsi > p1_rsi * 1.002 and rsi_serie.iloc[-1] < 50:
                resultados.append({
                    "tipo":    "Divergencia alcista (RSI)",
                    "señal":   "BUY",
                    "detalle": f"Precio ↓ ({p1_v:.2f} → {p2_v:.2f})  |  RSI ↑ ({p1_rsi:.1f} → {p2_rsi:.1f})",
                    "fuente":  "Acción del Precio 2018, p.50",
                })

        # Divergencia bajista RSI: precio sube, RSI baja en los máximos
        if len(picos_precio) == 2 and len(picos_rsi) == 2:
            p1_v  = picos_precio[0][1]
            p2_v  = picos_precio[1][1]
            p1_rsi = picos_rsi[0][1]
            p2_rsi = picos_rsi[1][1]
            if p2_v > p1_v * 1.002 and p2_rsi < p1_rsi * 0.998 and rsi_serie.iloc[-1] > 50:
                resultados.append({
                    "tipo":    "Divergencia bajista (RSI)",
                    "señal":   "SELL",
                    "detalle": f"Precio ↑ ({p1_v:.2f} → {p2_v:.2f})  |  RSI ↓ ({p1_rsi:.1f} → {p2_rsi:.1f})",
                    "fuente":  "Acción del Precio 2018, p.50",
                })

    # ── Divergencias con MACD (histograma) ───────────────────
    hist_col = "MACDh_12_26_9"
    if hist_col in seg.columns and not seg[hist_col].isna().all():
        macd_serie = seg[hist_col].dropna()
        precio_aligned = precio_serie.iloc[-len(macd_serie):]

        valles_precio = valles_locales(precio_aligned)
        valles_macd   = valles_locales(macd_serie)
        picos_precio  = picos_locales(precio_aligned)
        picos_macd    = picos_locales(macd_serie)

        # Divergencia alcista MACD
        if len(valles_precio) == 2 and len(valles_macd) == 2:
            p1_v   = valles_precio[0][1]
            p2_v   = valles_precio[1][1]
            p1_m   = valles_macd[0][1]
            p2_m   = valles_macd[1][1]
            if p2_v < p1_v * 0.998 and p2_m > p1_m and p2_m < 0:
                resultados.append({
                    "tipo":    "Divergencia alcista (MACD histograma)",
                    "señal":   "BUY",
                    "detalle": f"Precio ↓ ({p1_v:.2f} → {p2_v:.2f})  |  MACD hist ↑ ({p1_m:.4f} → {p2_m:.4f})",
                    "fuente":  "Acción del Precio 2018, p.50",
                })

        # Divergencia bajista MACD
        if len(picos_precio) == 2 and len(picos_macd) == 2:
            p1_v   = picos_precio[0][1]
            p2_v   = picos_precio[1][1]
            p1_m   = picos_macd[0][1]
            p2_m   = picos_macd[1][1]
            if p2_v > p1_v * 1.002 and p2_m < p1_m and p2_m > 0:
                resultados.append({
                    "tipo":    "Divergencia bajista (MACD histograma)",
                    "señal":   "SELL",
                    "detalle": f"Precio ↑ ({p1_v:.2f} → {p2_v:.2f})  |  MACD hist ↓ ({p1_m:.4f} → {p2_m:.4f})",
                    "fuente":  "Acción del Precio 2018, p.50",
                })

    return resultados


# ─────────────────────────────────────────────
# PATRONES CHARTISTAS (Gallofré, 2014)
# ─────────────────────────────────────────────
def encontrar_maximos_minimos_locales(df, ventana=5):
    """
    Detecta máximos y mínimos locales en la serie de precios.
    Base para el reconocimiento de figuras chartistas.
    (Gallofré, 2014 — principio de soportes y resistencias)
    """
    highs = []
    lows  = []
    for i in range(ventana, len(df) - ventana):
        seg = df["high"].iloc[i - ventana: i + ventana + 1]
        if df["high"].iloc[i] == seg.max():
            highs.append((i, df["high"].iloc[i]))
        seg = df["low"].iloc[i - ventana: i + ventana + 1]
        if df["low"].iloc[i] == seg.min():
            lows.append((i, df["low"].iloc[i]))
    return highs, lows


def detectar_doble_techo(df, highs):
    """
    Doble Techo — Gallofré (2014, p.15)
    Dos máximos similares después de tendencia alcista.
    Proyección bajista = distancia techo-suelo.
    """
    if len(highs) < 2:
        return None
    A_idx, A_val = highs[-2]
    C_idx, C_val = highs[-1]
    if abs(A_val - C_val) / A_val > TOLERANCIA_PATRON:
        return None
    # Verificar que hay tendencia alcista previa (precio subió antes del punto A)
    precio_inicio = df["close"].iloc[max(0, A_idx - 20)]
    if A_val <= precio_inicio * 1.05:
        return None
    # Suelo entre los dos techos
    suelo = df["low"].iloc[A_idx:C_idx].min()
    proyeccion = suelo - (A_val - suelo)
    return {
        "patron": "Doble Techo",
        "señal":  "SELL",
        "techo":   round(A_val, 4),
        "suelo":   round(suelo, 4),
        "objetivo": round(proyeccion, 4),
        "fuente":  "Gallofré 2014, p.15",
    }


def detectar_doble_suelo(df, lows):
    """
    Doble Suelo — Gallofré (2014, p.16)
    Dos mínimos similares después de tendencia bajista.
    Proyección alcista = distancia suelo-techo.
    """
    if len(lows) < 2:
        return None
    A_idx, A_val = lows[-2]
    B_idx, B_val = lows[-1]
    if abs(A_val - B_val) / A_val > TOLERANCIA_PATRON:
        return None
    precio_inicio = df["close"].iloc[max(0, A_idx - 20)]
    if A_val >= precio_inicio * 0.95:
        return None
    techo = df["high"].iloc[A_idx:B_idx].max()
    proyeccion = techo + (techo - A_val)
    return {
        "patron": "Doble Suelo",
        "señal":  "BUY",
        "suelo":   round(A_val, 4),
        "techo":   round(techo, 4),
        "objetivo": round(proyeccion, 4),
        "fuente":  "Gallofré 2014, p.16",
    }


def detectar_hch(df, highs, lows):
    """
    Hombro-Cabeza-Hombro — Gallofré (2014, p.22)
    Tres máximos: hombro izq < cabeza > hombro der (similares entre sí).
    Señal bajista cuando rompe la clavicular.
    """
    if len(highs) < 3:
        return None
    H1_idx, H1 = highs[-3]
    C_idx,  C  = highs[-2]
    H2_idx, H2 = highs[-1]
    # Cabeza debe ser mayor que ambos hombros
    if not (C > H1 and C > H2):
        return None
    # Hombros deben ser similares
    if abs(H1 - H2) / H1 > TOLERANCIA_PATRON * 2:
        return None
    # Clavicular: promedio de los mínimos entre hombros y cabeza
    val1 = df["low"].iloc[H1_idx:C_idx].min()
    val2 = df["low"].iloc[C_idx:H2_idx].min()
    clavicular = (val1 + val2) / 2
    proyeccion = clavicular - (C - clavicular)
    return {
        "patron":     "HCH (Hombro-Cabeza-Hombro)",
        "señal":      "SELL",
        "cabeza":      round(C, 4),
        "clavicular":  round(clavicular, 4),
        "objetivo":    round(proyeccion, 4),
        "fuente":     "Gallofré 2014, p.22",
    }


def detectar_hchi(df, lows, highs):
    """
    HCH Invertido — Gallofré (2014, p.24)
    Tres mínimos: hombro izq > cabeza < hombro der.
    Señal alcista cuando rompe la clavicular.
    """
    if len(lows) < 3:
        return None
    H1_idx, H1 = lows[-3]
    C_idx,  C  = lows[-2]
    H2_idx, H2 = lows[-1]
    if not (C < H1 and C < H2):
        return None
    if abs(H1 - H2) / H1 > TOLERANCIA_PATRON * 2:
        return None
    val1 = df["high"].iloc[H1_idx:C_idx].max()
    val2 = df["high"].iloc[C_idx:H2_idx].max()
    clavicular = (val1 + val2) / 2
    proyeccion = clavicular + (clavicular - C)
    return {
        "patron":     "HCHi (Hombro-Cabeza-Hombro Invertido)",
        "señal":      "BUY",
        "cabeza":      round(C, 4),
        "clavicular":  round(clavicular, 4),
        "objetivo":    round(proyeccion, 4),
        "fuente":     "Gallofré 2014, p.24",
    }


def detectar_triangulo(df, highs, lows):
    """
    Triángulos — Gallofré (2014, p.41-46)
    Simétrico: máximos decrecientes + mínimos crecientes.
    Ascendente: resistencia plana + mínimos crecientes.
    Descendente: soporte plano + máximos decrecientes.
    """
    if len(highs) < 2 or len(lows) < 2:
        return None
    H1_val = highs[-2][1]
    H2_val = highs[-1][1]
    L1_val = lows[-2][1]
    L2_val = lows[-1][1]

    max_decrece = H2_val < H1_val * (1 - 0.005)
    min_crece   = L2_val > L1_val * (1 + 0.005)
    max_plano   = abs(H1_val - H2_val) / H1_val < 0.015
    min_plano   = abs(L1_val - L2_val) / L1_val < 0.015

    if max_decrece and min_crece:
        return {"patron": "Triángulo Simétrico", "señal": "--",
                "nota": "Esperar rotura con volumen para confirmar dirección",
                "fuente": "Gallofré 2014, p.41"}
    elif max_plano and min_crece:
        return {"patron": "Triángulo Ascendente", "señal": "BUY",
                "nota": "Resistencia plana — rotura alcista probable",
                "fuente": "Gallofré 2014, p.44"}
    elif max_decrece and min_plano:
        return {"patron": "Triángulo Descendente", "señal": "SELL",
                "nota": "Soporte plano — rotura bajista probable",
                "fuente": "Gallofré 2014, p.45"}
    return None


def detectar_gaps(df):
    """
    Gaps — Gallofré (2014, p.48-51)
    Gap alcista: open[t] > high[t-1]
    Gap bajista: open[t] < low[t-1]
    Clasifica por tamaño relativo (rotura > 1%, continuación, común).
    """
    gaps = []
    for i in range(1, min(10, len(df))):
        curr_open = df["open"].iloc[-i]
        prev_high = df["high"].iloc[-i - 1]
        prev_low  = df["low"].iloc[-i - 1]
        curr_vol  = df["volume"].iloc[-i]
        avg_vol   = df["volume"].iloc[-20:-i].mean()

        if curr_open > prev_high:
            pct = (curr_open - prev_high) / prev_high * 100
            tipo = "Rotura" if pct > 1.0 else "Continuación" if pct > 0.3 else "Común"
            vol_str = "con volumen elevado" if curr_vol > avg_vol * 1.5 else ""
            gaps.append({
                "tipo":    f"Gap alcista — {tipo} ({pct:.2f}%) {vol_str}",
                "señal":  "BUY" if tipo in ("Rotura", "Continuación") else "--",
                "vela":    i,
                "fuente":  "Gallofré 2014, p.50",
            })
        elif curr_open < prev_low:
            pct = (prev_low - curr_open) / prev_low * 100
            tipo = "Rotura" if pct > 1.0 else "Continuación" if pct > 0.3 else "Común"
            vol_str = "con volumen elevado" if curr_vol > avg_vol * 1.5 else ""
            gaps.append({
                "tipo":    f"Gap bajista — {tipo} ({pct:.2f}%) {vol_str}",
                "señal":  "SELL" if tipo in ("Rotura", "Continuación") else "--",
                "vela":    i,
                "fuente":  "Gallofré 2014, p.50",
            })
    return gaps


def analizar_chartismo(df):
    """Ejecuta todos los detectores de patrones chartistas."""
    highs, lows = encontrar_maximos_minimos_locales(df)
    patrones = []

    dt = detectar_doble_techo(df, highs)
    if dt: patrones.append(dt)

    ds = detectar_doble_suelo(df, lows)
    if ds: patrones.append(ds)

    hch = detectar_hch(df, highs, lows)
    if hch: patrones.append(hch)

    hchi = detectar_hchi(df, lows, highs)
    if hchi: patrones.append(hchi)

    tri = detectar_triangulo(df, highs, lows)
    if tri: patrones.append(tri)

    gaps = detectar_gaps(df)
    patrones.extend(gaps)

    return patrones


# ─────────────────────────────────────────────
# PATRONES ARMÓNICOS XABCD (Sanchez Guillen, 2018)
# ─────────────────────────────────────────────
def detectar_patrones_armonicos(df):
    """
    Detecta patrones armónicos Bat y Gartley sobre los swing points recientes.
    Fuente: Sanchez Guillen, P.A. (2018). Guía para Elaborar Patrones Armónicos.
            Basado en Carney, S.M. (2001). Harmonic Trading.

    Los patrones armónicos son "formaciones geométricas de precios que emplean
    los números de Fibonacci para definir puntos de inflexión precisos."
    (Sanchez Guillen, 2018, p.2)

    Estructura XABCD — 5 puntos de oscilación:
      X → A  :  movimiento impulso inicial
      A → B  :  retroceso de XA
      B → C  :  retroceso de AB (parcial)
      C → D  :  movimiento final donde se toma la operación

    Patrón BAT (Carney, 2001):
      AB = 38.2% – 50.0% de XA
      BC = 38.2% – 88.6% de AB
      CD = 88.6% de XA  (punto de entrada)
      Extensión CD = 161.8% – 261.8% de BC
      Fuente: Sanchez Guillen (2018), p.3-5

    Patrón GARTLEY (Gartley, 1935):
      AB = 61.8% de XA  (ideal)
      BC = 38.2% – 88.6% de AB
      CD = 78.6% de XA  (punto de entrada)
      Extensión CD = 127% – 161.8% de BC
      Fuente: Sanchez Guillen (2018), p.6-9

    Metodología: identifica los 5 swing points más recientes usando los
    máximos y mínimos locales, verifica los ratios Fibonacci con tolerancia
    del 8% para adaptarse a la volatilidad de crypto.
    """
    resultados = []

    if len(df) < 30:
        return resultados

    # Detectar swing points locales (ventana 4 para mayor sensibilidad)
    ventana = 4
    highs_idx = []
    lows_idx  = []
    for i in range(ventana, len(df) - ventana):
        seg_h = df["high"].iloc[i - ventana: i + ventana + 1]
        if df["high"].iloc[i] == seg_h.max():
            highs_idx.append(i)
        seg_l = df["low"].iloc[i - ventana: i + ventana + 1]
        if df["low"].iloc[i] == seg_l.min():
            lows_idx.append(i)

    # Combinar y ordenar todos los swing points por posición
    swings = []
    for i in highs_idx:
        swings.append((i, df["high"].iloc[i], "high"))
    for i in lows_idx:
        swings.append((i, df["low"].iloc[i], "low"))
    swings.sort(key=lambda x: x[0])

    # Filtrar: eliminar swings del mismo tipo consecutivo
    swings_filtrados = []
    for sw in swings:
        if not swings_filtrados or swings_filtrados[-1][2] != sw[2]:
            swings_filtrados.append(sw)
        else:
            # Conservar el más extremo si son del mismo tipo
            prev = swings_filtrados[-1]
            if sw[2] == "high" and sw[1] > prev[1]:
                swings_filtrados[-1] = sw
            elif sw[2] == "low" and sw[1] < prev[1]:
                swings_filtrados[-1] = sw

    # Necesitamos al menos 5 swing points para XABCD
    if len(swings_filtrados) < 5:
        return resultados

    TOLERANCIA = 0.08  # 8% — mayor que en Forex por volatilidad crypto

    def ratio_ok(valor, objetivo, tol=TOLERANCIA):
        """Verifica si un ratio está dentro de la tolerancia."""
        return abs(valor - objetivo) / objetivo <= tol

    def ratio_en_rango(valor, minimo, maximo, tol=TOLERANCIA):
        """Verifica si un ratio está dentro de un rango con tolerancia."""
        return (minimo * (1 - tol)) <= valor <= (maximo * (1 + tol))

    # Iterar sobre los últimos conjuntos de 5 swing points
    for j in range(len(swings_filtrados) - 5, max(-1, len(swings_filtrados) - 9), -1):
        X_idx, X_val, X_tipo = swings_filtrados[j]
        A_idx, A_val, A_tipo = swings_filtrados[j + 1]
        B_idx, B_val, B_tipo = swings_filtrados[j + 2]
        C_idx, C_val, C_tipo = swings_filtrados[j + 3]
        D_idx, D_val, D_tipo = swings_filtrados[j + 4]

        # El patrón requiere alternancia high-low-high-low-high o low-high-low-high-low
        tipos = [X_tipo, A_tipo, B_tipo, C_tipo, D_tipo]
        alternados = all(tipos[i] != tipos[i + 1] for i in range(4))
        if not alternados:
            continue

        XA = abs(A_val - X_val)
        AB = abs(B_val - A_val)
        BC = abs(C_val - B_val)
        CD = abs(D_val - C_val)

        if XA == 0 or AB == 0 or BC == 0:
            continue

        ratio_AB_XA = AB / XA
        ratio_BC_AB = BC / AB
        ratio_CD_XA = CD / XA
        ratio_CD_BC = CD / BC

        # Determinar dirección: alcista si X es low, bajista si X es high
        direccion_alcista = (X_tipo == "low")

        # ── PATRÓN BAT (Carney, 2001) ──
        # Sanchez Guillen (2018), p.3-5
        # AB = 38.2–50% XA, BC = 38.2–88.6% AB, CD = 88.6% XA
        bat_AB = ratio_en_rango(ratio_AB_XA, 0.382, 0.500)
        bat_BC = ratio_en_rango(ratio_BC_AB, 0.382, 0.886)
        bat_CD = ratio_ok(ratio_CD_XA, 0.886)
        bat_CD_ext = ratio_en_rango(ratio_CD_BC, 1.618, 2.618)

        if bat_AB and bat_BC and bat_CD and bat_CD_ext:
            señal = "BUY" if direccion_alcista else "SELL"
            # Objetivos: TP1=38.2% del CD, TP2=61.8% del CD (Sanchez Guillen, p.5)
            if direccion_alcista:
                tp1 = round(D_val + CD * 0.382, 4)
                tp2 = round(D_val + CD * 0.618, 4)
                sl  = round(X_val * 0.995, 4)   # ligeramente bajo X
            else:
                tp1 = round(D_val - CD * 0.382, 4)
                tp2 = round(D_val - CD * 0.618, 4)
                sl  = round(X_val * 1.005, 4)   # ligeramente sobre X

            resultados.append({
                "patron":  f"Patrón Bat {'alcista' if direccion_alcista else 'bajista'} (XABCD)",
                "señal":   señal,
                "fuerza":  "fuerte",
                "detalle": (f"AB/XA={ratio_AB_XA:.3f} (ideal 0.382–0.500)  |  "
                            f"CD/XA={ratio_CD_XA:.3f} (ideal 0.886)"),
                "objetivo_1": tp1,
                "objetivo_2": tp2,
                "stop_loss":  sl,
                "punto_D":    round(D_val, 4),
                "fuente":  "Sanchez Guillen 2018, p.3 / Carney 2001",
            })
            continue  # Bat encontrado, no seguir buscando en este set

        # ── PATRÓN GARTLEY (Gartley, 1935) ──
        # Sanchez Guillen (2018), p.6-9
        # AB = 61.8% XA, BC = 38.2–88.6% AB, CD = 78.6% XA
        gar_AB = ratio_ok(ratio_AB_XA, 0.618)
        gar_BC = ratio_en_rango(ratio_BC_AB, 0.382, 0.886)
        gar_CD = ratio_ok(ratio_CD_XA, 0.786)
        gar_CD_ext = ratio_en_rango(ratio_CD_BC, 1.270, 1.618)

        if gar_AB and gar_BC and gar_CD and gar_CD_ext:
            señal = "BUY" if direccion_alcista else "SELL"
            if direccion_alcista:
                tp1 = round(D_val + CD * 0.382, 4)
                tp2 = round(D_val + CD * 0.618, 4)
                sl  = round(X_val * 0.995, 4)
            else:
                tp1 = round(D_val - CD * 0.382, 4)
                tp2 = round(D_val - CD * 0.618, 4)
                sl  = round(X_val * 1.005, 4)

            resultados.append({
                "patron":  f"Patrón Gartley {'alcista' if direccion_alcista else 'bajista'} (XABCD)",
                "señal":   señal,
                "fuerza":  "fuerte",
                "detalle": (f"AB/XA={ratio_AB_XA:.3f} (ideal 0.618)  |  "
                            f"CD/XA={ratio_CD_XA:.3f} (ideal 0.786)"),
                "objetivo_1": tp1,
                "objetivo_2": tp2,
                "stop_loss":  sl,
                "punto_D":    round(D_val, 4),
                "fuente":  "Sanchez Guillen 2018, p.6 / Gartley 1935",
            })

    return resultados


# ─────────────────────────────────────────────
# SCORE DE CONFLUENCIA
# ─────────────────────────────────────────────
def calcular_score(señales_ind, patrones):
    """
    Genera un score de confluencia 0-100.
    Idea: cuantas más señales apuntan en la misma dirección, mayor es la confianza.
    """
    buy_pts  = 0
    sell_pts = 0
    total    = 0

    peso = {"BUY": 1, "SELL": 1, "--": 0}

    for s, desc, fuente in señales_ind:
        total += 1
        if s == "BUY":  buy_pts  += 1
        if s == "SELL": sell_pts += 1

    for p in patrones:
        señal = p.get("señal", "--")
        if señal == "BUY":  buy_pts  += 2   # patrones chartistas pesan más
        if señal == "SELL": sell_pts += 2
        if señal != "--": total += 2

    if total == 0:
        return 50, "NEUTRO"

    pct_buy  = buy_pts  / total * 100
    pct_sell = sell_pts / total * 100

    if pct_buy > 60:
        return round(pct_buy), "BUY"
    elif pct_sell > 60:
        return round(pct_sell), "SELL"
    else:
        return 50, "NEUTRO"


# ─────────────────────────────────────────────
# NIVELES DE SL / TP  (Wilder ATR, 1978)
# ─────────────────────────────────────────────
def calcular_sl_tp(df, direccion, symbol=""):
    """
    Stop Loss y Take Profit basados en ATR (Wilder, 1978).
    Multiplicador ajustado por volatilidad estructural de cada activo.
    Fuente: Ammous (2019, tabla 10) — BTC ~7x más volátil que fiat,
    ~5x más que oro → SL más amplio para evitar stop hunting.

    SL  = precio ± 1.5 × ATR × multiplicador
    TP1 = precio ± 2.0 × ATR × multiplicador
    TP2 = precio ± 3.0 × ATR × multiplicador
    """
    precio = df["close"].iloc[-1]
    atr_col = "ATRr_14"
    if atr_col not in df.columns:
        return None
    atr = df[atr_col].iloc[-1]
    if pd.isna(atr):
        return None

    base = symbol.split("/")[0].upper() if symbol else "DEFAULT"
    mult = ATR_MULTIPLICADOR_CRYPTO.get(base, ATR_MULTIPLICADOR_CRYPTO["DEFAULT"])

    if direccion == "BUY":
        return {
            "stop_loss":     round(precio - 1.5 * atr * mult, 4),
            "take_profit_1": round(precio + 2.0 * atr * mult, 4),
            "take_profit_2": round(precio + 3.0 * atr * mult, 4),
            "multiplicador": mult,
        }
    elif direccion == "SELL":
        return {
            "stop_loss":     round(precio + 1.5 * atr * mult, 4),
            "take_profit_1": round(precio - 2.0 * atr * mult, 4),
            "take_profit_2": round(precio - 3.0 * atr * mult, 4),
            "multiplicador": mult,
        }
    return None


# ─────────────────────────────────────────────
# ANÁLISIS COMPLETO POR TIMEFRAME
# ─────────────────────────────────────────────
def analizar_timeframe(symbol, timeframe, nombre_horizonte, regimen_data=None):
    df = obtener_velas(symbol, timeframe)
    if df is None or len(df) < 50:
        return

    # Régimen de mercado para mostrar y filtrar señales
    regimen = regimen_data.get("regimen", "INDEFINIDO") if regimen_data else "INDEFINIDO"

    df = calcular_indicadores(df)
    señales_ind  = analizar_indicadores(df, timeframe)
    patrones     = analizar_chartismo(df)
    velas        = detectar_velas_japonesas(df)
    volumen      = analizar_volumen(df)
    divergencias = detectar_divergencias(df)
    armonicos    = detectar_patrones_armonicos(df)
    fib          = calcular_fibonacci(df)
    precio       = df["close"].iloc[-1]

    # Score incluye todas las fuentes de señal
    # Volumen tiene peso 1 (igual que indicadores); OBV divergencia y climax
    # tienen más impacto por ser señales compuestas
    score, dir = calcular_score(
        señales_ind,
        patrones
        + [{"señal": v["señal"]} for v in velas        if v["señal"] != "--"]
        + [{"señal": vol["señal"]} for vol in volumen   if vol["señal"] != "--"]
        + [{"señal": d["señal"]} for d in divergencias  if d["señal"] != "--"]
        + [{"señal": a["señal"]} for a in armonicos      if a["señal"] != "--"]
    )

    # Etiqueta compacta del régimen para mostrar en cada timeframe
    if regimen == "BULL":
        reg_tag = f"{Fore.GREEN}[▲ BULL]{Style.RESET_ALL}"
    elif regimen == "BEAR":
        reg_tag = f"{Fore.RED}[▼ BEAR]{Style.RESET_ALL}"
    elif regimen == "LATERAL":
        reg_tag = f"{Fore.YELLOW}[◆ LATERAL]{Style.RESET_ALL}"
    else:
        reg_tag = f"{Fore.LIGHTBLACK_EX}[? INDEFINIDO]{Style.RESET_ALL}"

    print(f"\n  {Fore.CYAN}[{timeframe.upper()}]  Precio: {precio:,.4f} USDT  {reg_tag}{Style.RESET_ALL}")

    # Indicadores
    if señales_ind:
        print(f"  {Fore.YELLOW}Indicadores técnicos:{Style.RESET_ALL}")
        for s, desc, fuente in señales_ind:
            txt = f"{desc}  ({fuente})"
            if s == "BUY":   señal_buy(txt)
            elif s == "SELL": señal_sell(txt)
            else:             neutro(txt)

    # Velas japonesas
    if velas:
        print(f"  {Fore.YELLOW}Velas japonesas:{Style.RESET_ALL}")
        for v in velas:
            txt = f"{v['patron']}  [fuerza: {v['fuerza']}]  ({v['fuente']})"
            if v["señal"] == "BUY":    señal_buy(txt)
            elif v["señal"] == "SELL": señal_sell(txt)
            else:                       neutro(txt)

    # Chartismo — con etiqueta de régimen en patrones de inversión
    if patrones:
        print(f"  {Fore.YELLOW}Patrones chartistas:{Style.RESET_ALL}")
        for p in patrones:
            nombre = p.get("patron") or p.get("tipo", "Patrón")
            fuente = p.get("fuente", "")
            extra  = ""
            if "objetivo" in p:
                extra = f"  → objetivo {p['objetivo']:,.4f}"
            if "nota" in p:
                extra = f"  — {p['nota']}"
            señal_p = p.get("señal", "--")
            reg_lbl = etiqueta_regimen(señal_p, regimen)
            if señal_p == "BUY":
                señal_buy(f"{nombre}{extra}  ({fuente}){reg_lbl}")
            elif señal_p == "SELL":
                señal_sell(f"{nombre}{extra}  ({fuente}){reg_lbl}")
            else:
                neutro(f"{nombre}{extra}  ({fuente})")

    # Volumen y OBV
    if volumen:
        print(f"  {Fore.YELLOW}Análisis de volumen (OBV + precio/vol):{Style.RESET_ALL}")
        for vol in volumen:
            txt = f"{vol['tipo']}  [fuerza: {vol['fuerza']}]  — {vol['descripcion']}  ({vol['fuente']})"
            if vol["señal"] == "BUY":    señal_buy(txt)
            elif vol["señal"] == "SELL": señal_sell(txt)
            else:                         neutro(txt)

    # Divergencias
    if divergencias:
        print(f"  {Fore.YELLOW}Divergencias precio/oscilador:{Style.RESET_ALL}")
        for d in divergencias:
            txt = f"{d['tipo']}  — {d['detalle']}  ({d['fuente']})"
            if d["señal"] == "BUY":    señal_buy(txt)
            elif d["señal"] == "SELL": señal_sell(txt)
            else:                       neutro(txt)

    # Patrones Armónicos — con etiqueta de régimen destacada
    if armonicos:
        print(f"  {Fore.YELLOW}Patrones armónicos XABCD:{Style.RESET_ALL}")
        for a in armonicos:
            reg_lbl = etiqueta_regimen(a["señal"], regimen)
            txt = (f"{a['patron']}  — {a['detalle']}  |  "
                   f"D={a['punto_D']:,.4f}  "
                   f"TP1={a['objetivo_1']:,.4f}  TP2={a['objetivo_2']:,.4f}  "
                   f"SL={a['stop_loss']:,.4f}  ({a['fuente']}){reg_lbl}")
            if a["señal"] == "BUY":    señal_buy(txt)
            elif a["señal"] == "SELL": señal_sell(txt)
            else:                       neutro(txt)
        info("TP armónico: Fib 38.2% y 61.8% del tramo CD  |  SL bajo/sobre punto X")
        info("Mover SL a entrada al alcanzar TP1  (Sanchez Guillen 2018, p.5)")

    # Fibonacci
    imprimir_fibonacci(fib, precio)

    # Score y SL/TP
    color_score = Fore.GREEN if dir == "BUY" else Fore.RED if dir == "SELL" else Fore.WHITE
    print(f"\n  {color_score}  Score confluencia: {score}/100  →  {dir}{Style.RESET_ALL}")

    if dir in ("BUY", "SELL"):
        niveles = calcular_sl_tp(df, dir, symbol)
        if niveles:
            print(f"  {Fore.LIGHTBLACK_EX}  SL:  {niveles['stop_loss']:,.4f}  |  "
                  f"TP1: {niveles['take_profit_1']:,.4f}  |  "
                  f"TP2: {niveles['take_profit_2']:,.4f}  "
                  f"(ATR×{niveles['multiplicador']} — Wilder 1978 / Ammous 2019){Style.RESET_ALL}")


# ─────────────────────────────────────────────
# MENÚ PRINCIPAL
# ─────────────────────────────────────────────
def menu_seleccion():
    print(f"\n{Fore.CYAN}{'═' * 60}")
    print("  CRYPTO ANALYZER  —  Señales técnicas + chartismo")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'═' * 60}{Style.RESET_ALL}")

    print(f"\n{Fore.YELLOW}  Criptomonedas disponibles:{Style.RESET_ALL}")
    for i, (nombre, symbol) in enumerate(CRYPTOS_DISPONIBLES.items(), 1):
        print(f"    {i}. {nombre} ({symbol})")
    print(f"    {len(CRYPTOS_DISPONIBLES)+1}. Ingresar par personalizado")

    try:
        opcion = int(input(f"\n{Fore.WHITE}  Elegí una opción (1-{len(CRYPTOS_DISPONIBLES)+1}): {Style.RESET_ALL}"))
    except ValueError:
        print(f"{Fore.RED}  Opción inválida.{Style.RESET_ALL}")
        return None, None

    keys = list(CRYPTOS_DISPONIBLES.keys())
    if 1 <= opcion <= len(keys):
        nombre  = keys[opcion - 1]
        symbol  = CRYPTOS_DISPONIBLES[nombre]
    elif opcion == len(keys) + 1:
        symbol = input("  Ingresá el par (ej: DOGE/USDT): ").strip().upper()
        nombre = symbol.split("/")[0]
    else:
        print(f"{Fore.RED}  Opción fuera de rango.{Style.RESET_ALL}")
        return None, None

    print(f"\n{Fore.YELLOW}  Horizonte de análisis:{Style.RESET_ALL}")
    horizontes = list(TIMEFRAMES.keys())
    for i, h in enumerate(horizontes, 1):
        tfs = " / ".join(TIMEFRAMES[h])
        print(f"    {i}. {h.capitalize()}  ({tfs})")
    print(f"    {len(horizontes)+1}. Todos")

    try:
        op_h = int(input(f"\n{Fore.WHITE}  Elegí horizonte (1-{len(horizontes)+1}): {Style.RESET_ALL}"))
    except ValueError:
        return None, None

    if 1 <= op_h <= len(horizontes):
        horizonte = {horizontes[op_h - 1]: TIMEFRAMES[horizontes[op_h - 1]]}
    elif op_h == len(horizontes) + 1:
        horizonte = TIMEFRAMES
    else:
        return None, None

    return symbol, horizonte


def main():
    symbol, horizontes = menu_seleccion()
    if symbol is None:
        return

    titulo(f"ANÁLISIS: {symbol}")
    print(f"  {Fore.LIGHTBLACK_EX}Descargando {VELAS_ANALISIS} velas de Binance (sin API key)...{Style.RESET_ALL}")

    # ── Clasificar régimen de mercado (una sola vez, sobre datos diarios) ──
    print(f"  {Fore.LIGHTBLACK_EX}Clasificando régimen de mercado (datos diarios)...{Style.RESET_ALL}")
    regimen_data = clasificar_regimen(symbol)
    imprimir_regimen(regimen_data)

    # ── Contexto macro Bitcoin (Ammous, 2019) — solo si es BTC ─────────────
    imprimir_contexto_macro(symbol)

    # ── Análisis por timeframe — régimen pasado como contexto ──────────────
    for nombre_h, timeframes in horizontes.items():
        seccion(f"Horizonte: {nombre_h.upper()}")
        for tf in timeframes:
            analizar_timeframe(symbol, tf, nombre_h, regimen_data)

    print(f"\n{Fore.CYAN}{'═' * 60}")
    print("  Bibliografía aplicada:")
    print("   · Gallofré (2014)          — Chartismo: figuras, soportes, gaps")
    print("   · Wilder (1978)            — RSI, ATR, Stop Loss dinámico")
    print("   · Appel (1979)             — MACD, momentum y cruces")
    print("   · Bollinger (2001)         — Bandas, compresión, volatilidad")
    print("   · Murphy (1999)            — EMAs, golden/death cross,")
    print("                                Volumen/OBV: reglas precio-vol, climax, divergencia OBV")
    print("   · Ammous (2019)            — Stock-to-Flow, ciclo halving, volatilidad BTC")
    print("   · IG Group (2023)          — 16 patrones de velas japonesas")
    print("   · Elliott/Fibo             — Retrocesos 38.2%, 61.8%, proyecciones 161.8%")
    print("   · Acción del Precio (2018) — Estocástico, divergencias precio/oscilador")
    print("   · Sanchez Guillen (2018)   — Patrones armónicos Bat y Gartley (XABCD)")
    print(f"{'═' * 60}{Style.RESET_ALL}\n")

    otra = input("  ¿Analizar otra cripto? (s/n): ").strip().lower()
    if otra == "s":
        main()


# ─────────────────────────────────────────────
# VELAS JAPONESAS (IG Group, 2023)
# ─────────────────────────────────────────────
def detectar_velas_japonesas(df):
    """
    Detecta los 16 patrones de velas japonesas más importantes.
    Fuente: IG Group (2023). "16 patrones de velas japonesas que todo inversor debería conocer."

    Cada patrón requiere una tendencia previa para ser válido.
    Las velas más recientes tienen mayor peso en la señal.

    Retorna lista de {"patron", "señal", "fuerza", "fuente"}
    """
    if len(df) < 5:
        return []

    resultados = []

    # Extraemos las últimas 3 velas para detección
    c0 = df.iloc[-1]   # vela actual (más reciente)
    c1 = df.iloc[-2]   # vela anterior
    c2 = df.iloc[-3]   # dos velas atrás

    # Helpers de medidas de velas
    def cuerpo(v):
        return abs(v["close"] - v["open"])

    def sombra_inf(v):
        return min(v["open"], v["close"]) - v["low"]

    def sombra_sup(v):
        return v["high"] - max(v["open"], v["close"])

    def rango_total(v):
        return v["high"] - v["low"]

    def es_alcista(v):
        return v["close"] > v["open"]

    def es_bajista(v):
        return v["close"] < v["open"]

    # Tendencia previa (últimas 5 velas antes de la actual)
    closes_prev = df["close"].iloc[-6:-1]
    tendencia_alcista_previa  = closes_prev.iloc[-1] > closes_prev.iloc[0] * 1.005
    tendencia_bajista_previa  = closes_prev.iloc[-1] < closes_prev.iloc[0] * 0.995

    # ── PATRONES ALCISTAS ────────────────────────────────────────

    # 1. Martillo — IG Group, p.2
    # Cuerpo pequeño, sombra inferior larga (≥2×cuerpo), sombra superior corta, tras tendencia bajista
    if tendencia_bajista_previa:
        cuerpo0 = cuerpo(c0)
        if (cuerpo0 > 0
                and sombra_inf(c0) >= 2 * cuerpo0
                and sombra_sup(c0) <= cuerpo0 * 0.5
                and cuerpo0 <= rango_total(c0) * 0.35):
            fuerza = "fuerte" if es_alcista(c0) else "moderada"
            resultados.append({
                "patron": "Martillo",
                "señal": "BUY",
                "fuerza": fuerza,
                "fuente": "IG Group 2023, p.2",
            })

    # 2. Martillo invertido — IG Group, p.2
    # Cuerpo pequeño, sombra superior larga (≥2×cuerpo), sombra inferior corta, tras tendencia bajista
    if tendencia_bajista_previa:
        cuerpo0 = cuerpo(c0)
        if (cuerpo0 > 0
                and sombra_sup(c0) >= 2 * cuerpo0
                and sombra_inf(c0) <= cuerpo0 * 0.5
                and cuerpo0 <= rango_total(c0) * 0.35):
            resultados.append({
                "patron": "Martillo invertido",
                "señal": "BUY",
                "fuerza": "moderada",
                "fuente": "IG Group 2023, p.2",
            })

    # 3. Envolvente alcista — IG Group, p.3
    # Vela bajista pequeña completamente envuelta por vela alcista grande, tras tendencia bajista
    if (tendencia_bajista_previa
            and es_bajista(c1) and es_alcista(c0)
            and c0["open"] < c1["close"]
            and c0["close"] > c1["open"]
            and cuerpo(c0) > cuerpo(c1) * 1.3):
        resultados.append({
            "patron": "Envolvente alcista",
            "señal": "BUY",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.3",
        })

    # 4. Penetrante — IG Group, p.3
    # Vela roja larga + vela verde que cierra sobre el punto medio de la roja, con gap bajista
    if (tendencia_bajista_previa
            and es_bajista(c1) and es_alcista(c0)
            and c0["open"] < c1["close"]                     # gap bajista en apertura
            and c0["close"] > (c1["open"] + c1["close"]) / 2  # cierra sobre punto medio
            and c0["close"] < c1["open"]):                   # pero no la envuelve del todo
        resultados.append({
            "patron": "Penetrante",
            "señal": "BUY",
            "fuerza": "moderada",
            "fuente": "IG Group 2023, p.3",
        })

    # 5. Estrella de la mañana — IG Group, p.4
    # 3 velas: roja grande | estrella pequeña | verde grande
    if (tendencia_bajista_previa
            and es_bajista(c2) and es_alcista(c0)
            and cuerpo(c1) <= cuerpo(c2) * 0.35          # estrella pequeña
            and cuerpo(c0) >= cuerpo(c2) * 0.6
            and c0["close"] > (c2["open"] + c2["close"]) / 2):
        resultados.append({
            "patron": "Estrella de la mañana",
            "señal": "BUY",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.4",
        })

    # 6. Tres soldados blancos — IG Group, p.4
    # 3 velas alcistas consecutivas con colas cortas y cierres progresivamente más altos
    c3 = df.iloc[-4] if len(df) >= 4 else None
    if (c3 is not None and tendencia_bajista_previa
            and es_alcista(c2) and es_alcista(c1) and es_alcista(c0)
            and c0["close"] > c1["close"] > c2["close"]
            and c0["open"] > c1["open"] and c1["open"] > c2["open"]
            and sombra_sup(c0) <= cuerpo(c0) * 0.3
            and sombra_sup(c1) <= cuerpo(c1) * 0.3):
        resultados.append({
            "patron": "Tres soldados blancos",
            "señal": "BUY",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.4",
        })

    # ── PATRONES BAJISTAS ────────────────────────────────────────

    # 7. Hombre colgado — IG Group, p.5
    # Misma forma que martillo pero al final de tendencia ALCISTA
    if tendencia_alcista_previa:
        cuerpo0 = cuerpo(c0)
        if (cuerpo0 > 0
                and sombra_inf(c0) >= 2 * cuerpo0
                and sombra_sup(c0) <= cuerpo0 * 0.5
                and cuerpo0 <= rango_total(c0) * 0.35):
            resultados.append({
                "patron": "Hombre colgado",
                "señal": "SELL",
                "fuerza": "moderada",
                "fuente": "IG Group 2023, p.5",
            })

    # 8. Estrella fugaz — IG Group, p.5
    # Cuerpo pequeño, sombra superior larga, tras tendencia ALCISTA
    if tendencia_alcista_previa:
        cuerpo0 = cuerpo(c0)
        if (cuerpo0 > 0
                and sombra_sup(c0) >= 2 * cuerpo0
                and sombra_inf(c0) <= cuerpo0 * 0.5
                and cuerpo0 <= rango_total(c0) * 0.35):
            resultados.append({
                "patron": "Estrella fugaz",
                "señal": "SELL",
                "fuerza": "moderada",
                "fuente": "IG Group 2023, p.6",
            })

    # 9. Envolvente bajista — IG Group, p.6
    # Vela verde pequeña envuelta por vela roja grande, tras tendencia ALCISTA
    if (tendencia_alcista_previa
            and es_alcista(c1) and es_bajista(c0)
            and c0["open"] > c1["close"]
            and c0["close"] < c1["open"]
            and cuerpo(c0) > cuerpo(c1) * 1.3):
        resultados.append({
            "patron": "Envolvente bajista",
            "señal": "SELL",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.6",
        })

    # 10. Estrella del atardecer — IG Group, p.6
    # Espejo de estrella de mañana: verde grande | estrella | roja grande
    if (tendencia_alcista_previa
            and es_alcista(c2) and es_bajista(c0)
            and cuerpo(c1) <= cuerpo(c2) * 0.35
            and cuerpo(c0) >= cuerpo(c2) * 0.6
            and c0["close"] < (c2["open"] + c2["close"]) / 2):
        resultados.append({
            "patron": "Estrella del atardecer",
            "señal": "SELL",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.6",
        })

    # 11. Tres cuervos negros — IG Group, p.7
    # 3 velas bajistas consecutivas, cada una abre similar al cierre anterior
    if (tendencia_alcista_previa
            and es_bajista(c2) and es_bajista(c1) and es_bajista(c0)
            and c0["close"] < c1["close"] < c2["close"]
            and sombra_inf(c0) <= cuerpo(c0) * 0.3
            and sombra_inf(c1) <= cuerpo(c1) * 0.3):
        resultados.append({
            "patron": "Tres cuervos negros",
            "señal": "SELL",
            "fuerza": "fuerte",
            "fuente": "IG Group 2023, p.7",
        })

    # 12. Cubierta de nube oscura — IG Group, p.7
    # Vela verde + roja que abre sobre máx. anterior y cierra bajo el punto medio
    if (tendencia_alcista_previa
            and es_alcista(c1) and es_bajista(c0)
            and c0["open"] > c1["high"]                       # abre sobre máximo
            and c0["close"] < (c1["open"] + c1["close"]) / 2  # cierra bajo punto medio
            and c0["close"] > c1["open"]):                    # pero no envuelve
        resultados.append({
            "patron": "Cubierta de nube oscura",
            "señal": "SELL",
            "fuerza": "moderada",
            "fuente": "IG Group 2023, p.7",
        })

    # ── PATRONES DE CONTINUACIÓN / INDECISIÓN ───────────────────

    # 13. Doji — IG Group, p.8
    # Cuerpo casi inexistente (open ≈ close), sombras de cualquier longitud
    cuerpo0 = cuerpo(c0)
    if cuerpo0 <= rango_total(c0) * 0.08 and rango_total(c0) > 0:
        resultados.append({
            "patron": "Doji (indecisión de mercado)",
            "señal": "--",
            "fuerza": "neutra",
            "fuente": "IG Group 2023, p.8",
        })

    # 14. Trompo — IG Group, p.9
    # Cuerpo corto centrado con sombras similares en ambos lados
    if (cuerpo0 > 0
            and cuerpo0 <= rango_total(c0) * 0.3
            and sombra_sup(c0) >= cuerpo0 * 0.5
            and sombra_inf(c0) >= cuerpo0 * 0.5
            and abs(sombra_sup(c0) - sombra_inf(c0)) <= cuerpo0):
        resultados.append({
            "patron": "Trompo (consolidación probable)",
            "señal": "--",
            "fuerza": "neutra",
            "fuente": "IG Group 2023, p.9",
        })

    # 15. Triple formación bajista — IG Group, p.9
    # Vela roja grande | 3 velas verdes pequeñas dentro del rango | vela roja grande
    if len(df) >= 6 and es_bajista(c2):
        c_1 = df.iloc[-4]
        c_2 = df.iloc[-5]
        c_3 = df.iloc[-6]
        if (es_bajista(c_3)
                and es_alcista(c_2) and es_alcista(c_1) and es_alcista(c2)
                and cuerpo(c_2) < cuerpo(c_3) * 0.5
                and cuerpo(c_1) < cuerpo(c_3) * 0.5
                and cuerpo(c2)  < cuerpo(c_3) * 0.5
                and c_2["close"] < c_3["open"]
                and es_bajista(c1)):
            resultados.append({
                "patron": "Triple formación bajista",
                "señal": "SELL",
                "fuerza": "fuerte",
                "fuente": "IG Group 2023, p.9",
            })

    # 16. Triple formación alcista — IG Group, p.10
    # Vela verde grande | 3 velas rojas pequeñas dentro del rango | vela verde grande
    if len(df) >= 6 and es_alcista(c2):
        c_1 = df.iloc[-4]
        c_2 = df.iloc[-5]
        c_3 = df.iloc[-6]
        if (es_alcista(c_3)
                and es_bajista(c_2) and es_bajista(c_1) and es_bajista(c2)
                and cuerpo(c_2) < cuerpo(c_3) * 0.5
                and cuerpo(c_1) < cuerpo(c_3) * 0.5
                and cuerpo(c2)  < cuerpo(c_3) * 0.5
                and c_2["close"] > c_3["open"]
                and es_alcista(c1)):
            resultados.append({
                "patron": "Triple formación alcista",
                "señal": "BUY",
                "fuerza": "fuerte",
                "fuente": "IG Group 2023, p.10",
            })

    return resultados


# ─────────────────────────────────────────────
# NIVELES FIBONACCI (Elliott/Forex-indicators.net)
# ─────────────────────────────────────────────
def calcular_fibonacci(df):
    """
    Calcula retrocesos y proyecciones de Fibonacci sobre el swing reciente.
    Fuente: ElWave / Forex-indicators.net — "Ondas de Elliott y Fibo", p.17

    Ratios de retroceso: 23.6%, 38.2%, 50%, 61.8%, 78.6%
    Ratios de proyección: 100%, 127.2%, 161.8%, 261.8%

    Metodología: detecta el máximo y mínimo de las últimas 50 velas
    como swing high y swing low, luego calcula los niveles Fibonacci
    sobre ese rango.
    """
    ventana = min(50, len(df))
    segmento = df.iloc[-ventana:]

    swing_high = segmento["high"].max()
    swing_low  = segmento["low"].min()
    rango      = swing_high - swing_low
    precio_actual = df["close"].iloc[-1]

    if rango == 0:
        return None

    # Determinar dirección del swing (¿venimos de arriba o de abajo?)
    idx_max = segmento["high"].idxmax()
    idx_min = segmento["low"].idxmin()
    swing_alcista = idx_min < idx_max   # mínimo antes del máximo → swing alcista

    # Niveles de retroceso desde el swing
    retrocesos = {
        "23.6%": round(swing_high - rango * 0.236, 4),
        "38.2%": round(swing_high - rango * 0.382, 4),
        "50.0%": round(swing_high - rango * 0.500, 4),
        "61.8%": round(swing_high - rango * 0.618, 4),
        "78.6%": round(swing_high - rango * 0.786, 4),
    }

    # Proyecciones desde el swing low
    proyecciones = {
        "100.0%":  round(swing_low + rango * 1.000, 4),
        "127.2%":  round(swing_low + rango * 1.272, 4),
        "161.8%":  round(swing_low + rango * 1.618, 4),
        "261.8%":  round(swing_low + rango * 2.618, 4),
    }

    # Nivel de soporte/resistencia más cercano al precio actual
    todos_niveles = list(retrocesos.values()) + list(proyecciones.values())
    nivel_mas_cercano = min(todos_niveles, key=lambda x: abs(x - precio_actual))
    distancia_pct = abs(nivel_mas_cercano - precio_actual) / precio_actual * 100

    return {
        "swing_high":       round(swing_high, 4),
        "swing_low":        round(swing_low, 4),
        "swing_alcista":    swing_alcista,
        "retrocesos":       retrocesos,
        "proyecciones":     proyecciones,
        "nivel_cercano":    nivel_mas_cercano,
        "distancia_pct":    round(distancia_pct, 2),
        "fuente":           "Elliott/Forex-indicators.net, p.17",
    }


def imprimir_fibonacci(fib, precio_actual):
    """Imprime los niveles Fibonacci relevantes."""
    if not fib:
        return

    direccion = "alcista" if fib["swing_alcista"] else "bajista"
    print(f"\n  {Fore.YELLOW}Fibonacci — swing {direccion} "
          f"({fib['swing_low']:,.2f} → {fib['swing_high']:,.2f}):{Style.RESET_ALL}")

    # Retrocesos (soporte en swing alcista, resistencia en bajista)
    for nivel, precio_fib in fib["retrocesos"].items():
        cerca = " ◄ PRECIO AQUÍ" if abs(precio_fib - precio_actual) / precio_actual < 0.005 else ""
        color = Fore.GREEN + Style.BRIGHT if cerca else Fore.LIGHTBLACK_EX
        print(f"  {color}    Ret {nivel}: {precio_fib:,.4f}{cerca}{Style.RESET_ALL}")

    # Proyecciones clave (objetivos de precio)
    for nivel, precio_fib in fib["proyecciones"].items():
        if nivel in ("161.8%", "261.8%"):  # solo las más relevantes
            cerca = " ◄ PRECIO AQUÍ" if abs(precio_fib - precio_actual) / precio_actual < 0.005 else ""
            color = Fore.GREEN + Style.BRIGHT if cerca else Fore.LIGHTBLACK_EX
            print(f"  {color}    Proy {nivel}: {precio_fib:,.4f}{cerca}{Style.RESET_ALL}")

    # Alerta si el precio está en zona Fibonacci (dentro del 2%)
    if fib["distancia_pct"] <= 2.0:
        print(f"  {Fore.YELLOW}  ► ZONA FIBONACCI: precio a {fib['distancia_pct']}% "
              f"del nivel {fib['nivel_cercano']:,.4f}  ({fib['fuente']}){Style.RESET_ALL}")


if __name__ == "__main__":
    main()
