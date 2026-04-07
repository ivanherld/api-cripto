from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.routers import analysis, market

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de análisis técnico sobre datos de Binance. "
        "Régimen bull/bear, indicadores, patrones chartistas, "
        "velas japonesas, armónicos, divergencias, Fibonacci y SL/TP."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router,   prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
