from fastapi import APIRouter

from app.domain.indicadores_logisticos import (
    IndicadoresRequest,
    IndicadoresResponse,
    calcular_indicadores,
)

router = APIRouter(prefix="/api/v1", tags=["indicadores"])


@router.post("/indicadores-logisticos", response_model=IndicadoresResponse)
def indicadores(request: IndicadoresRequest) -> IndicadoresResponse:
    return calcular_indicadores(request)
