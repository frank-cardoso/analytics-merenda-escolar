from app.domain.previsao_consumo import (
    HistoricoConsumo,
    PrevisaoConsumoRequest,
    calcular_previsao,
)


def test_classifica_risco_alto_quando_consumo_fica_muito_abaixo_do_planejado():
    request = PrevisaoConsumoRequest(
        data_referencia="2026-08-26",
        turno="NOITE",
        cardapio="Arroz, feijao, frango e salada",
        quantidade_planejada=300,
        consumos_autorizados=1,
        tentativas_bloqueadas=3,
        taxa_consumo_planejado=0.33,
        sobra_estimada=299,
        historico=[],
    )

    response = calcular_previsao(request)

    assert response.demanda_estimada == 1
    assert response.ajuste_sugerido == -299
    assert response.risco_desperdicio == "ALTO"
    assert response.confianca == "BAIXA"
    assert response.metodo == "baseline-estatistico-v1"


def test_usa_media_historica_quando_historico_existe():
    request = PrevisaoConsumoRequest(
        data_referencia="2026-08-26",
        turno="NOITE",
        cardapio="Arroz, feijao, frango e salada",
        quantidade_planejada=300,
        consumos_autorizados=1,
        tentativas_bloqueadas=0,
        taxa_consumo_planejado=0.33,
        sobra_estimada=299,
        historico=[
            HistoricoConsumo(data_referencia="2026-08-23", consumos_autorizados=80),
            HistoricoConsumo(data_referencia="2026-08-24", consumos_autorizados=100),
            HistoricoConsumo(data_referencia="2026-08-25", consumos_autorizados=90),
        ],
    )

    response = calcular_previsao(request)

    assert response.demanda_estimada == 90
    assert response.ajuste_sugerido == -210
    assert response.risco_desperdicio == "ALTO"
    assert response.confianca == "MEDIA"
