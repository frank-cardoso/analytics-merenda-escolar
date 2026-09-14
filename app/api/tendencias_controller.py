from fastapi import APIRouter

from app.domain.tendencia_item import (
    TendenciaItemRequest,
    TendenciaItemResponse,
    calcular_tendencias,
)

router = APIRouter(prefix="/api/v1", tags=["tendencias"])


@router.post(
    "/tendencias-item",
    response_model=TendenciaItemResponse,
    response_model_by_alias=True,
)
def criar_tendencias_item(request: TendenciaItemRequest) -> TendenciaItemResponse:
    return calcular_tendencias(request)
