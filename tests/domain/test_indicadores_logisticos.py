from app.domain.indicadores_logisticos import (
    ContagemTurma,
    IndicadoresRequest,
    IngredienteRef,
    MedicaoDoDia,
    ReceitaFechamento,
    ReceitaMedida,
    AtendimentoDia,
    calcular_indicadores,
)


def _request(**alteracoes) -> IndicadoresRequest:
    base = {
        "data_referencia": "2026-09-21",
        "inicio_historico": "2026-08-23",
        "refeicao": {"id": "5e1a0000-0000-4000-8000-000000000002", "nome": "Lanche da manhã"},
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


def test_aceitacao_dos_itens_agrega_fechamentos_da_merendeira():
    resposta = calcular_indicadores(_request(fechamentos_do_mes=[
        ReceitaFechamento(
            receita_id="00000000-0000-0000-0000-000000000001", nome="Arroz branco",
            porcoes_preparadas=100, porcoes_servidas=80, sobra_nao_distribuida=20,
            resto_no_prato=8, fechamentos=1),
        ReceitaFechamento(
            receita_id="00000000-0000-0000-0000-000000000001", nome="Arroz branco",
            porcoes_preparadas=50, porcoes_servidas=40, sobra_nao_distribuida=10,
            resto_no_prato=4, fechamentos=1),
        ReceitaFechamento(
            receita_id="00000000-0000-0000-0000-000000000001", nome="Arroz branco",
            porcoes_preparadas=50, porcoes_servidas=40, sobra_nao_distribuida=10,
            resto_no_prato=4, fechamentos=1),
    ]))

    item = resposta.aceitacao_itens[0]
    assert item.item == "Arroz branco"
    assert item.porcoes_preparadas == 200
    assert item.porcoes_servidas == 160
    assert item.porcoes_consumidas == 144
    assert item.resto_no_prato == 16
    assert item.percentual == 90.0
    assert item.fechamentos == 3


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
        _receita("Purê de batata", ["batata"], 2000, 100, 120),
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


def test_contagem_turma_aceita_turma_id_nulo():
    contagem = ContagemTurma.model_validate(
        {"turmaId": None, "turma": "Sem turma", "consumosRegistrados": 3, "alunosUnicos": 2})

    assert contagem.turma_id is None
    assert contagem.turma == "Sem turma"


def test_contagem_turma_propaga_turma_id_na_resposta():
    turma_id = "00000000-0000-0000-0000-0000000000a1"
    resposta = calcular_indicadores(_request(turmas=[
        {"turmaId": turma_id, "turma": "8A", "consumosRegistrados": 5, "alunosUnicos": 4},
        {"turmaId": None, "turma": "Sem turma", "consumosRegistrados": 2, "alunosUnicos": 2},
    ]))

    assert resposta.por_turma[0].turma_id == turma_id
    assert resposta.por_turma[0].repeticoes == 1
    assert resposta.por_turma[1].turma_id is None
    assert resposta.model_dump(by_alias=True)["porTurma"][0]["turmaId"] == turma_id
    assert all(t.status_meta == "NAO_AVALIAVEL" and t.percentual is None
               for t in resposta.por_turma)


def test_schema_version_e_6():
    assert calcular_indicadores(_request()).schema_version == "6"


def test_indicadores_ecoam_a_refeicao_no_schema_6():
    resposta = calcular_indicadores(_request(
        refeicao={"id": "5e1a0000-0000-4000-8000-000000000003", "nome": "Almoço"}))

    assert resposta.schema_version == "6"
    assert resposta.refeicao.nome == "Almoço"
    assert "turno" not in resposta.model_dump(by_alias=True)


def test_aviso_de_historico_sem_refeicao():
    com_legado = calcular_indicadores(_request(historico_sem_refeicao=12))
    sem_legado = calcular_indicadores(_request(historico_sem_refeicao=0))

    assert any(a.startswith("12 registros do histórico do legado") for a in com_legado.avisos)
    assert not any("legado" in aviso for aviso in sem_legado.avisos)


def test_motivo_por_turma_nao_cita_turma_atual_do_cadastro():
    resposta = calcular_indicadores(_request(turmas=[
        {"turmaId": None, "turma": "Sem turma", "consumosRegistrados": 1, "alunosUnicos": 1}]))

    motivo = resposta.por_turma[0].motivo
    assert "atual do cadastro" not in motivo
    assert "vigente na data do consumo" in motivo
    assert not any("atual do cadastro" in aviso for aviso in resposta.avisos)


def _fechamento(nome, preparadas, servidas, resto, fechamentos=1, receita_id=None):
    return ReceitaFechamento(
        receita_id=receita_id or f"00000000-0000-0000-0000-{abs(hash(nome)) % 10**12:012d}",
        nome=nome, porcoes_preparadas=preparadas, porcoes_servidas=servidas,
        sobra_nao_distribuida=preparadas - servidas, resto_no_prato=resto, fechamentos=fechamentos)


def _dias(atendidos, planejadas):
    return [AtendimentoDia(data=f"2026-09-{n + 1:02d}", planejadas=p, atendidos=a)
            for n, (a, p) in enumerate(zip(atendidos, planejadas))]


def test_sem_escopo_de_cardapio_com_fechamentos_avalia_aceitacao_e_desperdicio():
    fechamentos = [_fechamento("Sopa de legumes", 100, 90, 9) for _ in range(21)]

    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=fechamentos, quantidade_fechamentos_do_mes=21,
        cobertura_fechamentos_completa=False))

    assert resposta.aceitacao.status == "DISPONIVEL"
    assert resposta.aceitacao.percentual == 90.0
    assert resposta.desperdicio.status == "DISPONIVEL"
    assert resposta.desperdicio.percentual == 19.0


def test_com_escopo_a_cobertura_incompleta_continua_recusando():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Sopa", 100, 90, 9) for _ in range(21)],
        datas_selecionadas=["2026-09-01"], cobertura_fechamentos_completa=False))

    assert resposta.aceitacao.status == "DADOS_INSUFICIENTES"


def test_sobra_percentual_por_item():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Arroz", 100, 82, 0, fechamentos=3)],
        fechamentos_da_semana=[_fechamento("Arroz", 100, 82, 0)]))

    assert resposta.aceitacao_itens[0].sobra_percentual == 18.0
    assert resposta.aceitacao_itens_semana[0].sobra_percentual == 18.0
    assert resposta.model_dump(by_alias=True)["aceitacaoItens"][0]["sobraPercentual"] == 18.0


def test_sobra_percentual_nula_sem_preparado():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Fruta", 0, 0, 0, fechamentos=3)]))

    assert resposta.aceitacao_itens[0].sobra_percentual is None


def test_plano_revisar_preparacao_abaixo_de_90():
    # Preparado = servido: só a aceitação (resto) aparece no plano.
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Sopa de legumes", 100, 100, 18, fechamentos=6)]))

    acao = resposta.plano_de_acao[0]
    assert acao.tipo == "REVISAR_PREPARACAO"
    assert acao.item == "Sopa de legumes"
    assert acao.texto == ("Revisar a preparação de Sopa de legumes: aceitação de 82% (meta 90%) "
                          "em 6 dias medidos.")
    assert acao.valor == 82.0
    assert acao.referencia == 90.0
    assert len(resposta.plano_de_acao) == 1


def test_plano_ignora_item_com_menos_de_3_fechamentos():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Sopa de legumes", 100, 100, 40, fechamentos=2)]))

    assert resposta.plano_de_acao == []


def test_plano_reduzir_preparo_sobra_acima_de_10():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Iogurte", 100, 82, 0, fechamentos=5)]))

    acao = resposta.plano_de_acao[0]
    assert acao.tipo == "REDUZIR_PREPARO"
    assert acao.texto == ("Preparar menos Iogurte: sobrou na panela 18% do que foi preparado "
                          "em 5 dias medidos.")
    assert (acao.valor, acao.referencia) == (18.0, 10.0)


def test_plano_rever_planejamento_abaixo_de_80():
    resposta = calcular_indicadores(_request(
        atendimento_diario=_dias([38, 38, 38, 39, 39], [101] * 5),
        fechamentos_do_mes=[_fechamento("Sopa de legumes", 100, 100, 18, fechamentos=6)]))

    primeira = resposta.plano_de_acao[0]
    assert primeira.tipo == "REVER_PLANEJAMENTO"
    assert primeira.texto == ("Rever a quantidade planejada: em média 38 refeições servidas por dia "
                              "para 101 planejadas (38%).")
    assert primeira.valor == 38.0
    assert primeira.referencia == 80.0
    assert primeira.item is None and primeira.receita_id is None
    assert resposta.plano_de_acao[1].tipo == "REVISAR_PREPARACAO"


def test_plano_reduzir_preparo_sobra_exatamente_10_gera_acao():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Iogurte", 100, 90, 0, fechamentos=5)]))

    assert [a.tipo for a in resposta.plano_de_acao] == ["REDUZIR_PREPARO"]


def test_plano_reduzir_preparo_texto_com_casa_decimal():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Iogurte", 1000, 825, 0, fechamentos=5)]))

    assert "sobrou na panela 17,5% do que foi preparado" in resposta.plano_de_acao[0].texto


def test_plano_aceitacao_exatamente_90_nao_gera_acao():
    resposta = calcular_indicadores(_request(
        fechamentos_do_mes=[_fechamento("Arroz", 100, 100, 10, fechamentos=5)]))

    assert resposta.plano_de_acao == []


def test_plano_limiar_usa_valor_arredondado_mostrado():
    # 89,96% de aceitação aparece como 90 e 79,96% de atendimento aparece como 80.
    resposta = calcular_indicadores(_request(
        atendimento_diario=_dias([7996], [10000]),
        fechamentos_do_mes=[_fechamento("Arroz", 10000, 10000, 1004, fechamentos=5)]))

    assert resposta.plano_de_acao == []


def test_plano_vazio_quando_tudo_dentro_das_metas():
    resposta = calcular_indicadores(_request(
        atendimento_diario=_dias([90, 85], [100, 100]),
        fechamentos_do_mes=[_fechamento("Arroz", 100, 95, 5, fechamentos=5)]))

    assert resposta.plano_de_acao == []


def test_medias_ignoram_dias_sem_cardapio():
    resposta = calcular_indicadores(_request(
        atendimento_diario=_dias([40, 0, 60, 0], [100, 0, 100, 0])))

    assert resposta.execucao_planejamento.media_atendidos_dia == 50.0
    assert resposta.execucao_planejamento.media_planejada_dia == 100.0


def test_medias_nulas_sem_dias_com_cardapio():
    resposta = calcular_indicadores(_request())

    assert resposta.execucao_planejamento.media_atendidos_dia is None
    assert resposta.execucao_planejamento.media_planejada_dia is None
    assert resposta.plano_de_acao == []


def test_motivos_nao_usam_jargao_antigo():
    sem_dados = calcular_indicadores(_request())
    pequeno = calcular_indicadores(_request(medicao_do_dia=MedicaoDoDia(
        porcoes_preparadas=4, porcoes_servidas=3, sobra_nao_distribuida=1,
        resto_no_prato=0, itens_medidos=1, itens_do_cardapio=1)))
    textos = " ".join(
        r.aceitacao.motivo + r.desperdicio.motivo for r in (sem_dados, pequeno))

    for antigo in ("cuba", "não distribuída", "denominador"):
        assert antigo not in textos
