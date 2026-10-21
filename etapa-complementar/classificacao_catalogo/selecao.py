"""Seleção conjunta de receita e abstenção, ajustada somente no treino interno.

As taxas e a probabilidade condicional descrevem o grupo aceito no ajuste.
Não são probabilidades calibradas de cada questão nem garantia de precisão
futura. A avaliação externa do procedimento é responsabilidade do chamador.
"""

from __future__ import annotations

import math

from classificacao_decisao.calibracao import wilson


QUANTIS = (0.5, 0.65, 0.8, 0.9)
SUPORTE_MINIMO = 10
PRECISAO_MINIMA = 0.95
REGRAS = frozenset(
    [f"{campo}_q{round(q * 100)}" for campo in ("score", "margem") for q in QUANTIS]
    + ["consenso"]
)


def _numero(valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Escores e cortes devem ser números finitos.")
    try:
        resultado = float(valor)
    except (ValueError, OverflowError):
        raise ValueError("Número fora do intervalo suportado.") from None
    if not math.isfinite(resultado):
        raise ValueError("Escores e cortes devem ser números finitos.")
    return resultado


def _alvos(p: dict) -> None:
    if (not isinstance(p, dict) or not isinstance(p.get("acertos"), dict)
            or any(type(p["acertos"].get(m)) is not bool for m in ("ramo", "exato"))):
        raise ValueError("Cada predição deve conter alvos booleanos de ramo e exato.")


def _predicoes(ps: object) -> list[dict]:
    if not isinstance(ps, list) or not ps:
        raise ValueError("Cada receita deve conter predições internas.")
    ids = set()
    for p in ps:
        _alvos(p)
        if not isinstance(p.get("id"), str) or not p["id"] or p["id"] in ids:
            raise ValueError("IDs internos devem ser textos únicos não vazios.")
        ids.add(p["id"])
        _numero(p.get("score"))
        _numero(p.get("margem"))
        if type(p.get("consenso")) is not bool:
            raise ValueError("O indicador de consenso deve ser booleano.")
    return ps


def selecionar(resultados: dict[str, list[dict]], prioridades: list[str]) -> dict:
    """Escolhe regra por cobertura, precisão e desempenho global, nessa ordem."""
    if (not isinstance(resultados, dict) or not resultados
            or not isinstance(prioridades, list)
            or any(not isinstance(nome, str) or not nome for nome in prioridades)
            or len(set(prioridades)) != len(prioridades)
            or set(resultados) != set(prioridades)):
        raise ValueError("Prioridades devem listar todas as receitas uma única vez.")
    ordem = {nome: i for i, nome in enumerate(prioridades)}
    globais, candidatos = {}, []
    ids_esperados = None
    for nome in prioridades:
        ps = _predicoes(resultados[nome])
        ids = {p["id"] for p in ps}
        if ids_esperados is None:
            ids_esperados = ids
        elif ids != ids_esperados:
            raise ValueError("As receitas devem cobrir as mesmas questões internas.")
        globais[nome] = {m: sum(p["acertos"][m] for p in ps) for m in ("ramo", "exato")}
        regras = []
        for campo in ("score", "margem"):
            valores = sorted(_numero(p[campo]) for p in ps)
            for q in QUANTIS:
                corte = valores[math.floor(q * (len(valores) - 1))]
                regras.append((f"{campo}_q{round(q * 100)}", corte,
                               [p for p in ps if p[campo] >= corte]))
        regras.append(("consenso", None, [p for p in ps if p["consenso"]]))
        for regra, corte, aceitos in regras:
            n = len(aceitos)
            k = sum(p["acertos"]["ramo"] for p in aceitos)
            precisao = k / n if n else None
            candidatos.append({
                "receita": nome, "regra": regra, "corte": corte,
                "n": n, "k": k,
                "habilitada": n >= SUPORTE_MINIMO and precisao >= PRECISAO_MINIMA,
                "precisao_empirica": precisao,
                "probabilidade_condicional": (k + 0.5) / (n + 1) if n else None,
            })

    viaveis = [c for c in candidatos if c["habilitada"]]
    if viaveis:
        escolhida = min(viaveis, key=lambda c: (
            -c["n"], -c["precisao_empirica"],
            -globais[c["receita"]]["ramo"], -globais[c["receita"]]["exato"],
            ordem[c["receita"]], c["regra"],
        ))
    else:
        nome = min(prioridades, key=lambda n: (
            -globais[n]["ramo"], -globais[n]["exato"], ordem[n],
        ))
        escolhida = {
            "receita": nome, "regra": None, "corte": None,
            "n": 0, "k": 0, "habilitada": False,
            "precisao_empirica": None, "probabilidade_condicional": None,
        }
    return {**escolhida, "diagnosticos": candidatos}


def aplicar(p: dict, politica: dict) -> bool:
    """Aplica a regra salva sem consultar rótulos nem reajustar o corte."""
    if not isinstance(politica, dict) or type(politica.get("habilitada")) is not bool:
        raise ValueError("Política sem indicador booleano de habilitação.")
    if not politica["habilitada"]:
        return False
    regra = politica.get("regra")
    if regra not in REGRAS:
        raise ValueError("Regra de seleção desconhecida.")
    if not isinstance(p, dict):
        raise ValueError("A predição deve ser um objeto.")
    if regra == "consenso":
        if type(p.get("consenso")) is not bool:
            raise ValueError("O indicador de consenso deve ser booleano.")
        return p["consenso"]
    campo = regra.split("_q", 1)[0]
    return _numero(p.get(campo)) >= _numero(politica.get("corte"))


def medir(ps: list[dict], decisoes: list[bool]) -> dict:
    """Mede somente decisões fornecidas; Wilson bilateral não certifica a meta."""
    if (not isinstance(ps, list) or not isinstance(decisoes, list)
            or len(ps) != len(decisoes) or any(type(d) is not bool for d in decisoes)):
        raise ValueError("Predições e decisões booleanas devem ter o mesmo comprimento.")
    for p in ps:
        _alvos(p)
    n = sum(decisoes)
    k = sum(p["acertos"]["ramo"] for p, d in zip(ps, decisoes) if d)
    return {
        "count": len(ps), "n": n, "k": k,
        "coverage": n / len(ps) if ps else None,
        "precision": k / n if n else None,
        "wilson95": wilson(k, n),
    }
