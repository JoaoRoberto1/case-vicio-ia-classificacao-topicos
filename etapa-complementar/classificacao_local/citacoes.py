"""Sinais lexicais locais de citações, sem interpretação ou validação jurídica.

O extrator não consulta modelos, não conhece temas e não decide classificações.
Números de leis e nomes de códigos são representações independentes: não há mapa
que infira, por exemplo, o nome de um código a partir do número de uma lei.

Convenções e perdas deliberadas:
* anos com dois dígitos usam o corte fixo 30 (30..99 -> 1930..1999; 00..29 ->
  2000..2029); é uma convenção textual, não a confirmação da data de uma norma;
* um ano só é associado à norma quando integra sua citação explícita;
* siglas são reconhecidas apenas em maiúsculas; nomes por extenso não dependem
  de caixa ou acentos;
* listas simples de artigos são lidas; intervalos conservam apenas os extremos
  escritos, sem gerar os artigos intermediários;
* parágrafos, incisos e alíneas não são extraídos;
* pares instrumento/artigo só são produzidos se houver um único instrumento
  normalizado em todo o texto recebido. São coocorrências desse campo, não uma
  resolução semântica de a qual norma cada artigo pertence.

Com mais de um instrumento, os sinais individuais continuam disponíveis, mas
não há pares. Nem a existência de uma norma/artigo nem sua vigência é validada.
"""

from __future__ import annotations

import re
import unicodedata


_NORMA = re.compile(
    r"\b(?P<tipo>decreto\s*[-–—]?\s*lei|lei\s+complementar|lei)\s+"
    r"(?:(?:n(?:[.]\s*)?[º°o]|numero|n[.])\s*)?"
    r"(?P<numero>\d+(?:[.]\d{3})*)(?!\w)"
    r"(?:"
    r"\s*/\s*(?P<ano_barra>\d{4}|\d{2})(?!\d)"
    r"|(?:,\s*|\s+)de\s+"
    r"(?:\d{1,2}[º°]?\s+de\s+[a-z]+\s+de\s+)?"
    r"(?P<ano_extenso>\d{4})(?!\d)"
    r")?",
    re.IGNORECASE,
)

_NOMES = (
    (re.compile(r"\bcodigo\s+de\s+processo\s+penal\b", re.IGNORECASE),
     "codigo:processo_penal"),
    (re.compile(r"\bcodigo\s+penal\b", re.IGNORECASE), "codigo:penal"),
    (re.compile(r"\bconstituicao\s+federal\b", re.IGNORECASE),
     "constituicao:federal"),
    (re.compile(r"\blei\s+de\s+execucao\s+penal\b", re.IGNORECASE),
     "lei_nome:execucao_penal"),
)

_SIGLAS = (
    (re.compile(r"\bCPP\b"), "codigo:processo_penal"),
    (re.compile(r"\bCP\b"), "codigo:penal"),
    (re.compile(r"\bCF(?:\s*/\s*(?:1988|88))?\b"),
     "constituicao:federal"),
    (re.compile(r"\bLEP\b"), "lei_nome:execucao_penal"),
)

_INICIO_ARTIGOS = re.compile(
    r"\b(?:artigos?|arts?[.]?)(?![a-z_])\s*", re.IGNORECASE
)
_ARTIGO = re.compile(
    r"(?P<numero>\d+)[º°ª]?"
    r"(?:(?:\s*[-–—]\s*(?P<sufixo_separado>[a-z]))"
    r"|(?P<sufixo_colado>[a-z]))?"
    r"(?!\w)(?![.]\d)",
    re.IGNORECASE,
)
_SEPARADOR_ARTIGOS = re.compile(
    r"\s*(?:,|\be\b|\ba\b|[-–—])\s*", re.IGNORECASE
)


def _sem_acentos(texto: str) -> str:
    # NFD preserva os indicadores ordinais º/ª, ao contrário de NFKD.
    return "".join(
        caractere for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def _ano_normalizado(ano: str) -> str:
    if len(ano) == 4:
        return ano
    valor = int(ano)
    return str((1900 if valor >= 30 else 2000) + valor)


def _instrumentos(texto: str) -> set[str]:
    encontrados: set[str] = set()
    for ocorrencia in _NORMA.finditer(texto):
        tipo = ocorrencia["tipo"].lower()
        if tipo.startswith("decreto"):
            tipo = "decreto_lei"
        elif "complementar" in tipo:
            tipo = "lei_complementar"
        else:
            tipo = "lei"
        numero = str(int(ocorrencia["numero"].replace(".", "")))
        ano = ocorrencia["ano_barra"] or ocorrencia["ano_extenso"]
        identificador = f"{tipo}:{numero}"
        if ano:
            identificador += f"/{_ano_normalizado(ano)}"
        encontrados.add(identificador)
    for padrao, identificador in (*_NOMES, *_SIGLAS):
        if padrao.search(texto):
            encontrados.add(identificador)
    return encontrados


def _artigos(texto: str) -> set[str]:
    encontrados: set[str] = set()
    for inicio in _INICIO_ARTIGOS.finditer(texto):
        posicao = inicio.end()
        while ocorrencia := _ARTIGO.match(texto, posicao):
            numero = str(int(ocorrencia["numero"]))
            sufixo = (
                ocorrencia["sufixo_separado"] or ocorrencia["sufixo_colado"]
            )
            identificador = f"art:{numero}"
            if sufixo:
                identificador += f"-{sufixo.upper()}"
            encontrados.add(identificador)
            separador = _SEPARADOR_ARTIGOS.match(texto, ocorrencia.end())
            if separador is None:
                break
            posicao = separador.end()
    return encontrados


def extrair_citacoes(texto: str) -> dict[str, list[str]]:
    """Retorna instrumentos, artigos e coocorrências inequívocas no campo.

    As três listas são únicas e ordenadas lexicograficamente. A função é pura:
    o mesmo texto sempre produz o mesmo resultado, sem arquivos, rede ou estado.
    O chamador deve fornecer um campo coerente, de preferência já sem HTML.
    """
    if not isinstance(texto, str):
        raise TypeError("O texto para extração de citações deve ser uma string.")
    texto_normalizado = _sem_acentos(texto)
    instrumentos = sorted(_instrumentos(texto_normalizado))
    artigos = sorted(_artigos(texto_normalizado))
    pares = (
        [f"{instrumentos[0]}|{artigo}" for artigo in artigos]
        if len(instrumentos) == 1 else []
    )
    return {"instrumentos": instrumentos, "artigos": artigos, "pares": pares}
