"""Calibração numérica local, sem dependências opcionais nem acesso a modelos.

O objetivo soma a log-loss dos exemplos, a penalidade L2 dos coeficientes
(intercepto sem L2) e duas pseudo-observações no centro padronizado: um acerto
e um erro, ambos com peso 0,5. Na receita constante, a solução coincide com
a média posterior Beta(0,5; 0,5), (acertos + 0,5) / (n + 1). Não se trata
do prior de Jeffreys de uma regressão multivariada nem de Platt literal.

A média e o desvio populacional são estimados exclusivamente no treino
recebido. A regularização incide sobre coeficientes nessa escala. O ajuste
usa Newton com busca de passo de Armijo; alvos humanos continuam booleanos.
Convergência exige norma máxima do gradiente <= 1e-8 e decremento de Newton
g.T @ H^-1 @ g <= 1e-12. Isso evita exigir diferenças de objetivo menores
que a precisão de ponto flutuante, sem aceitar somente um passo pequeno.
"""

from __future__ import annotations

import math
from statistics import NormalDist


SCHEMA = "calibrador_m4_v1"
ATRIBUTOS = frozenset({"score", "margem"})
TOLERANCIA = 1e-8
TOLERANCIA_DECREMENTO = 1e-12
MAX_ITERACOES = 100
EPSILON_LOGLOSS = 1e-15
_CHAVES_MODELO = {
    "schema", "metodo", "atributos", "medias", "escalas", "coeficientes",
    "intercepto", "n", "acertos", "regularizacao", "pseudocontagens",
    "convergencia",
}


def _numero(valor: object, campo: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{campo} deve ser um número finito.")
    try:
        resultado = float(valor)
    except (OverflowError, ValueError):
        raise ValueError(f"{campo} deve ser um número finito.") from None
    if not math.isfinite(resultado):
        raise ValueError(f"{campo} deve ser um número finito.")
    return resultado


def _atributos(atributos: object) -> list[str]:
    if (
        not isinstance(atributos, list)
        or any(not isinstance(item, str) or item not in ATRIBUTOS for item in atributos)
        or len(set(atributos)) != len(atributos)
    ):
        raise ValueError("Atributos devem ser uma lista sem repetição de score e margem.")
    return atributos.copy()


def _sigmoide(valor: float) -> float:
    if valor >= 0.0:
        fator = math.exp(-valor)
        return 1.0 / (1.0 + fator)
    fator = math.exp(valor)
    return fator / (1.0 + fator)


def _softplus(valor: float) -> float:
    return max(valor, 0.0) + math.log1p(math.exp(-abs(valor)))


def _linear(coeficientes: list[float], linha: list[float]) -> float:
    try:
        resultado = math.fsum(a * b for a, b in zip(coeficientes, linha))
    except (OverflowError, ValueError):
        raise ValueError("Os atributos excederam o intervalo numérico suportado.") from None
    if not math.isfinite(resultado):
        raise ValueError("Os atributos excederam o intervalo numérico suportado.")
    return resultado


def _objetivo(
    parametros: list[float], linhas: list[list[float]], alvos: list[bool], penalidade: float,
) -> float:
    perdas = [
        _softplus(-_linear(parametros, linha) if alvo else _linear(parametros, linha))
        for linha, alvo in zip(linhas, alvos)
    ]
    perdas.extend((
        0.5 * _softplus(parametros[0]),
        0.5 * _softplus(-parametros[0]),
        0.5 * penalidade * math.fsum(valor * valor for valor in parametros[1:]),
    ))
    return math.fsum(perdas)


def _derivadas(
    parametros: list[float], linhas: list[list[float]], alvos: list[bool], penalidade: float,
) -> tuple[list[float], list[list[float]]]:
    dimensoes = len(parametros)
    gradiente = [0.0] * dimensoes
    hessiana = [[0.0] * dimensoes for _ in range(dimensoes)]
    for linha, alvo in zip(linhas, alvos):
        p = _sigmoide(_linear(parametros, linha))
        erro = p - float(alvo)
        variancia = p * (1.0 - p)
        for i in range(dimensoes):
            gradiente[i] += erro * linha[i]
            for j in range(dimensoes):
                hessiana[i][j] += variancia * linha[i] * linha[j]
    centro = _sigmoide(parametros[0])
    gradiente[0] += centro - 0.5
    hessiana[0][0] += centro * (1.0 - centro)
    for i in range(1, dimensoes):
        gradiente[i] += penalidade * parametros[i]
        hessiana[i][i] += penalidade
    return gradiente, hessiana


def _resolver(matriz: list[list[float]], vetor: list[float]) -> list[float]:
    """Eliminação gaussiana com pivoteamento para sistemas de até 3 parâmetros."""
    n = len(vetor)
    aumentado = [linha.copy() + [valor] for linha, valor in zip(matriz, vetor)]
    for coluna in range(n):
        pivo = max(range(coluna, n), key=lambda i: abs(aumentado[i][coluna]))
        if not math.isfinite(aumentado[pivo][coluna]) or aumentado[pivo][coluna] == 0.0:
            raise ValueError("Hessiana singular ou não finita na calibração.")
        aumentado[coluna], aumentado[pivo] = aumentado[pivo], aumentado[coluna]
        divisor = aumentado[coluna][coluna]
        aumentado[coluna] = [valor / divisor for valor in aumentado[coluna]]
        for i in range(n):
            if i != coluna:
                fator = aumentado[i][coluna]
                aumentado[i] = [
                    atual - fator * referencia
                    for atual, referencia in zip(aumentado[i], aumentado[coluna])
                ]
    solucao = [linha[-1] for linha in aumentado]
    if not all(math.isfinite(valor) for valor in solucao):
        raise ValueError("Passo não finito na calibração.")
    return solucao


def _otimizar(
    linhas: list[list[float]], alvos: list[bool], penalidade: float,
) -> tuple[list[float], int]:
    p = (sum(alvos) + 0.5) / (len(alvos) + 1.0)
    parametros = [math.log(p) - math.log1p(-p)] + [0.0] * (len(linhas[0]) - 1)
    for iteracao in range(MAX_ITERACOES + 1):
        gradiente, hessiana = _derivadas(parametros, linhas, alvos, penalidade)
        passo = _resolver(hessiana, gradiente)
        decr = math.fsum(a * b for a, b in zip(gradiente, passo))
        if (
            max(abs(valor) for valor in gradiente) <= TOLERANCIA
            and 0.0 <= decr <= TOLERANCIA_DECREMENTO
        ):
            return parametros, iteracao
        if iteracao == MAX_ITERACOES:
            break
        if decr <= 0.0 or not math.isfinite(decr):
            raise ValueError("Direção de Newton inválida na calibração.")
        anterior = _objetivo(parametros, linhas, alvos, penalidade)
        fator = 1.0
        for _ in range(60):
            candidato = [
                atual - fator * delta for atual, delta in zip(parametros, passo)
            ]
            objetivo = _objetivo(candidato, linhas, alvos, penalidade)
            if objetivo <= anterior - 1e-4 * fator * decr:
                break
            fator *= 0.5
        else:
            raise ValueError("Busca de passo não convergiu na calibração.")
        parametros = candidato
    raise ValueError("A calibração não convergiu em 100 iterações.")


def ajustar(
    registros: list[dict], atributos: list[str], regularizacao: float = 1.0,
) -> dict:
    """Ajusta P(acerto no ramo) usando apenas os registros de treino fornecidos."""
    atributos = _atributos(atributos)
    regularizacao = _numero(regularizacao, "regularizacao")
    if regularizacao <= 0.0:
        raise ValueError("regularizacao deve ser estritamente positiva.")
    if not isinstance(registros, list) or not registros:
        raise ValueError("O treino deve ser uma lista não vazia de registros.")
    alvos, dados = [], []
    for registro in registros:
        if not isinstance(registro, dict) or type(registro.get("acerto")) is not bool:
            raise ValueError("Cada registro de treino deve conter acerto booleano.")
        alvos.append(registro["acerto"])
        dados.append([_numero(registro.get(campo), campo) for campo in atributos])
    medias, escalas = [], []
    try:
        for indice in range(len(atributos)):
            valores = [linha[indice] for linha in dados]
            if all(valor == valores[0] for valor in valores):
                media, escala = valores[0], 1.0
            else:
                media = math.fsum(valores) / len(valores)
                escala = math.hypot(*(valor - media for valor in valores)) / math.sqrt(len(valores))
            medias.append(_numero(media, "média do treino"))
            escalas.append(_numero(escala, "desvio do treino") or 1.0)
    except (OverflowError, ValueError):
        raise ValueError("Escala dos atributos de treino excede o intervalo numérico.") from None
    linhas = [
        [1.0] + [
            _numero((valor - media) / escala, "atributo padronizado")
            for valor, media, escala in zip(linha, medias, escalas)
        ]
        for linha in dados
    ]
    n, acertos = len(alvos), sum(alvos)
    constante = not atributos or acertos in {0, n}
    if constante:
        probabilidade = (acertos + 0.5) / (n + 1.0)
        parametros = [
            math.log(probabilidade) - math.log1p(-probabilidade),
            *([0.0] * len(atributos)),
        ]
        iteracoes = 0
    else:
        parametros, iteracoes = _otimizar(linhas, alvos, regularizacao)
    modelo = {
        "schema": SCHEMA,
        "metodo": (
            "constante_pseudocontagens" if constante else "logistica_l2_pseudocontagens"
        ),
        "atributos": atributos,
        "medias": medias,
        "escalas": escalas,
        "coeficientes": parametros[1:],
        "intercepto": parametros[0],
        "n": n,
        "acertos": acertos,
        "regularizacao": regularizacao,
        "pseudocontagens": {"acertos": 0.5, "erros": 0.5, "local": "centro_padronizado"},
        "convergencia": {
            "convergiu": True, "iteracoes": iteracoes,
            "max_iteracoes": MAX_ITERACOES, "tolerancia": TOLERANCIA,
            "tolerancia_decremento": TOLERANCIA_DECREMENTO,
        },
    }
    validar_modelo(modelo)
    return modelo


def validar_modelo(modelo: dict) -> None:
    """Recusa modelos incompletos, incompatíveis ou numericamente inválidos."""
    if not isinstance(modelo, dict) or set(modelo) != _CHAVES_MODELO:
        raise ValueError("Esquema do calibrador incompleto ou com campos desconhecidos.")
    if modelo["schema"] != SCHEMA:
        raise ValueError("Versão do calibrador incompatível.")
    atributos = _atributos(modelo["atributos"])
    for campo in ("medias", "escalas", "coeficientes"):
        valores = modelo[campo]
        if not isinstance(valores, list) or len(valores) != len(atributos):
            raise ValueError(f"Dimensão inválida em {campo}.")
        for valor in valores:
            numero = _numero(valor, campo)
            if campo == "escalas" and numero <= 0:
                raise ValueError("Todas as escalas devem ser positivas.")
    _numero(modelo["intercepto"], "intercepto")
    if _numero(modelo["regularizacao"], "regularizacao") <= 0:
        raise ValueError("regularizacao deve ser estritamente positiva.")
    n, acertos = modelo["n"], modelo["acertos"]
    if type(n) is not int or n <= 0 or type(acertos) is not int or not 0 <= acertos <= n:
        raise ValueError("Contagens de treino inválidas.")
    if modelo["pseudocontagens"] != {
        "acertos": 0.5, "erros": 0.5, "local": "centro_padronizado",
    }:
        raise ValueError("Pseudocontagens incompatíveis.")
    convergencia = modelo["convergencia"]
    if (
        not isinstance(convergencia, dict)
        or set(convergencia) != {
            "convergiu", "iteracoes", "max_iteracoes", "tolerancia", "tolerancia_decremento",
        }
        or convergencia["convergiu"] is not True
        or type(convergencia["iteracoes"]) is not int
        or not 0 <= convergencia["iteracoes"] <= MAX_ITERACOES
        or type(convergencia["max_iteracoes"]) is not int
        or convergencia["max_iteracoes"] != MAX_ITERACOES
        or _numero(convergencia["tolerancia"], "tolerancia") != TOLERANCIA
        or _numero(convergencia["tolerancia_decremento"], "tolerancia_decremento") != TOLERANCIA_DECREMENTO
    ):
        raise ValueError("Metadados de convergência inválidos.")
    constante = not atributos or acertos in {0, n}
    metodo = "constante_pseudocontagens" if constante else "logistica_l2_pseudocontagens"
    if modelo["metodo"] != metodo:
        raise ValueError("Método incompatível com atributos ou contagens.")
    if constante:
        esperado = (acertos + 0.5) / (n + 1.0)
        if (
            any(valor != 0 for valor in modelo["coeficientes"])
            or not math.isclose(
                _sigmoide(modelo["intercepto"]), esperado, rel_tol=0.0, abs_tol=1e-14,
            )
            or convergencia["iteracoes"] != 0
        ):
            raise ValueError("Parâmetros da constante suavizada são inconsistentes.")


def prever(modelo: dict, registro: dict) -> float:
    """Aplica a transformação salva sem ajustar estatísticas do novo registro."""
    validar_modelo(modelo)
    if not isinstance(registro, dict):
        raise ValueError("O registro para previsão deve ser um objeto.")
    linha = [1.0]
    for campo, media, escala in zip(
        modelo["atributos"], modelo["medias"], modelo["escalas"],
    ):
        valor = _numero(registro.get(campo), campo)
        linha.append(_numero((valor - media) / escala, "atributo padronizado"))
    return _sigmoide(_linear([modelo["intercepto"], *modelo["coeficientes"]], linha))


def wilson(acertos: int, n: int, confianca: float = 0.95) -> dict | None:
    """Intervalo bilateral de Wilson para proporção; n=0 não tem estimativa."""
    if type(n) is not int or n < 0 or type(acertos) is not int or not 0 <= acertos <= n:
        raise ValueError("Wilson requer contagens inteiras e 0 <= acertos <= n.")
    confianca = _numero(confianca, "confianca")
    if not 0 < confianca < 1:
        raise ValueError("confianca deve estar estritamente entre zero e um.")
    try:
        z = NormalDist().inv_cdf((1.0 + confianca) / 2.0)
    except ValueError:
        raise ValueError("Nível de confiança fora da precisão numérica suportada.") from None
    if n == 0:
        return None
    p, z2 = acertos / n, z * z
    divisor = 1.0 + z2 / n
    centro = (p + z2 / (2.0 * n)) / divisor
    raio = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / divisor
    return {
        "inferior": 0.0 if acertos == 0 else max(0.0, centro - raio),
        "superior": 1.0 if acertos == n else min(1.0, centro + raio),
    }


def metricas(probabilidades: list[float], alvos: list[bool]) -> dict:
    """Brier, log-loss e ECE em cinco faixas fixas, inclusive com suporte zero."""
    if (
        not isinstance(probabilidades, list) or not isinstance(alvos, list)
        or len(probabilidades) != len(alvos)
        or any(type(alvo) is not bool for alvo in alvos)
    ):
        raise ValueError("Probabilidades e alvos booleanos devem ser listas de mesmo tamanho.")
    probabilidades = [_numero(p, "probabilidade") for p in probabilidades]
    if any(not 0 <= p <= 1 for p in probabilidades):
        raise ValueError("Probabilidades devem estar entre zero e um.")
    n, acertos = len(alvos), sum(alvos)
    limites = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    faixas = []
    for indice in range(5):
        membros = [
            (p, alvo) for p, alvo in zip(probabilidades, alvos)
            if limites[indice] <= p
            and (p < limites[indice + 1] or (indice == 4 and p <= 1.0))
        ]
        suporte = len(membros)
        certos = sum(alvo for _, alvo in membros)
        faixas.append({
            "inferior": limites[indice],
            "superior": limites[indice + 1],
            "inclui_superior": indice == 4,
            "n": suporte,
            "probabilidade_media": math.fsum(p for p, _ in membros) / suporte if suporte else None,
            "taxa_acerto": certos / suporte if suporte else None,
            "intervalo_wilson_95": wilson(certos, suporte),
        })
    perdas = []
    for p, alvo in zip(probabilidades, alvos):
        p = min(1.0 - EPSILON_LOGLOSS, max(EPSILON_LOGLOSS, p))
        perdas.append(-math.log(p) if alvo else -math.log1p(-p))
    return {
        "n": n,
        "acertos": acertos,
        "taxa_acerto": acertos / n if n else None,
        "brier": math.fsum((p - alvo) ** 2 for p, alvo in zip(probabilidades, alvos)) / n if n else None,
        "logloss": math.fsum(perdas) / n if n else None,
        "ece": math.fsum(
            faixa["n"] * abs(faixa["probabilidade_media"] - faixa["taxa_acerto"])
            for faixa in faixas if faixa["n"]
        ) / n if n else None,
        "intervalo_wilson_95": wilson(acertos, n),
        "epsilon_logloss": EPSILON_LOGLOSS,
        "faixas": faixas,
    }
