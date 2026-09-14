from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TendenciaConsumo = Literal["QUEDA", "ESTAVEL", "ALTA"]

# Variacao minima, em pontos percentuais, entre a primeira e a segunda metade da serie para
# classificar como QUEDA ou ALTA em vez de ESTAVEL. Mesmo espirito dos limiares de
# _classificar_risco em previsao_consumo.py: heuristica inicial, ajustavel com mais dado real.
LIMIAR_VARIACAO_PP = 5.0


class SerieItemConsumo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item: str
    taxas_execucao: list[float] = Field(alias="taxasExecucao")


class TendenciaItemRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    itens: list[SerieItemConsumo]


class TendenciaItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item: str
    tendencia: TendenciaConsumo


class TendenciaItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tendencias: list[TendenciaItem]


def calcular_tendencias(request: TendenciaItemRequest) -> TendenciaItemResponse:
    return TendenciaItemResponse(
        tendencias=[
            TendenciaItem(item=serie.item, tendencia=_classificar_tendencia(serie.taxas_execucao))
            for serie in request.itens
        ]
    )


def _classificar_tendencia(taxas_execucao: list[float]) -> TendenciaConsumo:
    if len(taxas_execucao) < 2:
        return "ESTAVEL"

    metade = len(taxas_execucao) // 2
    primeira_metade = taxas_execucao[:metade]
    segunda_metade = taxas_execucao[metade:]
    diferenca = _media(segunda_metade) - _media(primeira_metade)

    if diferenca <= -LIMIAR_VARIACAO_PP:
        return "QUEDA"
    if diferenca >= LIMIAR_VARIACAO_PP:
        return "ALTA"
    return "ESTAVEL"


def _media(valores: list[float]) -> float:
    return sum(valores) / len(valores)
