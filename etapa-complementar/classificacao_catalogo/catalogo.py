"""Enriquecimento versionado: recebe somente taxonomia, nunca questões/rótulos."""

from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlparse

ARQUIVOS = [f"config/modulo7/catalogo_{s}.json" for s in
            ("penal", "processo", "especial", "criminologia")]


def enriquecer(taxonomia: dict, documentos: list[dict]) -> dict:
    origem = taxonomia["por_id"]
    esperados = {i for i, t in origem.items()
                 if t["status"] == "active" and int(t["nivel"]) > 0}
    descritores = {}
    for doc in documentos:
        if (doc.get("schema") != "enriquecimento_catalogo_m7_v1"
                or doc.get("procedimento") != "LLM_preparacao_somente_taxonomia"
                or doc.get("questoes_ou_rotulos_consultados") is not False):
            raise ValueError("Procedência incompatível com preparação cega do catálogo.")
        for r in doc["registros"]:
            i = r["tema_id"]
            if i in descritores or i not in esperados:
                raise ValueError("Descritor duplicado ou tema não candidato.")
            if (not isinstance(r.get("descricao"), str) or not r["descricao"].strip()
                    or not isinstance(r.get("termos"), list) or not 5 <= len(r["termos"]) <= 12
                    or any(not isinstance(x, str) or not x.strip() for x in r["termos"])
                    or len(set(r["termos"])) != len(r["termos"])
                    or type(r.get("ambiguo")) is not bool
                    or not isinstance(r.get("fontes"), list) or not r["fontes"]
                    or any(urlparse(f).scheme != "https" or not urlparse(f).netloc
                           for f in r["fontes"])):
                raise ValueError("Descritor incompleto ou inválido.")
            descritores[i] = r
    if set(descritores) != esperados:
        raise ValueError("Descritores não cobrem exatamente todos os candidatos ativos.")
    registros = deepcopy(taxonomia["registros"])
    for t in registros:
        if t["tema_id"] in descritores:
            r = descritores[t["tema_id"]]
            t["descricao"] = r["descricao"] + " Termos associados: " + "; ".join(r["termos"]) + "."
    return {"registros": registros, "por_id": {t["tema_id"]: t for t in registros}}


def carregar(raiz: Path, taxonomia: dict) -> dict:
    return enriquecer(taxonomia, [json.loads((raiz / p).read_text(encoding="utf-8"))
                                  for p in ARQUIVOS])
