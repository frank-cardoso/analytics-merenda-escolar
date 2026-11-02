from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@patch("app.domain.reconhecimento_facial.DeepFace.verify")
def test_verificacao_facial_confere(verify_mock):
    verify_mock.return_value = {
        "verified": True,
        "distance": 0.1234,
        "threshold": 0.4,
        "model": "Facenet",
    }
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconhecimento-facial/verificacoes",
        json={
            "fotoBase64": "base64-fake",
            "embeddingCadastrado": [0.1, 0.2, 0.3],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "confere": True,
        "distancia": 0.1234,
        "limiar": 0.4,
        "modelo": "Facenet",
    }


@patch("app.domain.reconhecimento_facial.DeepFace.verify")
def test_verificacao_facial_sem_rosto_detectado_retorna_422(verify_mock):
    verify_mock.side_effect = ValueError("Face could not be detected.")
    client = TestClient(app)

    response = client.post(
        "/api/v1/reconhecimento-facial/verificacoes",
        json={
            "fotoBase64": "base64-fake",
            "embeddingCadastrado": [0.1, 0.2, 0.3],
        },
    )

    assert response.status_code == 422
    assert "Face could not be detected" in response.json()["detail"]


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
