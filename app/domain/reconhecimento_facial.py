"""Verificacao facial 1:1: confere se a foto capturada bate com o aluno ja cadastrado.

O servico nunca guarda foto nem embedding. O Java e dono do cadastro facial (tira a foto de
referencia, gera o embedding e guarda); aqui so chega a foto do momento da bipagem e o vetor
ja salvo daquele aluno, e a resposta e so se bate ou nao. Nada fica em memoria depois do
request — sem isso a validacao de presenca virasse um banco de rostos de crianca por acidente.

Nao e busca entre todos os alunos (1:N): o Java ja sabe quem esta tentando confirmar presenca
(pela matricula ou QR), entao aqui e so a comparacao contra o embedding daquele aluno.
"""

from typing import Literal

from deepface import DeepFace
from pydantic import BaseModel, ConfigDict, Field

ModeloReconhecimento = Literal["Facenet", "Facenet512", "SFace", "ArcFace"]

MODELO_PADRAO: ModeloReconhecimento = "Facenet"


class VerificarRostoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    foto_base64: str = Field(alias="fotoBase64")
    embedding_cadastrado: list[float] = Field(alias="embeddingCadastrado", min_length=1)
    modelo: ModeloReconhecimento = MODELO_PADRAO


class VerificarRostoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    confere: bool
    distancia: float
    limiar: float
    modelo: str


class GerarEmbeddingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    foto_base64: str = Field(alias="fotoBase64")
    modelo: ModeloReconhecimento = MODELO_PADRAO


class GerarEmbeddingResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    embedding: list[float]
    modelo: str


class RostoNaoDetectadoError(Exception):
    """A foto recebida nao tem rosto detectavel. Nao e "nao confere", e falta de dado."""


class MultiplosRostosDetectadosError(Exception):
    """Cadastro exige uma foto com um rosto so; com mais de um, nao da pra saber qual vale."""


def verificar_rosto(request: VerificarRostoRequest) -> VerificarRostoResponse:
    try:
        resultado = DeepFace.verify(
            img1_path=request.foto_base64,
            img2_path=request.embedding_cadastrado,
            model_name=request.modelo,
            detector_backend="opencv",
            enforce_detection=True,
        )
    except ValueError as erro:
        # DeepFace levanta ValueError quando enforce_detection=True e nao acha rosto na foto.
        raise RostoNaoDetectadoError(str(erro)) from erro

    return VerificarRostoResponse(
        confere=resultado["verified"],
        distancia=round(resultado["distance"], 4),
        limiar=resultado["threshold"],
        modelo=resultado["model"],
    )


def gerar_embedding(request: GerarEmbeddingRequest) -> GerarEmbeddingResponse:
    """Cadastro da foto de referencia: gera o vetor que o Java vai guardar.

    So o vetor sai daqui — a foto em si nunca e persistida, nem aqui nem no retorno.
    """
    try:
        resultados = DeepFace.represent(
            img_path=request.foto_base64,
            model_name=request.modelo,
            detector_backend="opencv",
            enforce_detection=True,
        )
    except ValueError as erro:
        raise RostoNaoDetectadoError(str(erro)) from erro

    if len(resultados) > 1:
        raise MultiplosRostosDetectadosError(
            f"{len(resultados)} rostos detectados na foto; cadastro exige exatamente um."
        )

    return GerarEmbeddingResponse(
        embedding=resultados[0]["embedding"],
        modelo=request.modelo,
    )
