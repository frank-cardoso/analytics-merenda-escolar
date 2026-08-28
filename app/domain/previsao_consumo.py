from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiscoDesperdicio = Literal["BAIXO", "MEDIO", "ALTO"]
ConfiancaPrevisao = Literal["BAIXA", "MEDIA", "ALTA"]


class HistoricoConsumo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data_referencia: str = Field(alias="dataReferencia")
    consumos_autorizados: int = Field(alias="consumosAutorizados", ge=0)


class PrevisaoConsumoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data_referencia: str = Field(alias="dataReferencia")
    turno: str
    cardapio: str
    quantidade_planejada: int = Field(alias="quantidadePlanejada", ge=0)
    consumos_autorizados: int = Field(alias="consumosAutorizados", ge=0)
    tentativas_bloqueadas: int = Field(alias="tentativasBloqueadas", ge=0)
    taxa_consumo_planejado: float = Field(alias="taxaConsumoPlanejado", ge=0)
    sobra_estimada: int = Field(alias="sobraEstimada", ge=0)
    historico: list[HistoricoConsumo] = Field(default_factory=list)


class PrevisaoConsumoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    demanda_estimada: int = Field(alias="demandaEstimada")
    ajuste_sugerido: int = Field(alias="ajusteSugerido")
    risco_desperdicio: RiscoDesperdicio = Field(alias="riscoDesperdicio")
    confianca: ConfiancaPrevisao
    metodo: str
    evidencias: list[str]


def calcular_previsao(request: PrevisaoConsumoRequest) -> PrevisaoConsumoResponse:
    demanda_estimada = _estimar_demanda(request)
    ajuste_sugerido = demanda_estimada - request.quantidade_planejada

    return PrevisaoConsumoResponse(
        demanda_estimada=demanda_estimada,
        ajuste_sugerido=ajuste_sugerido,
        risco_desperdicio=_classificar_risco(request, demanda_estimada),
        confianca=_classificar_confianca(request),
        metodo="baseline-estatistico-v1",
        evidencias=_montar_evidencias(request),
    )


def _estimar_demanda(request: PrevisaoConsumoRequest) -> int:
    if not request.historico:
        return request.consumos_autorizados

    total = sum(item.consumos_autorizados for item in request.historico)
    return round(total / len(request.historico))


def _classificar_risco(
    request: PrevisaoConsumoRequest,
    demanda_estimada: int,
) -> RiscoDesperdicio:
    if request.quantidade_planejada == 0:
        return "BAIXO"

    proporcao_demanda = demanda_estimada / request.quantidade_planejada
    if proporcao_demanda < 0.6:
        return "ALTO"
    if proporcao_demanda < 0.85:
        return "MEDIO"
    return "BAIXO"


def _classificar_confianca(request: PrevisaoConsumoRequest) -> ConfiancaPrevisao:
    tamanho_historico = len(request.historico)
    if tamanho_historico >= 7:
        return "ALTA"
    if tamanho_historico >= 3:
        return "MEDIA"
    return "BAIXA"


def _montar_evidencias(request: PrevisaoConsumoRequest) -> list[str]:
    evidencias = [
        f"Foram autorizados {request.consumos_autorizados} consumos de "
        f"{request.quantidade_planejada} refeicoes planejadas.",
        f"A sobra estimada informada pela API Java foi de {request.sobra_estimada} refeicoes.",
    ]

    if request.historico:
        evidencias.append(
            f"A previsao usou {len(request.historico)} registros historicos agregados."
        )
    else:
        evidencias.append("Historico insuficiente; previsao baseada no consumo atual.")

    if request.tentativas_bloqueadas:
        evidencias.append(
            f"Houve {request.tentativas_bloqueadas} tentativas bloqueadas no periodo."
        )

    return evidencias
