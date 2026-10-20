"""TF-IDF esparso, determinístico e sem dependências de aprendizado de máquina.

O vocabulário e o IDF pertencem exclusivamente aos documentos passados a
``ajustar``. ``transformar`` nunca aprende termos da consulta. Os bigramas
usam os tokens após a remoção da lista curta e fixa de palavras funcionais.
"""

from __future__ import annotations

from collections import Counter
import math
import re
import unicodedata


# Lista deliberadamente curta: negações, números e palavras jurídicas ficam.
STOPWORDS = frozenset(
    "a o as os um uma uns umas de da do das dos em na no nas nos "
    "ao aos e ou que se por para com como sua seu suas seus".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def termos(texto: str) -> list[str]:
    """Normaliza acentos/caixa e emite unigramas e bigramas identificáveis."""
    if not isinstance(texto, str):
        raise ValueError("O documento lexical deve ser uma string.")
    normalizado = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(caractere)
    )
    tokens = [
        token for token in _TOKEN.findall(normalizado) if token not in STOPWORDS
    ]
    return tokens + [
        f"{esquerda} {direita}" for esquerda, direita in zip(tokens, tokens[1:])
    ]


def ajustar(documentos: list[str]) -> dict[str, float]:
    """IDF = log((1 + número de documentos)/(1 + frequência documental)) + 1."""
    if not isinstance(documentos, list) or not documentos:
        raise ValueError("O ajuste lexical exige uma lista não vazia de documentos.")
    frequencias: Counter[str] = Counter()
    for documento in documentos:
        frequencias.update(set(termos(documento)))
    total = len(documentos)
    return {
        termo: math.log((1 + total) / (1 + frequencias[termo])) + 1.0
        for termo in sorted(frequencias)
    }


def transformar(texto: str, idf: dict[str, float]) -> dict[str, float]:
    """TF = 1 + log(contagem), seguido por IDF e normalização L2."""
    contagens = Counter(termos(texto))
    valores = {
        termo: (1.0 + math.log(contagens[termo])) * idf[termo]
        for termo in sorted(contagens)
        if termo in idf
    }
    norma = math.sqrt(math.fsum(valor * valor for valor in valores.values()))
    if not norma:
        return {}
    return {termo: valor / norma for termo, valor in valores.items()}


def similaridade(esquerda: dict[str, float], direita: dict[str, float]) -> float:
    """Produto escalar de vetores L2; ordem de soma independente do JSON."""
    if len(esquerda) > len(direita):
        esquerda, direita = direita, esquerda
    valor = math.fsum(
        esquerda[termo] * direita.get(termo, 0.0) for termo in sorted(esquerda)
    )
    return min(1.0, max(0.0, valor))


def termos_comuns(
    esquerda: dict[str, float], direita: dict[str, float], limite: int = 8
) -> list[str]:
    """Termos em comum, por contribuição ao produto escalar e desempate textual."""
    compartilhados = esquerda.keys() & direita.keys()
    return sorted(
        compartilhados,
        key=lambda termo: (-esquerda[termo] * direita[termo], termo),
    )[:limite]
