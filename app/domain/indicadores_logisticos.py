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


class MedicaoDoDia(Contrato):
    porcoes_preparadas: int = Field(ge=0)
    porcoes_servidas: int = Field(ge=0)
    sobra_nao_distribuida: int = Field(ge=0)
    resto_no_prato: int = Field(ge=0)
    itens_medidos: int = Field(ge=0)
    itens_do_cardapio: int = Field(ge=0)

    @model_validator(mode="after")
    def validar(self) -> Self:
        if self.porcoes_servidas + self.sobra_nao_distribuida != self.porcoes_preparadas:
            raise ValueError("Preparadas deve ser a soma de servidas e sobra não distribuída")
        if self.resto_no_prato > self.porcoes_servidas:
            raise ValueError("Resto no prato não pode superar o que foi servido")
        if self.itens_medidos > self.itens_do_cardapio:
            raise ValueError("Itens medidos não podem superar os itens do cardápio")
        return self

    @property
    def cobertura_completa(self) -> bool:
        return self.itens_do_cardapio > 0 and self.itens_medidos == self.itens_do_cardapio


class IngredienteRef(Contrato):
    id: str = Field(min_length=1, max_length=64)
    nome: str = Field(min_length=1, max_length=80)


class ReceitaMedida(Contrato):
    """Uma receita medida na janela, com a composição dela.

    O serviço recebe o grafo no pedido e não conhece tabela de ingrediente nenhuma. É isso que
    permite plugar em outra base sem mudar nada aqui.
    """

    receita_id: str = Field(min_length=1, max_length=64)
    nome: str = Field(min_length=1, max_length=120)
    ingredientes: list[IngredienteRef] = Field(default_factory=list)
    porcoes_servidas: int = Field(ge=0)
    resto_no_prato: int = Field(ge=0)
    amostra: int = Field(ge=0)

    @model_validator(mode="after")
    def validar(self) -> Self:
        if self.resto_no_prato > self.porcoes_servidas:
            raise ValueError("Resto no prato não pode superar o que foi servido")
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
    medicao_do_dia: MedicaoDoDia | None = None
    receitas_medidas: list[ReceitaMedida] = Field(default_factory=list)

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


# Faixas de convencao do prototipo, nao medidas em producao. Ficam nomeadas para que quem
# discordar saiba onde mexer, em vez de encontrar o numero solto no meio de um if.
ACEITACAO_ALTA = Decimal(90)
ACEITACAO_MEDIA = Decimal(75)
DESPERDICIO_BAIXO = Decimal(10)
DESPERDICIO_MEDIO = Decimal(20)

# Abaixo disso a media do ingrediente oscila demais para sustentar qualquer afirmacao.
AMOSTRA_MINIMA_INGREDIENTE = 30

# A conclusão determinística cita os três primeiros; mandar dez ao modelo é janela de contexto
# gasta com ingredientes que ninguém vai mencionar.
INGREDIENTES_NO_RANKING = 3

# Mesmo piso para o dia: com poucas porcoes a taxa vira ruido (3 servidas e 1 de resto dao 66,7%,
# um numero que existe e nao significa nada).
PORCOES_MINIMAS_DIA = 30


class Aceitacao(Contrato):
    """Aceitação medida pelo que voltou no prato. Não é execução do planejamento."""
    status: Literal["DISPONIVEL", "DADOS_INSUFICIENTES"]
    nivel: Literal["ALTA", "MEDIA", "BAIXA", "NAO_AVALIAVEL"]
    percentual: float | None = None
    porcoes_servidas: int | None = None
    resto_no_prato: int | None = None
    motivo: str | None = None


class Desperdicio(Contrato):
    """Perda sobre o que foi preparado: sobra na cuba mais resto no prato."""
    status: Literal["DISPONIVEL", "DADOS_INSUFICIENTES"]
    risco: Literal["ALTO", "MEDIO", "BAIXO", "NAO_AVALIAVEL"]
    percentual: float | None = None
    porcoes_preparadas: int | None = None
    sobra_nao_distribuida: int | None = None
    resto_no_prato: int | None = None
    motivo: str | None = None


class IngredienteResto(Contrato):
    ingrediente_id: str
    ingrediente: str
    amostra: int
    percentual_resto_com: float
    percentual_resto_sem: float | None
    diferenca_pp: float


class AnaliseIngredientes(Contrato):
    status: Literal["DISPONIVEL", "DADOS_INSUFICIENTES"]
    base_percentual_resto: float | None = None
    acima_da_base: list[IngredienteResto] = Field(default_factory=list)
    motivo: str | None = None


class AnaliseIndisponivel(Contrato):
    status: str = "DADOS_INSUFICIENTES"
    motivo: str
    ciclo_sugerido_dias: int | None = None


class IndicadoresResponse(Contrato):
    schema_version: str = "3"
    calculo_versao: str = "indicadores-v1"
    status: str = "DISPONIVEL"
    data_referencia: date
    inicio_historico: date
    turno: str
    execucao_planejamento: ExecucaoPlanejamento
    atendimentos: Atendimentos
    top_comidas: list[ItemRanking]
    por_turma: list[TurmaIndicadores]
    aceitacao: Aceitacao
    desperdicio: Desperdicio
    ingredientes: AnaliseIngredientes
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
        "QR Code representa autorização registrada, não comprovação de ingestão ou desperdício; "
        "aceitação e desperdício vêm da medição de sobra, não da fila.",
        "Adesão por turma não avaliável sem presença; bloqueios não representam rejeição.",
    ]
    if request.medicao_do_dia is None:
        avisos.append("Sem medição de sobra lançada para este dia e turno: aceitação e "
                      "desperdício ficam indisponíveis até alguém registrar.")
    else:
        medicao = request.medicao_do_dia
        avisos.append(f"Medição de sobra cobre {medicao.itens_medidos} de "
                      f"{medicao.itens_do_cardapio} itens do cardápio.")
    if request.receitas_medidas:
        avisos.append(f"Análise de ingrediente sobre {len(request.receitas_medidas)} receitas "
                      f"medidas na janela; o resto é medido por prato inteiro, então "
                      f"ingredientes servidos juntos dividem o mesmo número.")
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
        aceitacao=_calcular_aceitacao(request.medicao_do_dia),
        desperdicio=_calcular_desperdicio(request.medicao_do_dia),
        ingredientes=_analisar_ingredientes(request.receitas_medidas),
        rotacao_cardapio=AnaliseIndisponivel(
            motivo="Faltam séries de oferta e adesão comparáveis para recomendar um ciclo."
        ),
        avisos=avisos,
    )


def _base_insuficiente(medicao: MedicaoDoDia, denominador: int) -> str | None:
    """Motivo pelo qual o dia não pode ser classificado, ou None quando pode.

    Cobertura parcial é recusada de propósito: aceitação de um prato não é aceitação do cardápio,
    e o card do painel mostra só o rótulo — quem olha não vê que faltaram três itens.
    """
    if not medicao.cobertura_completa:
        return (f"Medição cobre {medicao.itens_medidos} de {medicao.itens_do_cardapio} itens do "
                f"cardápio. O indicador é do cardápio inteiro, não de parte dele.")
    if denominador < PORCOES_MINIMAS_DIA:
        return (f"Apenas {denominador} porções no denominador, abaixo do mínimo de "
                f"{PORCOES_MINIMAS_DIA} para classificar.")
    return None


def _calcular_aceitacao(medicao: MedicaoDoDia | None) -> Aceitacao:
    if medicao is None or medicao.porcoes_servidas == 0:
        return Aceitacao(
            status="DADOS_INSUFICIENTES", nivel="NAO_AVALIAVEL",
            motivo="Sem medição de resto no prato para este dia e turno. "
                   "Autorização na fila não comprova ingestão.",
        )

    impedimento = _base_insuficiente(medicao, medicao.porcoes_servidas)
    if impedimento:
        return Aceitacao(status="DADOS_INSUFICIENTES", nivel="NAO_AVALIAVEL", motivo=impedimento)

    consumido = Decimal(medicao.porcoes_servidas - medicao.resto_no_prato)
    taxa = consumido * 100 / medicao.porcoes_servidas
    nivel = ("ALTA" if taxa >= ACEITACAO_ALTA
             else "MEDIA" if taxa >= ACEITACAO_MEDIA else "BAIXA")
    return Aceitacao(
        status="DISPONIVEL", nivel=nivel, percentual=_arredondar(taxa),
        porcoes_servidas=medicao.porcoes_servidas, resto_no_prato=medicao.resto_no_prato,
        motivo="Medido sobre o que foi servido: porções servidas menos resto devolvido.",
    )


def _calcular_desperdicio(medicao: MedicaoDoDia | None) -> Desperdicio:
    if medicao is None or medicao.porcoes_preparadas == 0:
        return Desperdicio(
            status="DADOS_INSUFICIENTES", risco="NAO_AVALIAVEL",
            motivo="Sem medição de sobra não distribuída e resto no prato. Diferença entre "
                   "planejamento e autorizações é sobra de planejamento, não desperdício.",
        )

    impedimento = _base_insuficiente(medicao, medicao.porcoes_preparadas)
    if impedimento:
        return Desperdicio(status="DADOS_INSUFICIENTES", risco="NAO_AVALIAVEL", motivo=impedimento)

    perda = Decimal(medicao.sobra_nao_distribuida + medicao.resto_no_prato)
    taxa = perda * 100 / medicao.porcoes_preparadas
    risco = ("BAIXO" if taxa <= DESPERDICIO_BAIXO
             else "MEDIO" if taxa <= DESPERDICIO_MEDIO else "ALTO")
    return Desperdicio(
        status="DISPONIVEL", risco=risco, percentual=_arredondar(taxa),
        porcoes_preparadas=medicao.porcoes_preparadas,
        sobra_nao_distribuida=medicao.sobra_nao_distribuida,
        resto_no_prato=medicao.resto_no_prato,
        motivo="Perda sobre o preparado: sobra na cuba mais resto no prato.",
    )


def _analisar_ingredientes(receitas: list[ReceitaMedida]) -> AnaliseIngredientes:
    """Compara o resto dos pratos que levam o ingrediente contra os que não levam.

    A média isolada do ingrediente engana quando ele coocorre com outro: batata aparece na sopa de
    legumes ao lado do chuchu e herda a rejeição dele. A comparação presença × ausência dilui essa
    herança, porque batata também aparece em pratos onde o chuchu não está.

    Segue sendo associação: o resto é medido por prato inteiro, nunca por colherada.
    """
    medidas = [r for r in receitas if r.porcoes_servidas > 0]
    if not medidas:
        return AnaliseIngredientes(
            status="DADOS_INSUFICIENTES",
            motivo="Sem medições de resto no prato na janela.",
        )

    servidas_total = sum(r.porcoes_servidas for r in medidas)
    resto_total = sum(r.resto_no_prato for r in medidas)
    base_taxa = Decimal(resto_total) * 100 / servidas_total

    nomes = {ing.id: ing.nome for r in medidas for ing in r.ingredientes}
    acima = []
    for ingrediente_id, nome in nomes.items():
        com = [r for r in medidas if any(i.id == ingrediente_id for i in r.ingredientes)]
        sem = [r for r in medidas if all(i.id != ingrediente_id for i in r.ingredientes)]

        amostra = sum(r.amostra for r in com)
        servidas_com = sum(r.porcoes_servidas for r in com)
        if amostra < AMOSTRA_MINIMA_INGREDIENTE or servidas_com == 0:
            continue

        taxa_com = Decimal(sum(r.resto_no_prato for r in com)) * 100 / servidas_com
        servidas_sem = sum(r.porcoes_servidas for r in sem)
        taxa_sem = (
            Decimal(sum(r.resto_no_prato for r in sem)) * 100 / servidas_sem
            if servidas_sem else None
        )
        # Sem contraponto não há comparação; a diferença cai para a base global.
        referencia = base_taxa if taxa_sem is None else taxa_sem
        if taxa_com <= referencia:
            continue

        acima.append(IngredienteResto(
            ingrediente_id=ingrediente_id, ingrediente=nome, amostra=amostra,
            percentual_resto_com=_arredondar(taxa_com),
            percentual_resto_sem=_arredondar(taxa_sem),
            diferenca_pp=_arredondar(taxa_com - referencia),
        ))

    acima.sort(key=lambda i: -i.diferenca_pp)
    if not acima:
        return AnaliseIngredientes(
            status="DISPONIVEL", base_percentual_resto=_arredondar(base_taxa),
            motivo=f"Nenhum ingrediente ficou acima dos pratos sem ele com amostra mínima de "
                   f"{AMOSTRA_MINIMA_INGREDIENTE} medições.",
        )

    return AnaliseIngredientes(
        status="DISPONIVEL", base_percentual_resto=_arredondar(base_taxa),
        acima_da_base=acima[:INGREDIENTES_NO_RANKING],
        motivo="Resto dos pratos com o ingrediente contra os pratos sem ele; associação "
               "observada, não causa comprovada.",
    )


def _arredondar(valor: Decimal | None) -> float | None:
    if valor is None:
        return None
    return float(valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
