from app.domain.tendencia_item import SerieItemConsumo, TendenciaItemRequest, calcular_tendencias


def test_classifica_queda_quando_media_da_segunda_metade_cai_bem_abaixo_da_primeira():
    request = TendenciaItemRequest(
        itens=[SerieItemConsumo(item="Salada de alface", taxas_execucao=[80.0, 82.0, 40.0, 38.0])]
    )

    response = calcular_tendencias(request)

    assert response.tendencias[0].item == "Salada de alface"
    assert response.tendencias[0].tendencia == "QUEDA"


def test_classifica_alta_quando_media_da_segunda_metade_sobe_bem_acima_da_primeira():
    request = TendenciaItemRequest(
        itens=[SerieItemConsumo(item="Arroz branco", taxas_execucao=[40.0, 42.0, 80.0, 85.0])]
    )

    response = calcular_tendencias(request)

    assert response.tendencias[0].tendencia == "ALTA"


def test_classifica_estavel_quando_variacao_e_pequena():
    request = TendenciaItemRequest(
        itens=[SerieItemConsumo(item="Feijao carioca", taxas_execucao=[80.0, 81.0, 79.0, 82.0])]
    )

    response = calcular_tendencias(request)

    assert response.tendencias[0].tendencia == "ESTAVEL"


def test_classifica_estavel_quando_ha_menos_de_dois_pontos():
    request = TendenciaItemRequest(
        itens=[SerieItemConsumo(item="Cuscuz", taxas_execucao=[50.0])]
    )

    response = calcular_tendencias(request)

    assert response.tendencias[0].tendencia == "ESTAVEL"


def test_calcula_tendencia_para_varios_itens_de_uma_vez():
    request = TendenciaItemRequest(
        itens=[
            SerieItemConsumo(item="Salada de alface", taxas_execucao=[80.0, 40.0]),
            SerieItemConsumo(item="Arroz branco", taxas_execucao=[85.0, 84.0]),
        ]
    )

    response = calcular_tendencias(request)

    assert [t.item for t in response.tendencias] == ["Salada de alface", "Arroz branco"]
