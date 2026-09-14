from fastapi import FastAPI

from app.api.previsoes_controller import router as previsoes_router
from app.api.tendencias_controller import router as tendencias_router

app = FastAPI(
    title="Analytics Merenda Escolar",
    version="0.1.0",
    description="Servico analitico para previsao de demanda e risco de desperdicio.",
)

app.include_router(previsoes_router)
app.include_router(tendencias_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "UP"}
