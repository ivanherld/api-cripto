from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Crypto Analyzer API"
    app_version: str = "0.1.0"
    debug: bool = False

    # CORS — ampliar cuando se integre el frontend
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Límites por defecto
    default_candle_limit: int = 200
    max_candle_limit: int = 500


settings = Settings()

# Constantes de dominio (espejo de crypto_analyzer.py para no importar el módulo aquí)
CRYPTOS_DISPONIBLES: dict[str, str] = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "BNB": "BNB/USDT",
    "SOL": "SOL/USDT",
    "XRP": "XRP/USDT",
    "ADA": "ADA/USDT",
}

TIMEFRAMES: dict[str, list[str]] = {
    "scalping":  ["5m",  "15m"],
    "swing":     ["1h",  "4h"],
    "position":  ["1d",  "1w"],
}

ALL_TIMEFRAMES: list[str] = [tf for tfs in TIMEFRAMES.values() for tf in tfs]
