"""Gera a semente de rostos de demonstracao a partir do LFW (adultos, dataset publico).

Uso, a partir da raiz do repo analytics:
    ./.venv/bin/python scripts/gerar_rostos_demo.py --lfw-dir PATH_DO_LFW
"""

import argparse
import base64
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.reconhecimento_facial import (  # noqa: E402
    CandidatoRosto,
    GerarEmbeddingRequest,
    IdentificarRostoRequest,
    MultiplosRostosDetectadosError,
    RostoNaoDetectadoError,
    gerar_embedding,
    identificar_rosto,
)

ALUNOS = [(f"ALU-900{n}", f"2026900{n}") for n in range(1, 6)]
# Nome fictício por identidade LFW, escolhido conforme a aparência do rosto; reprodutível.
NOMES: dict[str, str] = {
    "Suzanne_Gaudet": "Helena Duarte",
    "Patricia_Heaton": "Lívia Campos",
    "Stanley_McChrystal": "Rafael Moreira",
    "Lennox_Lewis": "Otávio Brandão",
    "Lee_Jun": "Lucas Ferreira",
}
DISTANCIA_PROPRIA_MAXIMA = 0.30
URL_ORIGEM = "https://ndownloader.figshare.com/files/5976018"
ORIGEM = f"Labeled Faces in the Wild (LFW), baixado de {URL_ORIGEM}"


def data_url(caminho: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(caminho.read_bytes()).decode()


def embedding_de(caminho: Path) -> list[float] | None:
    try:
        return gerar_embedding(GerarEmbeddingRequest(foto_base64=data_url(caminho))).embedding
    except (RostoNaoDetectadoError, MultiplosRostosDetectadosError):
        return None


def identificar(caminho: Path, candidatos: list[CandidatoRosto]):
    req = IdentificarRostoRequest(foto_base64=data_url(caminho), candidatos=candidatos)
    return identificar_rosto(req)


def main() -> int:
    raiz_api = Path(__file__).resolve().parent.parent.parent / "api-merenda-escolar"
    p = argparse.ArgumentParser()
    p.add_argument("--lfw-dir", required=True, type=Path)
    semente = raiz_api / "src/main/resources/demo/rostos-demo.json"
    p.add_argument("--semente", type=Path, default=semente)
    p.add_argument("--imagens", type=Path, default=raiz_api / "demo/rostos-teste")
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args()

    identidades = []
    for pasta in sorted(args.lfw_dir.iterdir()):
        fotos = sorted(pasta.glob("*.jpg")) if pasta.is_dir() else []
        tem_par = all((pasta / f"{pasta.name}_000{n}.jpg").exists() for n in (1, 2))
        if 2 <= len(fotos) <= 3 and tem_par:
            identidades.append(pasta)
    random.Random(args.seed).shuffle(identidades)

    aceitos = []  # (pasta, embedding)
    descartes = {"sem um unico rosto": 0, "AMBIGUO/nao reconhecido": 0}
    usadas = 0
    for pasta in identidades:
        if len(aceitos) == len(ALUNOS):
            break
        usadas += 1
        cadastro = pasta / f"{pasta.name}_0001.jpg"
        emb = embedding_de(cadastro)
        if emb is None:
            descartes["sem um unico rosto"] += 1
            continue
        tentativa = [*aceitos, (pasta, emb)]
        candidatos = [CandidatoRosto(id=str(i), embedding=e) for i, (_, e) in enumerate(tentativa)]
        ok = True
        for i, (pst, _) in enumerate(tentativa):
            try:
                r = identificar(pst / f"{pst.name}_0002.jpg", candidatos)
            except (RostoNaoDetectadoError, MultiplosRostosDetectadosError):
                ok = False
                break
            if (
                r.decisao != "RECONHECIDO"
                or r.melhor_candidato_id != str(i)
                or r.distancia > DISTANCIA_PROPRIA_MAXIMA
            ):
                ok = False
                break
        if ok:
            aceitos.append((pasta, emb))
            print(f"aceito: {pasta.name}", flush=True)
        else:
            descartes["AMBIGUO/nao reconhecido"] += 1

    if len(aceitos) < len(ALUNOS):
        print(f"ERRO: apenas {len(aceitos)} identidades aceitas", file=sys.stderr)
        return 1

    sem_nome = [p_.name for p_, _ in aceitos if p_.name not in NOMES]
    if sem_nome:
        print(f"ERRO: identidades aceitas sem nome em NOMES: {sem_nome}", file=sys.stderr)
        return 1

    candidatos = [CandidatoRosto(id=str(i), embedding=e) for i, (_, e) in enumerate(aceitos)]
    vistos = {p_.name for p_, _ in aceitos}
    desconhecido = None
    menor_desc = None
    for pasta in identidades:
        if pasta.name in vistos:
            continue
        foto = pasta / f"{pasta.name}_0001.jpg"
        try:
            r = identificar(foto, candidatos)
        except (RostoNaoDetectadoError, MultiplosRostosDetectadosError):
            continue
        if r.decisao == "NAO_RECONHECIDO":
            desconhecido, menor_desc = pasta, r.distancia
            break
    if desconhecido is None:
        print("ERRO: nenhum desconhecido encontrado", file=sys.stderr)
        return 1

    args.imagens.mkdir(parents=True, exist_ok=True)
    args.semente.parent.mkdir(parents=True, exist_ok=True)
    alunos_json = []
    linhas = []
    for cand_id, ((codigo, matricula), (pasta, emb)) in enumerate(
        zip(ALUNOS, aceitos, strict=True)
    ):
        teste = pasta / f"{pasta.name}_0002.jpg"
        nome_img = f"{codigo}-teste.jpg"
        shutil.copyfile(teste, args.imagens / nome_img)
        alunos_json.append(
            {
                "codigoPublico": codigo,
                "matricula": matricula,
                "nome": NOMES[pasta.name],
                "lfwIdentidade": pasta.name,
                "imagemTeste": nome_img,
                "embedding": emb,
            }
        )
        r = identificar(teste, candidatos)
        assert r.decisao == "RECONHECIDO" and r.melhor_candidato_id == str(cand_id)
        margem = r.distancia_segundo - r.distancia
        linhas.append((codigo, pasta.name, r.distancia, r.distancia_segundo, margem))
    foto_desc = desconhecido / f"{desconhecido.name}_0001.jpg"
    shutil.copyfile(foto_desc, args.imagens / "desconhecido.jpg")
    args.semente.write_text(
        json.dumps(
            {"origem": ORIGEM, "modelo": "Facenet", "alunos": alunos_json}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\n{'codigo':9} {'identidade':26} {'propria':>8} {'impostor':>9} {'margem':>7}")
    for c, n, d, s, m in linhas:
        print(f"{c:9} {n:26} {d:8.4f} {s:9.4f} {m:7.4f}")
    print(f"\nmenor margem: {min(m for *_, m in linhas):.4f}")
    print(f"desconhecido: {desconhecido.name}, distancia mais proxima {menor_desc:.4f}")
    print(f"identidades avaliadas: {usadas}; descartes: {descartes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
