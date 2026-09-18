from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload():
    return {
        "dataReferencia": "2026-09-17", "inicioHistorico": "2026-08-19", "turno": "MANHA",
        "quantidadePlanejada": 100, "consumosRegistrados": 80, "alunosUnicos": 70,
        "metaPercentual": 80,
        "turmas": [{"turma": "A", "consumosRegistrados": 80, "alunosUnicos": 70}],
        "itens": [
            {"item": "Arroz", "planejamentos": 10, "execucoesRegistradas": 8,
             "escolas": 2, "origens": ["FAKE"]},
            {"item": "Feijão", "planejamentos": 5, "execucoesRegistradas": 5,
             "escolas": 2, "origens": ["FAKE"]},
            {"item": "Pouca amostra", "planejamentos": 1, "execucoesRegistradas": 1,
             "escolas": 1, "origens": ["FAKE"]}
        ]
    }


def test_meta_e_repeticoes_nao_confundem_refeicoes_com_alunos():
    response = client.post("/api/v1/indicadores-logisticos", json=payload())
    assert response.status_code == 200
    result = response.json()
    assert result["execucaoPlanejamento"]["percentual"] == 80
    assert result["execucaoPlanejamento"]["statusMeta"] == "ATINGIDA"
    assert result["atendimentos"]["repeticoes"] == 10
    assert result["porTurma"][0]["percentual"] is None
    assert result["porTurma"][0]["statusMeta"] == "NAO_AVALIAVEL"


def test_ranking_ponderado_por_contagens_exclui_amostras_pequenas():
    result = client.post("/api/v1/indicadores-logisticos", json=payload()).json()
    assert [item["item"] for item in result["topComidas"]] == ["Feijão", "Arroz"]
    assert result["topComidas"][1]["percentual"] == 80
    assert result["ingredientes"]["status"] == "DADOS_INSUFICIENTES"
    assert result["rotacaoCardapio"]["cicloSugeridoDias"] is None


def test_denominador_zero_nao_vira_zero_porcento():
    request = payload()
    request["quantidadePlanejada"] = 0
    result = client.post("/api/v1/indicadores-logisticos", json=request).json()
    assert result["execucaoPlanejamento"]["percentual"] is None
    assert result["execucaoPlanejamento"]["statusMeta"] == "NAO_AVALIAVEL"


def test_execucao_acima_de_cem_nao_e_ocultada():
    request = payload()
    request["quantidadePlanejada"] = 50
    result = client.post("/api/v1/indicadores-logisticos", json=request).json()
    assert result["execucaoPlanejamento"]["percentual"] == 160
    assert result["execucaoPlanejamento"]["diferencaMetaPp"] == 80


def test_rejeita_contagens_inconsistentes_e_datas_invertidas():
    request = payload()
    request["alunosUnicos"] = 81
    assert client.post("/api/v1/indicadores-logisticos", json=request).status_code == 422
    request = payload()
    request["inicioHistorico"] = "2026-09-18"
    assert client.post("/api/v1/indicadores-logisticos", json=request).status_code == 422
