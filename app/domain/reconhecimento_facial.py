"""Reconhecimento facial: identifica quem e a pessoa da foto entre os candidatos recebidos (1:N).

O servico nunca guarda foto nem embedding. O Java e dono do cadastro facial (guarda o embedding
de cada aluno) e manda, junto com a foto do momento da bipagem, os vetores dos candidatos; aqui
so se compara e se responde quem e o mais proximo e se a decisao e segura. Nada fica em memoria
depois do request — sem isso a identificacao viraria um banco de rostos de crianca por acidente.
"""

import math
from typing import Literal

from deepface import DeepFace
from deepface.modules import verification
from pydantic import BaseModel, ConfigDict, Field

ModeloReconhecimento = Literal["Facenet", "Facenet512", "SFace", "ArcFace"]

MODELO_PADRAO: ModeloReconhecimento = "Facenet"

# Diferenca minima entre o melhor e o segundo candidato; abaixo disso a identificacao e ambigua.
MARGEM_MINIMA: float = 0.08


class CandidatoRosto(BaseModel):
    id: str
    embedding: list[float] = Field(min_length=1)


class IdentificarRostoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    foto_base64: str = Field(alias="fotoBase64")
    candidatos: list[CandidatoRosto] = Field(min_length=1)
    modelo: ModeloReconhecimento = MODELO_PADRAO


class IdentificarRostoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    decisao: Literal["RECONHECIDO", "NAO_RECONHECIDO", "AMBIGUO"]
    melhor_candidato_id: str | None = Field(alias="melhorCandidatoId")
    distancia: float | None
    distancia_segundo: float | None = Field(alias="distanciaSegundo")
    limiar: float
    margem_minima: float = Field(alias="margemMinima")
    candidatos_ignorados: int = Field(alias="candidatosIgnorados")
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


def identificar_rosto(request: IdentificarRostoRequest) -> IdentificarRostoResponse:
    try:
        rostos = DeepFace.represent(
            img_path=request.foto_base64,
            model_name=request.modelo,
            detector_backend="opencv",
            enforce_detection=True,
        )
    except ValueError as erro:
        # DeepFace levanta ValueError quando enforce_detection=True e nao acha rosto na foto.
        raise RostoNaoDetectadoError(str(erro)) from erro

    # Foto da fila pode pegar quem aparece ao fundo: vale o maior rosto.
    foto = max(rostos, key=lambda r: r["facial_area"]["w"] * r["facial_area"]["h"])["embedding"]
    limiar = verification.find_threshold(request.modelo, "cosine")

    # Embedding de outra dimensao veio de outro modelo e nao e comparavel.
    compativeis = [c for c in request.candidatos if len(c.embedding) == len(foto)]

    # Vetor nulo ou com NaN da distancia NaN, que corrompe a ordenacao e elege o aluno errado.
    distancias = sorted(
        (d, c.id)
        for c in compativeis
        if math.isfinite(d := float(verification.find_distance(foto, c.embedding, "cosine")))
    )
    ignorados = len(request.candidatos) - len(distancias)

    def resposta(decisao, melhor=None, segundo=None) -> IdentificarRostoResponse:
        return IdentificarRostoResponse(
            decisao=decisao,
            melhor_candidato_id=melhor[1] if melhor else None,
            distancia=round(melhor[0], 4) if melhor else None,
            distancia_segundo=round(segundo[0], 4) if segundo else None,
            limiar=limiar,
            margem_minima=MARGEM_MINIMA,
            candidatos_ignorados=ignorados,
            modelo=request.modelo,
        )

    if not distancias:
        return resposta("NAO_RECONHECIDO")

    melhor = distancias[0]
    segundo = distancias[1] if len(distancias) > 1 else None
    if melhor[0] >= limiar:
        return resposta("NAO_RECONHECIDO", melhor, segundo)
    if segundo and segundo[0] - melhor[0] < MARGEM_MINIMA:
        return resposta("AMBIGUO", melhor, segundo)
    return resposta("RECONHECIDO", melhor, segundo)


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
