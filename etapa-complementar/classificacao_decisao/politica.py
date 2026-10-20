"""Regras de abstenção e avaliação numérica, sem julgamento de temas."""

from __future__ import annotations

from collections import Counter
import math
import re
import unicodedata

from .calibracao import metricas, wilson


def _normalizar(texto: str) -> str:
    texto = "".join(c for c in unicodedata.normalize("NFKD", texto.casefold())
                    if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texto)).strip()


def elegibilidade(taxonomia: dict, config: dict) -> dict[str, str]:
    """Motivo vazio significa elegível. Não promove previsões a ancestrais."""
    pais_ativos = {
        pai for t in taxonomia["registros"] if t["status"] == "active"
        for pai in t.get("ancestrais_ids", [])
    }
    motivos = {}
    for tema in taxonomia["registros"]:
        identificador = tema["tema_id"]
        titulo = " " + _normalizar(tema["titulo"]) + " "
        if tema["status"] != config["status"]:
            motivo = "Tema inativo."
        elif int(tema["nivel"]) < config["nivel_minimo"]:
            motivo = "Disciplina não é elegível para publicação."
        elif config["sem_descendente_ativo"] and identificador in pais_ativos:
            motivo = "Tema com descendentes ativos; revisar a especificidade."
        elif any(" " + _normalizar(expressao) + " " in titulo
                 for expressao in config["expressoes_titulo_generico"]):
            motivo = "Título genérico sinalizado pela regra; revisar a especificidade."
        else:
            motivo = ""
        motivos[identificador] = motivo
    return motivos


def dominio(registros: list[dict], atributos: list[str]) -> dict:
    if not registros:
        raise ValueError("Domínio exige referências de treinamento.")
    saida = {}
    for atributo in atributos:
        valores = [r[atributo] for r in registros]
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in valores):
            raise ValueError("Atributo não finito no domínio.")
        saida[atributo] = {"minimo": min(valores), "maximo": max(valores)}
    return saida


def dentro_dominio(registro: dict, faixas: dict) -> bool:
    for atributo, faixa in faixas.items():
        valor = registro[atributo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise ValueError("Atributo não finito na consulta.")
        if not faixa["minimo"] <= valor <= faixa["maximo"]:
            return False
    return True


def selecionar_politica(registros: list[dict], motivos: dict, config: dict) -> tuple[dict, list]:
    """Seleciona apenas pelo desenvolvimento crossfit; nenhuma consulta à reserva."""
    curvas = []
    for limiar in config["limiares_publicacao"]:
        retidos = [r for r in registros if not motivos[r["tema_sugerido_id"]]
                   and not r["sem_evidencia"] and r["dentro_dominio"]
                   and r["confianca"] >= limiar]
        n, k = len(retidos), sum(r["acerto"] for r in retidos)
        passa = (n >= config["suporte_minimo_publicacao"]
                 and k / n >= config["precisao_minima_desenvolvimento"])
        curvas.append({
            "limiar": limiar, "publicadas": n, "acertos": k,
            "precisao": k / n if n else None,
            "intervalo_wilson_95": wilson(k, n),
            "cobertura": n / len(registros) if registros else 0.0,
            "atende_criterios": passa,
        })
    candidatas = [c for c in curvas if c["atende_criterios"]]
    escolhida = min(candidatas, key=lambda c: (-c["publicadas"], c["limiar"])) if candidatas else None
    politica = {
        "schema": "politica_m4_v1", "publicacao_habilitada": escolhida is not None,
        "limiar": escolhida["limiar"] if escolhida else None,
        "suporte_minimo": config["suporte_minimo_publicacao"],
        "precisao_minima_desenvolvimento": config["precisao_minima_desenvolvimento"],
        "fora_automatico": False, "extras_previstos": [],
        "elegibilidade": config["elegibilidade"],
        "exigir_dominio_calibrador": True,
        "selecao": escolhida,
        "motivo_selecao": ("Maior cobertura entre limiares com suporte e precisão exigidos."
                           if escolhida else "Nenhum limiar atingiu suporte e precisão exigidos."),
    }
    return politica, curvas


def decidir(predicao: dict, politica: dict, motivos: dict) -> dict:
    if (politica.get("schema") != "politica_m4_v1"
            or politica.get("fora_automatico") is not False
            or politica.get("extras_previstos") != []):
        raise ValueError("Política incompatível com o procedimento congelado.")
    p = predicao["confianca"]
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Confiança inválida.")
    tema = predicao["tema_sugerido_id"]
    if tema not in motivos:
        raise ValueError("Tema sugerido ausente da taxonomia.")
    motivo = motivos[tema]
    if not motivo:
        if predicao["sem_evidencia"]:
            motivo = "Sem evidência suficiente para publicação; revisar sugestão."
        elif not predicao["dentro_dominio"]:
            motivo = "Caso fora da faixa observada na calibração; revisar sugestão."
        elif not politica["publicacao_habilitada"]:
            motivo = "Publicação automática sem suporte na validação; revisar sugestão."
        elif p < politica["limiar"]:
            motivo = "Confiança abaixo do mínimo de publicação; revisar sugestão."
    return {
        "id": predicao["id"], "decisao": "revisar" if motivo else "publicar",
        "tema_central_id": tema, "extras_ids": "", "confianca": p, "motivo": motivo,
    }


def medir_decisoes(registros: list[dict]) -> dict:
    publicadas = [r for r in registros if r["decisao"] == "publicar"]
    chamadas_fora = [r for r in registros if r["decisao"] == "fora"]
    n, k = len(publicadas), sum(r["acerto"] for r in publicadas)
    verdade_fora = [r for r in registros if r["referencia_fora"]]
    certas_fora = sum(r["referencia_fora"] for r in chamadas_fora)
    return {
        "total": len(registros),
        "decisoes": {d: sum(r["decisao"] == d for r in registros)
                     for d in ("publicar", "revisar", "fora")},
        "publicacao": {
            "n": n, "acertos": k, "erros": n - k,
            "precisao": k / n if n else None,
            "intervalo_wilson_95": wilson(k, n),
            "cobertura": n / len(registros) if registros else None,
        },
        "classificacao": {
            "acertos": {modo: sum(r["acertos"][modo] for r in registros)
                        for modo in ("ramo", "imediato", "exato")},
            "acertos_top5_ramo": sum(r["acerto_top_k_ramo"] for r in registros),
        },
        "calibracao": metricas([r["confianca"] for r in registros],
                              [r["acerto"] for r in registros]),
        "fora": {
            "referencias": len(verdade_fora), "chamadas": len(chamadas_fora),
            "acertos": certas_fora,
            "precisao": certas_fora / len(chamadas_fora) if chamadas_fora else None,
            "recall": certas_fora / len(verdade_fora) if verdade_fora else None,
        },
        "motivos_revisao": dict(sorted(Counter(
            r["motivo"] for r in registros if r["decisao"] == "revisar").items())),
    }
