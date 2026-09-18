"""Indicadores explicáveis. Execução registrada não mede preferência alimentar."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class Contrato(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ContagemTurma(Contrato):
    turma: str = Field(min_length=1, max_length=80)
    consumos_registrados: int = Field(ge=0)
    alunos_unicos: int = Field(ge=0)

    @model_validator(mode="after")
    def validar_contagens(self) -> Self:
        if self.alunos_unicos > self.consumos_registrados:
            raise ValueError("Alunos únicos não podem superar consumos registrados")
        return self


class ContagemItem(Contrato):
    item: str = Field(min_length=1, max_length=120)
    planejamentos: int = Field(ge=1)
    execucoes_registradas: int = Field(ge=0)
    escolas: int = Field(ge=1)
    origens: list[str]

    @model_validator(mode="after")
    def validar_execucoes(self) -> Self:
        if self.execucoes_registradas > self.planejamentos:
            raise ValueError("Execuções não podem superar planejamentos")
        return self


class IndicadoresRequest(Contrato):
    data_referencia: date
    inicio_historico: date
    turno: Literal["MANHA", "TARDE", "NOITE", "INTEGRAL"]
    quantidade_planejada: int = Field(ge=0)
    consumos_registrados: int = Field(ge=0)
    alunos_unicos: int = Field(ge=0)
    meta_percentual: float = Field(default=80, ge=0, le=100, allow_inf_nan=False)
    turmas: list[ContagemTurma] = Field(default_factory=list)
    itens: list[ContagemItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar(self) -> Self:
        if self.inicio_historico > self.data_referencia:
            raise ValueError("Período histórico invertido")
        if self.alunos_unicos > self.consumos_registrados:
            raise ValueError("Alunos únicos não podem superar consumos registrados")
        return self


class ExecucaoPlanejamento(Contrato):
    refeicoes_planejadas: int
    consumos_registrados: int
    percentual: float | None
    meta_percentual: float
    diferenca_meta_pp: float | None
    status_meta: Literal["ATINGIDA", "ABAIXO", "NAO_AVALIAVEL"]


class Atendimentos(Contrato):
    alunos_unicos: int
    repeticoes: int


class ItemRanking(ContagemItem):
    metrica: str = "EXECUCAO_REGISTRADA"
    percentual: float


class TurmaIndicadores(ContagemTurma):
    repeticoes: int
    percentual: float | None = None
    status_meta: str = "NAO_AVALIAVEL"
    motivo: str = "Sem registro de presença elegível; turma atual do cadastro do aluno."


class AnaliseIndisponivel(Contrato):
    status: str = "DADOS_INSUFICIENTES"
    motivo: str
    ciclo_sugerido_dias: int | None = None


class IndicadoresResponse(Contrato):
    schema_version: str = "2"
    calculo_versao: str = "indicadores-v1"
    status: str = "DISPONIVEL"
    data_referencia: date
    inicio_historico: date
    turno: str
    execucao_planejamento: ExecucaoPlanejamento
    atendimentos: Atendimentos
    top_comidas: list[ItemRanking]
    por_turma: list[TurmaIndicadores]
    ingredientes: AnaliseIndisponivel
    rotacao_cardapio: AnaliseIndisponivel
    avisos: list[str]


def calcular_indicadores(request: IndicadoresRequest) -> IndicadoresResponse:
    taxa = (
        Decimal(request.consumos_registrados) * 100 / request.quantidade_planejada
        if request.quantidade_planejada else None
    )
    meta = Decimal(str(request.meta_percentual))
    # Comparar antes de arredondar: 79,999% não atinge uma meta de 80%.
    status = "NAO_AVALIAVEL" if taxa is None else "ATINGIDA" if taxa >= meta else "ABAIXO"
    ranking = sorted(
        (item for item in request.itens if item.planejamentos >= 5),
        key=lambda item: (-Decimal(item.execucoes_registradas) / item.planejamentos,
                          -item.planejamentos, item.item),
    )[:10]
    avisos = [
        "Meta interna de execução do planejamento; não é medida de aceitação alimentar.",
        "Ranking histórico por item: execução registrada inclui quantidade zero; "
        "ausência de registro não comprova rejeição. Mínimo de 5 planejamentos por item.",
        "O ranking pode agregar várias escolas e origens; não representa apenas a fila local.",
        "QR Code representa autorização registrada, não comprovação de ingestão ou desperdício.",
        "Adesão por turma não avaliável sem presença; bloqueios não representam rejeição.",
    ]
    origens = sorted({origem for item in request.itens for origem in item.origens})
    if origens:
        avisos.append("Origens do histórico: " + ", ".join(origens) + ".")
    if not ranking:
        avisos.append("Sem itens com amostra suficiente para o ranking neste período.")
    return IndicadoresResponse(
        data_referencia=request.data_referencia,
        inicio_historico=request.inicio_historico,
        turno=request.turno,
        execucao_planejamento=ExecucaoPlanejamento(
            refeicoes_planejadas=request.quantidade_planejada,
            consumos_registrados=request.consumos_registrados,
            percentual=_arredondar(taxa), meta_percentual=request.meta_percentual,
            diferenca_meta_pp=_arredondar(taxa - meta) if taxa is not None else None,
            status_meta=status,
        ),
        atendimentos=Atendimentos(
            alunos_unicos=request.alunos_unicos,
            repeticoes=request.consumos_registrados - request.alunos_unicos,
        ),
        top_comidas=[ItemRanking(
            **item.model_dump(),
            percentual=_arredondar(Decimal(item.execucoes_registradas) * 100 / item.planejamentos),
        ) for item in ranking],
        por_turma=[TurmaIndicadores(
            **turma.model_dump(), repeticoes=turma.consumos_registrados - turma.alunos_unicos,
        ) for turma in request.turmas],
        ingredientes=AnaliseIndisponivel(
            motivo="Faltam composição padronizada das receitas e grupos comparáveis."
        ),
        rotacao_cardapio=AnaliseIndisponivel(
            motivo="Faltam séries de oferta e adesão comparáveis para recomendar um ciclo."
        ),
        avisos=avisos,
    )


def _arredondar(valor: Decimal | None) -> float | None:
    if valor is None:
        return None
    return float(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
