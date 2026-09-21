from app.domain.indicadores_logisticos import (
    IndicadoresRequest,
    IngredienteRef,
    MedicaoDoDia,
    ReceitaMedida,
    calcular_indicadores,
)


def _request(**alteracoes) -> IndicadoresRequest:
    base = {
        "data_referencia": "2026-09-21",
        "inicio_historico": "2026-08-23",
        "turno": "MANHA",
        "quantidade_planejada": 300,
        "consumos_registrados": 91,
        "alunos_unicos": 91,
    }
    return IndicadoresRequest(**{**base, **alteracoes})


def test_aceitacao_e_desperdicio_ficam_indisponiveis_sem_medicao():
    resposta = calcular_indicadores(_request())

    assert resposta.aceitacao.status == "DADOS_INSUFICIENTES"
    assert resposta.aceitacao.nivel == "NAO_AVALIAVEL"
    assert resposta.desperdicio.status == "DADOS_INSUFICIENTES"
    assert resposta.desperdicio.risco == "NAO_AVALIAVEL"
    assert any("Sem medição de sobra lançada" in aviso for aviso in resposta.avisos)


def test_aceitacao_mede_o_que_voltou_no_prato_nao_o_planejamento():
    resposta = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=100, porcoes_servidas=91, sobra_nao_distribuida=9,
        resto_no_prato=13, itens_medidos=5, itens_do_cardapio=5)))

    # 91 servidas, 13 de resto -> 78 consumidas de fato.
    assert resposta.aceitacao.status == "DISPONIVEL"
    assert resposta.aceitacao.percentual == 85.71
    assert resposta.aceitacao.nivel == "MEDIA"
    # Perda = 9 na cuba + 13 no prato sobre 100 preparadas.
    assert resposta.desperdicio.percentual == 22.0
    assert resposta.desperdicio.risco == "ALTO"


def test_desperdicio_baixo_nao_depende_da_diferenca_para_o_planejamento():
    # 300 planejadas contra 91 registradas seria "sobra" enorme, mas o que foi preparado
    # quase todo virou refeicao consumida.
    resposta = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=95, porcoes_servidas=91, sobra_nao_distribuida=4,
        resto_no_prato=2, itens_medidos=5, itens_do_cardapio=5)))

    assert resposta.desperdicio.risco == "BAIXO"
    assert resposta.aceitacao.nivel == "ALTA"


def _receita(nome, ingredientes, servidas, resto, amostra) -> ReceitaMedida:
    return ReceitaMedida(
        receita_id=f"r-{nome}", nome=nome,
        ingredientes=[IngredienteRef(id=f"i-{i}", nome=i) for i in ingredientes],
        porcoes_servidas=servidas, resto_no_prato=resto, amostra=amostra)


def test_compara_pratos_com_o_ingrediente_contra_pratos_sem_ele():
    # Chuchu aparece so em pratos de resto alto. Batata divide a sopa com o chuchu, mas tambem
    # aparece no pure, de resto baixo — o que dilui a heranca sem elimina-la.
    resposta = calcular_indicadores(_request(receitas_medidas=[
        _receita("Chuchu", ["chuchu"], 1000, 300, 60),
        _receita("Sopa de legumes", ["chuchu", "batata"], 1000, 290, 60),
        _receita("Pure de batata", ["batata"], 2000, 100, 120),
        _receita("Arroz branco", ["arroz"], 4000, 200, 200),
    ]))

    assert resposta.ingredientes.status == "DISPONIVEL"
    por_nome = {i.ingrediente: i for i in resposta.ingredientes.acima_da_base}
    assert list(por_nome)[0] == "chuchu"

    chuchu = por_nome["chuchu"]
    # 590 de resto em 2000 servidas com chuchu; 300 em 6000 sem.
    assert chuchu.percentual_resto_com == 29.5
    assert chuchu.percentual_resto_sem == 5.0
    assert chuchu.diferenca_pp == 24.5
    assert chuchu.amostra == 120

    # Batata nao some: ela esta mesmo num prato de resto alto. Mas a coocorrencia deixa de
    # domina-la — 390 em 3000 com batata contra 500 em 5000 sem, ou seja 3,0 pp, uma ordem de
    # grandeza abaixo do chuchu. Agregar por ingrediente em SQL dava 20 pp para os dois.
    assert por_nome["batata"].diferenca_pp == 3.0
    assert chuchu.diferenca_pp > 8 * por_nome["batata"].diferenca_pp


def test_ingrediente_com_amostra_abaixo_do_minimo_fica_de_fora():
    resposta = calcular_indicadores(_request(receitas_medidas=[
        _receita("Acelga refogada", ["acelga"], 100, 90, 5),
        _receita("Arroz branco", ["arroz"], 4000, 200, 200),
    ]))

    nomes = [i.ingrediente for i in resposta.ingredientes.acima_da_base]
    assert "acelga" not in nomes


def test_ingredientes_indisponiveis_sem_medicao_na_janela():
    resposta = calcular_indicadores(_request())

    assert resposta.ingredientes.status == "DADOS_INSUFICIENTES"


def test_cobertura_parcial_do_cardapio_nao_classifica():
    resposta = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=100, porcoes_servidas=91, sobra_nao_distribuida=9,
        resto_no_prato=13, itens_medidos=2, itens_do_cardapio=5)))

    assert resposta.aceitacao.status == "DADOS_INSUFICIENTES"
    assert resposta.aceitacao.nivel == "NAO_AVALIAVEL"
    assert "2 de 5 itens do cardápio" in resposta.aceitacao.motivo
    assert resposta.desperdicio.status == "DADOS_INSUFICIENTES"
    assert "2 de 5 itens do cardápio" in resposta.desperdicio.motivo


def test_volume_abaixo_do_piso_nao_classifica_mesmo_com_cobertura_total():
    # 3 servidas e 1 de resto dariam 66,7% de aceitacao — numero sem significado.
    resposta = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=4, porcoes_servidas=3, sobra_nao_distribuida=1,
        resto_no_prato=1, itens_medidos=2, itens_do_cardapio=2)))

    assert resposta.aceitacao.status == "DADOS_INSUFICIENTES"
    assert "abaixo do mínimo de 30" in resposta.aceitacao.motivo
    assert resposta.desperdicio.status == "DADOS_INSUFICIENTES"


def test_cobertura_total_no_piso_exato_classifica():
    resposta = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=32, porcoes_servidas=30, sobra_nao_distribuida=2,
        resto_no_prato=2, itens_medidos=3, itens_do_cardapio=3)))

    assert resposta.aceitacao.status == "DISPONIVEL"
    assert resposta.aceitacao.nivel == "ALTA"
    assert resposta.desperdicio.status == "DISPONIVEL"
