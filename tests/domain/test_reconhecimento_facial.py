from unittest.mock import patch

import pytest

from app.domain.reconhecimento_facial import (
    GerarEmbeddingRequest,
    MultiplosRostosDetectadosError,
    RostoNaoDetectadoError,
    VerificarRostoRequest,
    gerar_embedding,
    verificar_rosto,
)


def _request(**alteracoes) -> VerificarRostoRequest:
    base = {
        "foto_base64": "base64-fake",
        "embedding_cadastrado": [0.1, 0.2, 0.3],
        "modelo": "Facenet",
    }
    return VerificarRostoRequest(**{**base, **alteracoes})


def _request_embedding(**alteracoes) -> GerarEmbeddingRequest:
    base = {"foto_base64": "base64-fake", "modelo": "Facenet"}
    return GerarEmbeddingRequest(**{**base, **alteracoes})


@patch("app.domain.reconhecimento_facial.DeepFace.verify")
def test_rosto_confere(verify_mock):
    verify_mock.return_value = {
        "verified": True,
        "distance": 0.12,
        "threshold": 0.4,
        "model": "Facenet",
    }

    resposta = verificar_rosto(_request())

    assert resposta.confere is True
    assert resposta.distancia == 0.12
    assert resposta.limiar == 0.4
    assert resposta.modelo == "Facenet"
    verify_mock.assert_called_once_with(
        img1_path="base64-fake",
        img2_path=[0.1, 0.2, 0.3],
        model_name="Facenet",
        detector_backend="opencv",
        enforce_detection=True,
    )


@patch("app.domain.reconhecimento_facial.DeepFace.verify")
def test_rosto_nao_confere(verify_mock):
    verify_mock.return_value = {
        "verified": False,
        "distance": 0.81,
        "threshold": 0.4,
        "model": "Facenet",
    }

    resposta = verificar_rosto(_request())

    assert resposta.confere is False
    assert resposta.distancia == 0.81


@patch("app.domain.reconhecimento_facial.DeepFace.verify")
def test_rosto_nao_detectado_vira_erro_de_dominio(verify_mock):
    verify_mock.side_effect = ValueError("Face could not be detected.")

    with pytest.raises(RostoNaoDetectadoError):
        verificar_rosto(_request())


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
