from fastapi import APIRouter

from app.domain.previsao_consumo import (
    PrevisaoConsumoRequest,
    PrevisaoConsumoResponse,
    calcular_previsao,
)

router = APIRouter(prefix="/api/v1", tags=["previsoes"])


@router.post(
    "/previsoes-consumo",
    response_model=PrevisaoConsumoResponse,
    response_model_by_alias=True,
)
def criar_previsao_consumo(request: PrevisaoConsumoRequest) -> PrevisaoConsumoResponse:
    return calcular_previsao(request)
