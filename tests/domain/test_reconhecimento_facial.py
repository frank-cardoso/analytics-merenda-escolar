from unittest.mock import patch

import pytest

from app.domain.reconhecimento_facial import (
    GerarEmbeddingRequest,
    IdentificarRostoRequest,
    MultiplosRostosDetectadosError,
    RostoNaoDetectadoError,
    gerar_embedding,
    identificar_rosto,
)


def _request_embedding(**alteracoes) -> GerarEmbeddingRequest:
    base = {"foto_base64": "base64-fake", "modelo": "Facenet"}
    return GerarEmbeddingRequest(**{**base, **alteracoes})


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_gerar_embedding_com_um_rosto(represent_mock):
    represent_mock.return_value = [
        {"embedding": [0.1, 0.2, 0.3], "facial_area": {}, "face_confidence": 0.98}
    ]

    resposta = gerar_embedding(_request_embedding())

    assert resposta.embedding == [0.1, 0.2, 0.3]
    assert resposta.modelo == "Facenet"
    represent_mock.assert_called_once_with(
        img_path="base64-fake",
        model_name="Facenet",
        detector_backend="opencv",
        enforce_detection=True,
    )


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_gerar_embedding_sem_rosto_vira_erro_de_dominio(represent_mock):
    represent_mock.side_effect = ValueError("Face could not be detected.")

    with pytest.raises(RostoNaoDetectadoError):
        gerar_embedding(_request_embedding())


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_gerar_embedding_com_mais_de_um_rosto_rejeita(represent_mock):
    represent_mock.return_value = [
        {"embedding": [0.1], "facial_area": {}, "face_confidence": 0.9},
        {"embedding": [0.2], "facial_area": {}, "face_confidence": 0.8},
    ]

    with pytest.raises(MultiplosRostosDetectadosError):
        gerar_embedding(_request_embedding())


def _rosto(embedding, w=100, h=100):
    return {"embedding": embedding, "facial_area": {"x": 0, "y": 0, "w": w, "h": h}}


def _identificar(candidatos: dict[str, list[float]]):
    return identificar_rosto(
        IdentificarRostoRequest(
            foto_base64="base64-fake",
            candidatos=[{"id": id_, "embedding": emb} for id_, emb in candidatos.items()],
        )
    )


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_identifica_o_candidato_mais_proximo(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"A": [1.0, 0.0], "B": [0.0, 1.0]})

    assert resposta.decisao == "RECONHECIDO"
    assert resposta.melhor_candidato_id == "A"
    assert resposta.distancia == 0.0
    assert resposta.distancia_segundo == 1.0
    assert resposta.limiar == 0.4
    represent_mock.assert_called_once_with(
        img_path="base64-fake",
        model_name="Facenet",
        detector_backend="opencv",
        enforce_detection=True,
    )


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_nao_reconhece_quando_todos_acima_do_limiar(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"B": [0.0, 1.0]})

    assert resposta.decisao == "NAO_RECONHECIDO"
    assert resposta.melhor_candidato_id == "B"


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_ambiguo_quando_segundo_esta_perto_demais(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"A": [1.0, 0.0], "B": [1.0, 0.01]})

    assert resposta.decisao == "AMBIGUO"
    assert resposta.melhor_candidato_id == "A"


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_candidato_unico_abaixo_do_limiar_reconhece(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"A": [0.8, 0.6]})

    assert resposta.decisao == "RECONHECIDO"
    assert resposta.distancia == 0.2
    assert resposta.distancia_segundo is None


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_usa_o_maior_rosto_da_foto(represent_mock):
    represent_mock.return_value = [
        _rosto([0.0, 1.0], w=50, h=50),
        _rosto([1.0, 0.0], w=120, h=120),
    ]

    resposta = _identificar({"A": [1.0, 0.0], "B": [0.0, 1.0]})

    assert resposta.decisao == "RECONHECIDO"
    assert resposta.melhor_candidato_id == "A"


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_ignora_candidato_de_dimensao_diferente(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"A": [1.0, 0.0], "C": [1.0, 0.0, 0.0]})

    assert resposta.decisao == "RECONHECIDO"
    assert resposta.melhor_candidato_id == "A"
    assert resposta.candidatos_ignorados == 1


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_todos_incompativeis_nao_reconhece(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"C": [1.0, 0.0, 0.0]})

    assert resposta.decisao == "NAO_RECONHECIDO"
    assert resposta.melhor_candidato_id is None
    assert resposta.distancia is None
    assert resposta.candidatos_ignorados == 1


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_identificacao_sem_rosto_detectado_levanta_erro(represent_mock):
    represent_mock.side_effect = ValueError("Face could not be detected.")

    with pytest.raises(RostoNaoDetectadoError):
        _identificar({"A": [1.0, 0.0]})


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_vetor_nulo_nao_corrompe_a_ordenacao_nem_elege_o_aluno_errado(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar(
        {
            "a": [0.8, 0.6],
            "c": [0.5, 0.866],
            "z": [0.0, 0.0],
            "d": [0.4, 0.917],
            "b": [1.0, 0.0],
        }
    )

    assert resposta.decisao == "RECONHECIDO"
    assert resposta.melhor_candidato_id == "b"
    assert resposta.candidatos_ignorados == 1


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_so_vetor_nulo_nao_reconhece(represent_mock):
    represent_mock.return_value = [_rosto([1.0, 0.0])]

    resposta = _identificar({"z": [0.0, 0.0]})

    assert resposta.decisao == "NAO_RECONHECIDO"
    assert resposta.melhor_candidato_id is None
    assert resposta.candidatos_ignorados == 1
