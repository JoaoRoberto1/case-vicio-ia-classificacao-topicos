"""Contrato entre preparação de vetores e classificação numérica offline."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from classificacao_local.classificador import (
    CONFIG_PADRAO, _texto_questao, _texto_tema,
)


def texto_questao(registro: dict) -> str:
    return _texto_questao(registro, CONFIG_PADRAO, ponderado=False)


def texto_tema(registro: dict) -> str:
    return _texto_tema(registro, CONFIG_PADRAO, ponderado=False)


def hash_texto(tipo: str, registro: dict) -> str:
    if tipo == "questao":
        texto = "query: " + texto_questao(registro)
    elif tipo == "tema":
        texto = "passage: " + texto_tema(registro)
    else:
        raise ValueError("Tipo de entrada desconhecido.")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def construir_registros(
    questoes: list[dict], temas: list[dict], ids_permitidos: set[str],
) -> list[dict]:
    qs = {q["id"]: q for q in questoes}
    if len(qs) != len(questoes) or not ids_permitidos <= qs.keys():
        raise ValueError("Questões repetidas ou IDs permitidos ausentes.")
    ts = {t["tema_id"]: t for t in temas}
    if len(ts) != len(temas):
        raise ValueError("Temas repetidos.")
    registros = [
        {"tipo": "questao", "id": i, "papel": "query",
         "texto": texto_questao(qs[i]), "texto_sha256": hash_texto("questao", qs[i])}
        for i in sorted(ids_permitidos)
    ]
    registros.extend(
        {"tipo": "tema", "id": i, "papel": "passage",
         "texto": texto_tema(t), "texto_sha256": hash_texto("tema", t)}
        for i, t in sorted(ts.items())
        if t["status"] == "active" and int(t["nivel"]) > 0
    )
    return registros


def validar_cache(cache: dict, registros: list[dict], dimensoes: int = 384) -> None:
    if (cache.get("schema") != "embeddings_e5_v1"
            or type(cache.get("dimensoes")) is not int
            or cache["dimensoes"] != dimensoes):
        raise ValueError("Esquema ou dimensão do cache inválido.")
    for tipo, campo in (("questao", "questoes"), ("tema", "temas")):
        esperados = {r["id"]: r for r in registros if r["tipo"] == tipo}
        if not isinstance(cache.get(campo), dict) or set(cache[campo]) != set(esperados):
            raise ValueError(f"O cache deve cobrir exatamente os IDs de {campo}.")
        for identificador, registro in esperados.items():
            item = cache[campo][identificador]
            if item.get("texto_sha256") != registro["texto_sha256"]:
                raise ValueError("Cache não corresponde ao texto de preparação.")
            vetor = item.get("vetor")
            if (not isinstance(vetor, list) or len(vetor) != dimensoes
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in vetor)
                    or not math.isclose(math.fsum(v * v for v in vetor), 1.0,
                                        abs_tol=1e-5, rel_tol=0.0)):
                raise ValueError("Vetor inválido, não finito ou sem normalização L2.")
            if (type(item.get("tokens")) is not int or item["tokens"] < 0
                    or type(item.get("janelas")) is not int or item["janelas"] < 1):
                raise ValueError("Contagens de tokens/janelas inválidas.")


def carregar_cache(
    diretorio: Path, registros: list[dict], config: dict,
) -> tuple[dict, dict]:
    """Lê somente JSON validado. Nunca importa ou chama um codificador."""
    manifesto_path = diretorio / "manifesto.json"
    cache_path = diretorio / "vetores.json"
    if (manifesto_path.is_symlink() or cache_path.is_symlink()
            or not manifesto_path.is_file() or not cache_path.is_file()):
        raise ValueError("Cache/manifesto ausente ou inválido; prepare embeddings separadamente.")
    manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    conteudo = cache_path.read_bytes()
    assinatura = hashlib.sha256(conteudo).hexdigest()
    if assinatura != manifesto["produtos_sha256"]["vetores.json"]:
        raise ValueError("Cache de vetores adulterado.")
    if manifesto["configuracao"] != config:
        raise ValueError("Configuração de embeddings divergente do manifesto.")
    cache = json.loads(conteudo)
    validar_cache(cache, registros, config["preparacao"]["dimensoes"])
    cache["sha256"] = assinatura
    return cache, manifesto
