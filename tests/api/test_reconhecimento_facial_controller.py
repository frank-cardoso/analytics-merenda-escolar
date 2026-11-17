from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

URL_IDENTIFICACOES = "/api/v1/reconhecimento-facial/identificacoes"


def _corpo_identificacao(**alteracoes):
    base = {
        "fotoBase64": "base64-fake",
        "candidatos": [{"id": "A", "embedding": [1.0, 0.0]}],
    }
    return {**base, **alteracoes}


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_identificacao_facial_responde_em_camel_case(represent_mock):
    represent_mock.return_value = [
        {"embedding": [1.0, 0.0], "facial_area": {"x": 0, "y": 0, "w": 100, "h": 100}}
    ]
    client = TestClient(app)

    response = client.post(URL_IDENTIFICACOES, json=_corpo_identificacao())

    assert response.status_code == 200
    corpo = response.json()
    assert set(corpo) == {
        "decisao",
        "melhorCandidatoId",
        "distancia",
        "distanciaSegundo",
        "limiar",
        "margemMinima",
        "candidatosIgnorados",
        "modelo",
    }
    assert corpo["decisao"] == "RECONHECIDO"
    assert corpo["melhorCandidatoId"] == "A"


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_identificacao_sem_rosto_retorna_422(represent_mock):
    represent_mock.side_effect = ValueError("Face could not be detected.")
    client = TestClient(app)

    response = client.post(URL_IDENTIFICACOES, json=_corpo_identificacao())

    assert response.status_code == 422
    assert "Face could not be detected" in response.json()["detail"]


def test_identificacao_sem_candidatos_retorna_422():
    client = TestClient(app)

    response = client.post(URL_IDENTIFICACOES, json=_corpo_identificacao(candidatos=[]))

    assert response.status_code == 422


def test_endpoint_de_verificacao_1a1_nao_existe_mais():
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconhecimento-facial/verificacoes",
        json={"fotoBase64": "base64-fake", "embeddingCadastrado": [0.1]},
    )

    assert response.status_code == 404


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_gerar_embedding_retorna_vetor(represent_mock):
    represent_mock.return_value = [
        {"embedding": [0.1, 0.2, 0.3], "facial_area": {}, "face_confidence": 0.98}
    ]
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconhecimento-facial/embeddings",
        json={"fotoBase64": "base64-fake"},
    )

    assert response.status_code == 200
    assert response.json() == {"embedding": [0.1, 0.2, 0.3], "modelo": "Facenet"}


@patch("app.domain.reconhecimento_facial.DeepFace.represent")
def test_gerar_embedding_com_multiplos_rostos_retorna_422(represent_mock):
    represent_mock.return_value = [
        {"embedding": [0.1], "facial_area": {}, "face_confidence": 0.9},
        {"embedding": [0.2], "facial_area": {}, "face_confidence": 0.8},
    ]
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconhecimento-facial/embeddings",
        json={"fotoBase64": "base64-fake"},
    )

    assert response.status_code == 422
