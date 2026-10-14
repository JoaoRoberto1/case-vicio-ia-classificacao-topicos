"""Inferência finita, condicional à referência local de revisão.

Modelo hipergeométrico sem reposição e inversão de caudas inclusivas:
https://www.itl.nist.gov/div898/software/dataplot/refman2/ch8/hypcdf.pdf
https://cran.r-project.org/web/packages/samplingbook/vignettes/Sprop-remarks.html

A cauda superior é P(X >= k) = 1 - F(k - 1). Os intervalos cobrem somente
incerteza amostral; não incorporam erro da referência nem validam publicação.
"""

from __future__ import annotations

from fractions import Fraction
from math import comb


def _contagem(nome: str, valor: int) -> None:
    if type(valor) is not int or valor < 0:
        raise ValueError(f"{nome} deve ser um inteiro não negativo; booleanos não são contagens.")


def _nivel_exato(nivel: float | Fraction) -> Fraction:
    if isinstance(nivel, bool) or not isinstance(nivel, (int, float, Fraction)):
        raise ValueError("O nível de confiança deve ser numérico, finito e estar entre 0 e 1.")
    try:
        # str(0.95) representa o nível decimal pretendido, sem o erro binário
        # que poderia excluir uma cauda exatamente igual a 1/40.
        resultado = Fraction(str(nivel))
    except (ValueError, ZeroDivisionError):
        raise ValueError("O nível de confiança deve ser numérico, finito e estar entre 0 e 1.") from None
    if not 0 < resultado < 1:
        raise ValueError("O nível de confiança deve estar estritamente entre 0 e 1.")
    return resultado


def intervalo_erros_hipergeometrico(
    N: int, n: int, k: int, nivel: float | Fraction = 0.95
) -> tuple[int, int]:
    """Limites inteiros para o total de erros K em uma população de tamanho N.

    Observam-se k erros numa amostra aleatória simples, sem reposição, de
    tamanho n fixado antes da inspeção dos resultados. Cada K compatível com
    k <= K <= N - n + k é aceito se ambas as caudas inclusivas têm probabilidade
    >= (1 - nivel)/2. O intervalo é exato, possivelmente conservador devido à
    distribuição discreta. Nenhuma aproximação de ponto flutuante decide seus
    limites. N=0 admite apenas n=k=0; n=0 devolve todo o suporte [0, N].
    """
    for nome, valor in (("N", N), ("n", n), ("k", k)):
        _contagem(nome, valor)
    if n > N:
        raise ValueError("O tamanho da amostra n não pode exceder a população N.")
    if k > n:
        raise ValueError("A contagem de erros k não pode exceder a amostra n.")
    confianca = _nivel_exato(nivel)
    if n == N:
        return k, k
    if n == 0:
        return 0, N

    cauda_minima = (1 - confianca) / 2
    denominador = comb(N, n)
    limiar = cauda_minima.numerator * denominador
    multiplicador = cauda_minima.denominator
    inferior = superior = None
    for K in range(k, N - n + k + 1):
        inferior_num = superior_num = 0
        inicio, fim = max(0, n - (N - K)), min(n, K)
        for j in range(inicio, fim + 1):
            massa_num = comb(K, j) * comb(N - K, n - j)
            if j <= k:
                inferior_num += massa_num
            if j >= k:
                superior_num += massa_num
        if inferior_num * multiplicador >= limiar and superior_num * multiplicador >= limiar:
            if inferior is None:
                inferior = K
            superior = K
    if inferior is None or superior is None:
        raise ArithmeticError("A inversão hipergeométrica não encontrou parâmetros compatíveis.")
    return inferior, superior


def estimar_precisao(
    D: int,
    erros_D: int,
    inconclusivos_D: int,
    N: int,
    n: int,
    erros_amostra: int,
    inconclusivos_amostra: int,
    nivel: float | Fraction = 0.95,
) -> dict:
    """Combina um estrato censitado D e uma amostra aleatória do estrato N.

    D e N são quantidades de publicados, não de todas as questões disponíveis.
    O estrato D é revisado integralmente. No restante, n é fixado previamente e
    a amostra é aleatória simples sem reposição. A versão e a população devem
    permanecer congeladas durante a auditoria.

    Conservador conta inconclusivos como erros; otimista conta-os como acertos.
    Nenhum cenário descarta inconclusivos do denominador. São hipóteses sobre
    a referência local, não limites para erros desconhecidos dessa referência.
    Frações exatas são expostas além dos floats, sem arredondamento decimal.
    """
    contagens = {
        "D": D, "erros_D": erros_D, "inconclusivos_D": inconclusivos_D,
        "N": N, "n": n, "erros_amostra": erros_amostra,
        "inconclusivos_amostra": inconclusivos_amostra,
    }
    for nome, valor in contagens.items():
        _contagem(nome, valor)
    if n > N:
        raise ValueError("O tamanho da amostra n não pode exceder a população N.")
    if erros_D + inconclusivos_D > D:
        raise ValueError("Erros e inconclusivos do estrato D não podem exceder seu total.")
    if erros_amostra + inconclusivos_amostra > n:
        raise ValueError("Erros e inconclusivos da amostra não podem exceder n.")
    confianca = _nivel_exato(nivel)
    total = D + N
    if total == 0:
        status = "sem_publicadas"
    elif n == N:
        status = "censo"
    elif n == 0:
        status = "sem_amostra_restante"
    else:
        status = "estimativa_amostral"

    cenarios = {}
    for nome, d, k in (
        ("conservador", erros_D + inconclusivos_D, erros_amostra + inconclusivos_amostra),
        ("otimista", erros_D, erros_amostra),
    ):
        K_L, K_U = intervalo_erros_hipergeometrico(N, n, k, confianca)
        ponto = None
        intervalo = None
        if total:
            intervalo = (Fraction(total - d - K_U, total), Fraction(total - d - K_L, total))
            if N == 0:
                ponto = Fraction(D - d, total)
            elif n > 0:
                ponto = Fraction(D - d, total) + Fraction(N * (n - k), n * total)
        cenarios[nome] = {
            "tratamento_inconclusivos": "erro" if nome == "conservador" else "acerto",
            "erros_D": d,
            "erros_amostra": k,
            "intervalo_erros_restante": [K_L, K_U],
            "ponto": float(ponto) if ponto is not None else None,
            "ponto_exato": str(ponto) if ponto is not None else None,
            "intervalo": [float(limite) for limite in intervalo] if intervalo is not None else None,
            "intervalo_exato": [str(limite) for limite in intervalo] if intervalo is not None else None,
        }
    return {
        "metodo": "inversao_exata_hipergeometrica_caudas_inclusivas",
        "nivel_confianca": float(confianca),
        "nivel_confianca_exato": str(confianca),
        "total_publicadas": total,
        "status": status,
        "contagens": contagens,
        "intervalos_condicionais_referencia": True,
        "inclui_incerteza_referencia": False,
        "cenarios": cenarios,
        "limites": [
            "Inferência condicional à referência local; não inclui erro dessa referência nem constitui avaliação oficial.",
            "O estrato D foi censitado; somente a amostra aleatória simples sem reposição do estrato N é extrapolada.",
            "A validade amostral exige tamanho definido previamente e população e política congeladas durante a auditoria.",
            "Conservador e otimista mantêm inconclusivos no denominador; são cenários distintos, não calibração da referência.",
            "Se N > 0 e n = 0, seu total de erros permanece entre 0 e N e não há estimativa pontual.",
            "Sem publicados, a precisão e seu intervalo são indefinidos.",
        ],
    }
