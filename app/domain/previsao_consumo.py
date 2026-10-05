"""Previsao de demanda. Sem medicao de sobra e resto, desperdicio nao e avaliavel."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ConfiancaPrevisao = Literal["BAIXA", "MEDIA", "ALTA"]
OrigemEstimativa = Literal["MEDIA_HISTORICA", "PISO_REALIZADO", "REALIZADO_SEM_HISTORICO"]

METODO = "baseline-estatistico-v2"

MOTIVO_DESPERDICIO = (
    "Nao ha medicao de sobra nao distribuida nem de resto no prato. A diferenca entre "
    "planejamento e autorizacoes e sobra de planejamento, nao desperdicio de alimento."
)


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
    sobra_de_planejamento: int = Field(alias="sobraDePlanejamento", ge=0)
    historico: list[HistoricoConsumo] = Field(default_factory=list)


class PrevisaoConsumoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    demanda_estimada: int = Field(alias="demandaEstimada")
    media_historica: int | None = Field(alias="mediaHistorica")
    piso_realizado: int = Field(alias="pisoRealizado")
    origem_estimativa: OrigemEstimativa = Field(alias="origemEstimativa")
    diferenca_previsao_planejamento: int = Field(alias="diferencaPrevisaoPlanejamento")
    risco_desperdicio: Literal["NAO_AVALIAVEL"] = Field(alias="riscoDesperdicio")
    desperdicio_motivo: str = Field(alias="desperdicioMotivo")
    confianca: ConfiancaPrevisao
    metodo: str
    evidencias: list[str]


def calcular_previsao(request: PrevisaoConsumoRequest) -> PrevisaoConsumoResponse:
    media_historica = _media_historica(request)
    piso_realizado = request.consumos_autorizados
    demanda_estimada = (
        piso_realizado if media_historica is None else max(media_historica, piso_realizado)
    )

    return PrevisaoConsumoResponse(
        demanda_estimada=demanda_estimada,
        media_historica=media_historica,
        piso_realizado=piso_realizado,
        origem_estimativa=_origem(media_historica, piso_realizado),
        diferenca_previsao_planejamento=demanda_estimada - request.quantidade_planejada,
        risco_desperdicio="NAO_AVALIAVEL",
        desperdicio_motivo=MOTIVO_DESPERDICIO,
        confianca=_classificar_confianca(request),
        metodo=METODO,
        evidencias=_montar_evidencias(request, media_historica, piso_realizado),
    )


def _media_historica(request: PrevisaoConsumoRequest) -> int | None:
    if not request.historico:
        return None

    total = sum(item.consumos_autorizados for item in request.historico)
    return round(total / len(request.historico))


# A media historica cobre dias inteiros, mas o dia de hoje ja tem catraca rodada: prever abaixo
# do que ja aconteceu e impossivel. O realizado entra como piso, nunca como teto.
def _origem(media_historica: int | None, piso_realizado: int) -> OrigemEstimativa:
    if media_historica is None:
        return "REALIZADO_SEM_HISTORICO"
    return "MEDIA_HISTORICA" if media_historica >= piso_realizado else "PISO_REALIZADO"


def _classificar_confianca(request: PrevisaoConsumoRequest) -> ConfiancaPrevisao:
    tamanho_historico = len(request.historico)
    if tamanho_historico >= 7:
        return "ALTA"
    if tamanho_historico >= 3:
        return "MEDIA"
    return "BAIXA"


def _montar_evidencias(
    request: PrevisaoConsumoRequest,
    media_historica: int | None,
    piso_realizado: int,
) -> list[str]:
    evidencias = [
        f"Foram autorizados {request.consumos_autorizados} consumos de "
        f"{request.quantidade_planejada} refeicoes planejadas.",
        f"A sobra de planejamento informada pela API Java foi de {request.sobra_de_planejamento} "
        f"refeicoes; e diferenca de planejamento, nao desperdicio medido.",
    ]

    if media_historica is None:
        evidencias.append("Historico insuficiente; a estimativa e o proprio realizado do dia.")
    else:
        evidencias.append(
            f"A media de {len(request.historico)} registros historicos "
            f"foi {media_historica} consumos."
        )
        if media_historica < piso_realizado:
            evidencias.append(
                f"A media historica ({media_historica}) ficou abaixo do realizado do dia "
                f"({piso_realizado}); a estimativa usa o realizado como piso."
            )

    if request.tentativas_bloqueadas:
        evidencias.append(
            f"Houve {request.tentativas_bloqueadas} tentativas bloqueadas no periodo."
        )

    return evidencias
