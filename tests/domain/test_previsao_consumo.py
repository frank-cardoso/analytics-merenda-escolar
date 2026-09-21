from app.domain.previsao_consumo import (
    HistoricoConsumo,
    PrevisaoConsumoRequest,
    calcular_previsao,
)


def _request(**alteracoes) -> PrevisaoConsumoRequest:
    base = {
        "data_referencia": "2026-08-26",
        "turno": "NOITE",
        "cardapio": "Arroz, feijao, frango e salada",
        "quantidade_planejada": 300,
        "consumos_autorizados": 1,
        "tentativas_bloqueadas": 0,
        "taxa_consumo_planejado": 0.33,
        "sobra_de_planejamento": 299,
        "historico": [],
    }
    return PrevisaoConsumoRequest(**{**base, **alteracoes})


def test_desperdicio_nunca_e_classificado_sem_medicao_de_sobra_e_resto():
    response = calcular_previsao(_request(tentativas_bloqueadas=3))

    assert response.risco_desperdicio == "NAO_AVALIAVEL"
    assert "nao desperdicio de alimento" in response.desperdicio_motivo


def test_sem_historico_a_estimativa_e_o_realizado_do_dia():
    response = calcular_previsao(_request())

    assert response.demanda_estimada == 1
    assert response.media_historica is None
    assert response.piso_realizado == 1
    assert response.origem_estimativa == "REALIZADO_SEM_HISTORICO"
    assert response.diferenca_previsao_planejamento == -299
    assert response.confianca == "BAIXA"
    assert response.metodo == "baseline-estatistico-v2"


def test_usa_media_historica_quando_ela_supera_o_realizado():
    response = calcular_previsao(_request(historico=[
        HistoricoConsumo(data_referencia="2026-08-23", consumos_autorizados=80),
        HistoricoConsumo(data_referencia="2026-08-24", consumos_autorizados=100),
        HistoricoConsumo(data_referencia="2026-08-25", consumos_autorizados=90),
    ]))

    assert response.media_historica == 90
    assert response.demanda_estimada == 90
    assert response.origem_estimativa == "MEDIA_HISTORICA"
    assert response.diferenca_previsao_planejamento == -210
    assert response.confianca == "MEDIA"


def test_realizado_do_dia_e_piso_quando_media_historica_fica_abaixo():
    response = calcular_previsao(_request(consumos_autorizados=91, historico=[
        HistoricoConsumo(data_referencia="2026-08-23", consumos_autorizados=70),
        HistoricoConsumo(data_referencia="2026-08-24", consumos_autorizados=80),
        HistoricoConsumo(data_referencia="2026-08-25", consumos_autorizados=84),
    ]))

    assert response.media_historica == 78
    assert response.piso_realizado == 91
    assert response.demanda_estimada == 91
    assert response.origem_estimativa == "PISO_REALIZADO"
    assert response.diferenca_previsao_planejamento == -209
    assert (
        "A media historica (78) ficou abaixo do realizado do dia (91); "
        "a estimativa usa o realizado como piso."
    ) in response.evidencias
