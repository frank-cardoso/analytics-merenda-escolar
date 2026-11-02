from fastapi import APIRouter, HTTPException

from app.domain.reconhecimento_facial import (
    GerarEmbeddingRequest,
    GerarEmbeddingResponse,
    MultiplosRostosDetectadosError,
    RostoNaoDetectadoError,
    VerificarRostoRequest,
    VerificarRostoResponse,
    gerar_embedding,
    verificar_rosto,
)

router = APIRouter(prefix="/api/v1", tags=["reconhecimento-facial"])


@router.post(
    "/reconhecimento-facial/verificacoes",
    response_model=VerificarRostoResponse,
    response_model_by_alias=True,
)
def criar_verificacao_facial(request: VerificarRostoRequest) -> VerificarRostoResponse:
    try:
        return verificar_rosto(request)
    except RostoNaoDetectadoError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro


@router.post(
    "/reconhecimento-facial/embeddings",
    response_model=GerarEmbeddingResponse,
    response_model_by_alias=True,
)
def criar_embedding(request: GerarEmbeddingRequest) -> GerarEmbeddingResponse:
    try:
        return gerar_embedding(request)
    except RostoNaoDetectadoError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    except MultiplosRostosDetectadosError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
