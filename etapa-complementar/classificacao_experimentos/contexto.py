"""Carrega somente fontes preparadas e confere a cadeia dos módulos anteriores."""

import json
from pathlib import Path

from classificacao_local.experimento import selecionar_protocolo
from classificacao_topicos.pipeline import (
    _arquivo_local, _sha, verificar_preparacao,
)
from .entradas import construir_registros


def ler_json(raiz: Path, nome: str):
    return json.loads(_arquivo_local(raiz, nome).read_text(encoding="utf-8"))


def ler_jsonl(raiz: Path, nome: str):
    with _arquivo_local(raiz, nome).open(encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo]


def assinar(raiz: Path, nomes: list[str]) -> dict:
    return {nome: _sha(_arquivo_local(raiz, nome).read_bytes()) for nome in sorted(nomes)}


def conferir_assinaturas(raiz: Path, assinaturas: dict) -> None:
    if assinaturas != assinar(raiz, list(assinaturas)):
        raise ValueError("Fonte, código ou artefato divergente do registro fixado.")


def carregar_contexto(raiz: Path) -> dict:
    raiz = raiz.resolve()
    fixadas = ler_json(raiz, "config/modulo3/fontes.json")
    conferir_assinaturas(raiz, fixadas["sha256"])
    verificar_preparacao(raiz, raiz / "artefatos/preparacao")
    m2 = ler_json(raiz, "artefatos/lexical-v1/manifesto.json")
    conferir_assinaturas(raiz, m2["entradas_e_implementacao_sha256"])
    conferir_assinaturas(raiz, {
        "artefatos/lexical-v1/" + nome: sha
        for nome, sha in m2["produtos_sha256"].items()
    })
    protocolo = selecionar_protocolo(
        ler_json(raiz, "artefatos/preparacao/particoes.json"),
        ler_json(raiz, "config/modulo2/protocolo_desenvolvimento.json"),
    )
    if protocolo != ler_json(raiz, "artefatos/lexical-v1/protocolo.json"):
        raise ValueError("A divisão usada deve permanecer idêntica ao módulo 2.")
    questoes = ler_jsonl(raiz, "artefatos/preparacao/questoes_preparadas.jsonl")
    temas = ler_json(raiz, "artefatos/preparacao/temas_preparados.json")
    dev = set(protocolo["desenvolvimento_ids"])
    avaliacao = set(protocolo["avaliacao_ids"])
    registros = construir_registros(questoes, temas, dev | avaliacao)
    return {
        "questoes": questoes,
        "taxonomia": {"registros": temas, "por_id": {t["tema_id"]: t for t in temas}},
        "protocolo": protocolo,
        "registros": registros,
        "fontes_fixadas": fixadas,
    }
