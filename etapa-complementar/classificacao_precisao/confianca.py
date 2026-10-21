"""Confiança numérica e seleção conjunta aprendidas apenas no treino recebido.

A logística usa L2=1 e duas pseudo-observações no centro padronizado, uma
positiva e outra negativa, com peso 0,5. Isso coincide com a suavização de
Jeffreys na constante; não é o prior de Jeffreys multivariado. A escala é
estimada só no treino. A seleção recebe probabilidades cross-fit em
``confianca_oof``; a aplicação usa exclusivamente ``confianca``.

Uma taxa do grupo selecionado não é confiança calibrada de cada registro.
A avaliação externa, antes de habilitar publicação, cabe ao chamador.
"""

from __future__ import annotations

import math

from classificacao_catalogo.selecao import medir
from classificacao_decisao.calibracao import (
    _derivadas, _linear, _numero, _objetivo, _resolver, _sigmoide,
)


SCHEMA = "confianca_logistica_m8_v1"
REGULARIZACAO = 1.0
MAX_ITERACOES = 300
TOLERANCIA = 1e-8
TOLERANCIA_DECREMENTO = 1e-12
QUANTIS = (0.5, 0.65, 0.8, 0.9)
CORTES_CONFIANCA = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
SUPORTE_MINIMO = 10
PRECISAO_MINIMA = 0.95
REGRAS = frozenset(
    [f"{campo}_q{round(q * 100)}" for campo in ("score", "margem") for q in QUANTIS]
    + [f"confianca_p{round(c * 100)}" for c in CORTES_CONFIANCA]
    + ["consenso", "consenso_margem_q50", "evidencia_50_margem_q50", "consenso_evidencia_25"]
)
_CHAVES_MODELO = {
    "schema", "metodo", "dimensoes", "medias", "escalas", "coeficientes",
    "intercepto", "n", "acertos", "regularizacao", "pseudocontagens", "convergencia",
}
_PSEUDOCONTAGENS = {"acertos": 0.5, "erros": 0.5, "local": "centro_padronizado"}


def _atributos(p: dict, dimensoes: int | None = None) -> list[float]:
    if not isinstance(p, dict):
        raise ValueError("A predição deve ser um objeto.")
    valores = p.get("atributos_confianca")
    if not isinstance(valores, list) or not 6 <= len(valores) <= 10:
        raise ValueError("atributos_confianca deve conter de 6 a 10 números finitos.")
    if dimensoes is not None and len(valores) != dimensoes:
        raise ValueError("Dimensão dos atributos incompatível com o treino.")
    return [_numero(valor, "atributos_confianca") for valor in valores]


def _otimizar(linhas: list[list[float]], alvos: list[bool]) -> tuple[list[float], int]:
    p = (sum(alvos) + 0.5) / (len(alvos) + 1.0)
    parametros = [math.log(p) - math.log1p(-p)] + [0.0] * (len(linhas[0]) - 1)
    for iteracao in range(MAX_ITERACOES + 1):
        gradiente, hessiana = _derivadas(parametros, linhas, alvos, REGULARIZACAO)
        passo = _resolver(hessiana, gradiente)
        decremento = math.fsum(a * b for a, b in zip(gradiente, passo))
        if (max(abs(v) for v in gradiente) <= TOLERANCIA
                and 0.0 <= decremento <= TOLERANCIA_DECREMENTO):
            return parametros, iteracao
        if iteracao == MAX_ITERACOES:
            break
        if not math.isfinite(decremento) or decremento <= 0.0:
            raise ValueError("Direção de Newton inválida na confiança.")
        anterior = _objetivo(parametros, linhas, alvos, REGULARIZACAO)
        fator = 1.0
        for _ in range(60):
            candidato = [atual - fator * delta for atual, delta in zip(parametros, passo)]
            objetivo = _objetivo(candidato, linhas, alvos, REGULARIZACAO)
            if objetivo <= anterior - 1e-4 * fator * decremento:
                break
            fator *= 0.5
        else:
            raise ValueError("Busca de passo não convergiu na confiança.")
        parametros = candidato
    raise ValueError("A confiança não convergiu em 300 iterações.")


def ajustar(ps: list[dict]) -> dict:
    """Ajusta P(acerto no ramo), sem buscar dados externos ao treino fornecido."""
    if not isinstance(ps, list) or not ps:
        raise ValueError("O treino deve ser uma lista não vazia.")
    dados, alvos = [], []
    dimensoes = None
    for p in ps:
        valores = _atributos(p, dimensoes)
        dimensoes = len(valores)
        if not isinstance(p.get("acertos"), dict) or type(p["acertos"].get("ramo")) is not bool:
            raise ValueError("O treino requer acertos.ramo booleano.")
        dados.append(valores)
        alvos.append(p["acertos"]["ramo"])
    medias, escalas = [], []
    try:
        for i in range(dimensoes):
            valores = [linha[i] for linha in dados]
            if all(v == valores[0] for v in valores):
                media, escala = valores[0], 1.0
            else:
                media = math.fsum(v / len(valores) for v in valores)
                escala = math.hypot(*(v - media for v in valores)) / math.sqrt(len(valores))
            medias.append(_numero(media, "média do treino"))
            escalas.append(_numero(escala, "desvio do treino") or 1.0)
        linhas = [[1.0] + [_numero((v - m) / s, "atributo padronizado")
                          for v, m, s in zip(linha, medias, escalas)] for linha in dados]
    except (OverflowError, ValueError):
        raise ValueError("Escala dos atributos de treino excede o intervalo numérico.") from None
    n, acertos = len(alvos), sum(alvos)
    constante = acertos in {0, n}
    if constante:
        p = (acertos + 0.5) / (n + 1.0)
        parametros = [math.log(p) - math.log1p(-p)] + [0.0] * dimensoes
        iteracoes = 0
    else:
        parametros, iteracoes = _otimizar(linhas, alvos)
    modelo = {
        "schema": SCHEMA,
        "metodo": "constante_pseudocontagens" if constante else "logistica_l2_pseudocontagens",
        "dimensoes": dimensoes, "medias": medias, "escalas": escalas,
        "coeficientes": parametros[1:], "intercepto": parametros[0],
        "n": n, "acertos": acertos, "regularizacao": REGULARIZACAO,
        "pseudocontagens": _PSEUDOCONTAGENS.copy(),
        "convergencia": {
            "convergiu": True, "iteracoes": iteracoes, "max_iteracoes": MAX_ITERACOES,
            "tolerancia": TOLERANCIA, "tolerancia_decremento": TOLERANCIA_DECREMENTO,
        },
    }
    validar_modelo(modelo)
    return modelo


def validar_modelo(modelo: dict) -> None:
    if not isinstance(modelo, dict) or set(modelo) != _CHAVES_MODELO or modelo["schema"] != SCHEMA:
        raise ValueError("Esquema do calibrador de confiança inválido.")
    d = modelo["dimensoes"]
    if type(d) is not int or not 6 <= d <= 10:
        raise ValueError("Dimensão de confiança inválida.")
    for campo in ("medias", "escalas", "coeficientes"):
        valores = modelo[campo]
        if not isinstance(valores, list) or len(valores) != d:
            raise ValueError("Dimensões do calibrador incompatíveis.")
        for v in valores:
            v = _numero(v, campo)
            if campo == "escalas" and v <= 0:
                raise ValueError("As escalas devem ser positivas.")
    _numero(modelo["intercepto"], "intercepto")
    if _numero(modelo["regularizacao"], "regularizacao") != REGULARIZACAO:
        raise ValueError("Regularização incompatível com o protocolo.")
    n, acertos = modelo["n"], modelo["acertos"]
    if type(n) is not int or n <= 0 or type(acertos) is not int or not 0 <= acertos <= n:
        raise ValueError("Contagens do treino inválidas.")
    if modelo["pseudocontagens"] != _PSEUDOCONTAGENS:
        raise ValueError("Pseudocontagens incompatíveis.")
    convergencia = modelo["convergencia"]
    if (not isinstance(convergencia, dict)
            or set(convergencia) != {"convergiu", "iteracoes", "max_iteracoes", "tolerancia", "tolerancia_decremento"}
            or convergencia["convergiu"] is not True
            or type(convergencia["iteracoes"]) is not int
            or not 0 <= convergencia["iteracoes"] <= MAX_ITERACOES
            or type(convergencia["max_iteracoes"]) is not int
            or convergencia["max_iteracoes"] != MAX_ITERACOES
            or _numero(convergencia["tolerancia"], "tolerancia") != TOLERANCIA
            or _numero(convergencia["tolerancia_decremento"], "tolerancia_decremento") != TOLERANCIA_DECREMENTO):
        raise ValueError("Metadados de convergência inválidos.")
    constante = acertos in {0, n}
    esperado = "constante_pseudocontagens" if constante else "logistica_l2_pseudocontagens"
    if modelo["metodo"] != esperado:
        raise ValueError("Método incompatível com o treino.")
    if constante and (any(v != 0 for v in modelo["coeficientes"])
                       or convergencia["iteracoes"] != 0
                       or not math.isclose(_sigmoide(modelo["intercepto"]), (acertos + 0.5) / (n + 1.0),
                                           rel_tol=0.0, abs_tol=1e-14)):
        raise ValueError("Constante suavizada inconsistente.")


def prever(modelo: dict, p: dict) -> float:
    """Prediz só com atributos; não consulta rótulos, acertos ou partições."""
    validar_modelo(modelo)
    valores = _atributos(p, modelo["dimensoes"])
    linha = [1.0] + [_numero((v - m) / s, "atributo padronizado")
                      for v, m, s in zip(valores, modelo["medias"], modelo["escalas"])]
    return _sigmoide(_linear([modelo["intercepto"], *modelo["coeficientes"]], linha))


def _probabilidade(valor: object, campo: str) -> float:
    valor = _numero(valor, campo)
    if not 0 <= valor <= 1:
        raise ValueError(f"{campo} deve estar entre zero e um.")
    return valor


def _booleano(p: dict, campo: str) -> bool:
    if type(p.get(campo)) is not bool:
        raise ValueError(f"{campo} deve ser booleano.")
    return p[campo]


def _predicoes(ps: object) -> dict:
    if not isinstance(ps, list) or not ps:
        raise ValueError("Cada receita deve conter predições internas.")
    particoes = {}
    for p in ps:
        if (not isinstance(p, dict) or not isinstance(p.get("acertos"), dict)
                or any(type(p["acertos"].get(m)) is not bool for m in ("ramo", "exato"))):
            raise ValueError("A seleção requer acertos booleanos de ramo e exato.")
        if not isinstance(p.get("id"), str) or not p["id"] or p["id"] in particoes:
            raise ValueError("IDs internos devem ser textos únicos não vazios.")
        particao = p.get("particao_interna")
        if not ((isinstance(particao, str) and particao) or (type(particao) is int and particao >= 0)):
            raise ValueError("Cada registro deve identificar sua partição interna.")
        particoes[p["id"]] = particao
        for campo in ("score", "margem"):
            _numero(p.get(campo), campo)
        _booleano(p, "consenso")
        for campo in ("confianca_oof", "evidencia_especifica"):
            _probabilidade(p.get(campo), campo)
    return particoes


def _aceitar(p: dict, regra: str, corte: object, campo_confianca: str) -> bool:
    if regra == "consenso":
        return _booleano(p, "consenso")
    if regra.startswith("confianca_p"):
        return _probabilidade(p.get(campo_confianca), campo_confianca) >= _probabilidade(corte, "corte")
    if regra == "consenso_evidencia_25":
        return _booleano(p, "consenso") and _probabilidade(p.get("evidencia_especifica"), "evidencia_especifica") >= 0.25
    if regra == "consenso_margem_q50":
        return _booleano(p, "consenso") and _numero(p.get("margem"), "margem") >= _numero(corte, "corte")
    if regra == "evidencia_50_margem_q50":
        return (_probabilidade(p.get("evidencia_especifica"), "evidencia_especifica") >= 0.5
                and _numero(p.get("margem"), "margem") >= _numero(corte, "corte"))
    campo = regra.split("_q", 1)[0]
    return _numero(p.get(campo), campo) >= _numero(corte, "corte")


def selecionar(resultados: dict[str, list[dict]], prioridades: list[str]) -> dict:
    """Escolhe nos internos: suporte, precisão, acerto global e prioridade fixa."""
    if (not isinstance(resultados, dict) or not resultados or not isinstance(prioridades, list)
            or any(not isinstance(n, str) or not n for n in prioridades)
            or len(set(prioridades)) != len(prioridades) or set(resultados) != set(prioridades)):
        raise ValueError("Prioridades devem listar todas as receitas uma única vez.")
    ordem = {nome: i for i, nome in enumerate(prioridades)}
    globais, candidatos = {}, []
    particoes_esperadas = None
    for nome in prioridades:
        ps = resultados[nome]
        particoes = _predicoes(ps)
        if particoes_esperadas is None:
            particoes_esperadas = particoes
        elif particoes != particoes_esperadas:
            raise ValueError("As receitas devem cobrir os mesmos IDs nas mesmas partições.")
        globais[nome] = {m: sum(p["acertos"][m] for p in ps) for m in ("ramo", "exato")}
        regras, mediana_margem = [], None
        for campo in ("score", "margem"):
            valores = sorted(_numero(p[campo], campo) for p in ps)
            for q in QUANTIS:
                corte = valores[math.floor(q * (len(valores) - 1))]
                regras.append((f"{campo}_q{round(q * 100)}", corte))
                if campo == "margem" and q == 0.5:
                    mediana_margem = corte
        regras += [("consenso", None)]
        regras += [(f"confianca_p{round(c * 100)}", c) for c in CORTES_CONFIANCA]
        regras += [("consenso_margem_q50", mediana_margem),
                   ("evidencia_50_margem_q50", mediana_margem), ("consenso_evidencia_25", None)]
        for regra, corte in regras:
            aceitos = [p for p in ps if _aceitar(p, regra, corte, "confianca_oof")]
            n = len(aceitos)
            k = sum(p["acertos"]["ramo"] for p in aceitos)
            precisao = k / n if n else None
            candidatos.append({
                "receita": nome, "regra": regra, "corte": corte, "n": n, "k": k,
                "habilitada": n >= SUPORTE_MINIMO and precisao >= PRECISAO_MINIMA,
                "precisao_empirica": precisao,
                "probabilidade_condicional": precisao,
                "probabilidade_condicional_suavizada": (k + 0.5) / (n + 1) if n else None,
            })
    viaveis = [c for c in candidatos if c["habilitada"]]
    if viaveis:
        escolhida = min(viaveis, key=lambda c: (
            -c["n"], -c["precisao_empirica"], -globais[c["receita"]]["ramo"],
            -globais[c["receita"]]["exato"], ordem[c["receita"]], c["regra"],
        ))
    else:
        nome = min(prioridades, key=lambda n: (-globais[n]["ramo"], -globais[n]["exato"], ordem[n]))
        escolhida = {
            "receita": nome, "regra": None, "corte": None, "n": 0, "k": 0, "habilitada": False,
            "precisao_empirica": None, "probabilidade_condicional": None,
            "probabilidade_condicional_suavizada": None,
        }
    return {**escolhida, "diagnosticos": candidatos,
            "interpretacao_probabilidade_condicional": "taxa_do_grupo_interno_nao_confianca_individual"}


def aplicar(p: dict, politica: dict) -> bool:
    """Aplica corte salvo; regra de confiança exige a previsão final, nunca OOF."""
    if not isinstance(politica, dict) or type(politica.get("habilitada")) is not bool:
        raise ValueError("Política sem indicador booleano de habilitação.")
    if not politica["habilitada"]:
        return False
    regra = politica.get("regra")
    if regra not in REGRAS:
        raise ValueError("Regra de seleção desconhecida.")
    if not isinstance(p, dict):
        raise ValueError("A predição deve ser um objeto.")
    return _aceitar(p, regra, politica.get("corte"), "confianca")
