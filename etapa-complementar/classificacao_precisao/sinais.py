"""Seis evidências textuais de M8, sem modelos ou decisões de classificação.

O vocabulário e o IDF usam apenas título e termos do catálogo. Fontes em URL,
caminhos hierárquicos, gabaritos e metadados não são evidências. Artigos nunca
recebem uma norma inferida da disciplina ou de outro campo. A presença de uma
citação não confirma sua vigência, seu sentido jurídico ou a resposta correta.
"""

from collections import Counter
import math
import re
import unicodedata

from classificacao_local.citacoes import _NORMA, _ano_normalizado, _artigos


NOMES_ATRIBUTOS = (
    "instrumento_jaccard_corpo",
    "artigo_instrumento_jaccard_corpo",
    "cobertura_termos_distintivos_corpo",
    "cobertura_termos_distintivos_alternativas",
    "fracao_termos_titulo_corpo",
    "evidencia_normativa_exclusiva",
)

# Registro fechado, elaborado antes de métricas M8 e sem consultar questões.
# Ano ausente é completado SOMENTE para estes instrumentos verificados. Um ano
# explicitamente diferente nunca é substituído pelo ano registrado. Siglas são
# equivalentes textuais convencionais; não há mapeamento de um assunto à lei.
VERSAO_ALIASES = "instrumentos_m8_v1_2026-10-21"
ALIASES_INSTRUMENTOS = (
    ("decreto_lei:2848/1940", ("cp", "codigo penal"),
     "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm"),
    ("decreto_lei:3689/1941", ("cpp", "codigo de processo penal"),
     "https://www.planalto.gov.br/ccivil_03/decreto-lei/del3689.htm"),
    ("lei:7210/1984", ("lep", "lei de execucao penal"),
     "https://www.planalto.gov.br/ccivil_03/leis/l7210.htm"),
    ("decreto_lei:3688/1941", ("lcp", "lei das contravencoes penais"),
     "https://www.planalto.gov.br/ccivil_03/decreto-lei/del3688.htm"),
    ("lei:8069/1990", ("eca", "estatuto da crianca e do adolescente"),
     "https://www.planalto.gov.br/ccivil_03/leis/l8069.htm"),
    ("lei:8078/1990", ("cdc", "codigo de defesa do consumidor"),
     "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm"),
    ("lei:9503/1997", ("ctb", "codigo de transito brasileiro"),
     "https://www.planalto.gov.br/ccivil_03/leis/l9503compilado.htm"),
    ("lei:11343/2006", ("lei de drogas",),
     "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm"),
    ("lei:11340/2006", ("lei maria da penha",),
     "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11340.htm"),
    ("lei:10826/2003", ("estatuto do desarmamento",),
     "https://www.planalto.gov.br/ccivil_03/leis/2003/l10.826.htm"),
    ("lei:10741/2003", ("estatuto do idoso", "estatuto da pessoa idosa"),
     "https://www.planalto.gov.br/ccivil_03/leis/2003/l10.741.htm"),
    ("constituicao:federal/1988", (
        "cf", "cf/88", "cf/1988", "constituicao federal",
        "constituicao da republica federativa do brasil",
    ), "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"),
    ("lei:8137/1990", (), "https://www.planalto.gov.br/ccivil_03/leis/l8137.htm"),
    ("lei:1521/1951", (), "https://www.planalto.gov.br/ccivil_03/leis/l1521.htm"),
    ("lei:7492/1986", (), "https://www.planalto.gov.br/ccivil_03/leis/l7492.htm"),
    ("lei:12037/2009", (), "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/lei/l12037.htm"),
    ("lei:9296/1996", (), "https://www.planalto.gov.br/ccivil_03/leis/l9296.htm"),
    ("lei:9613/1998", (), "https://www.planalto.gov.br/ccivil_03/leis/l9613.htm"),
    ("lei:13260/2016", (), "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13260.htm"),
    ("lei:9455/1997", (), "https://www.planalto.gov.br/ccivil_03/leis/l9455.htm"),
    ("lei:4737/1965", ("codigo eleitoral",), "https://www.planalto.gov.br/ccivil_03/leis/l4737.htm"),
    ("lei:9605/1998", (), "https://www.planalto.gov.br/ccivil_03/leis/l9605.htm"),
    ("lei:12850/2013", (), "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12850.htm"),
    ("lei:11689/2008", (), "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2008/lei/l11689.htm"),
    ("lei:7960/1989", ("lei de prisao temporaria",), "https://www.planalto.gov.br/ccivil_03/leis/l7960.htm"),
    ("lei:13869/2019", ("lei de abuso de autoridade",), "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13869.htm"),
    ("lei:14344/2022", ("lei henry borel",), "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/lei/l14344.htm"),
    ("lei:11105/2005", (), "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2005/lei/l11105.htm"),
    ("lei:8072/1990", (), "https://www.planalto.gov.br/ccivil_03/leis/l8072.htm"),
    ("lei:7716/1989", (), "https://www.planalto.gov.br/ccivil_03/leis/l7716.htm"),
    ("lei:2889/1956", (), "https://www.planalto.gov.br/ccivil_03/leis/l2889.htm"),
    ("lei:9099/1995", (), "https://www.planalto.gov.br/ccivil_03/leis/l9099.htm"),
    ("lei:13431/2017", (), "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/lei/l13431.htm"),
)

_CONHECIDOS = {canonico.split("/")[0]: canonico
               for canonico, _, _ in ALIASES_INSTRUMENTOS}
_FONTES_NORMAS = {canonico: fonte for canonico, _, fonte in ALIASES_INSTRUMENTOS}
_PADROES = tuple(
    (re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, alias.split()))
                + r"(?!\w)"), canonico)
    for canonico, aliases, _ in ALIASES_INSTRUMENTOS for alias in aliases
)
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_DL = re.compile(r"\bdl(?=\s+(?:n[.º°o]?\s*)?\d)", re.IGNORECASE)
_SEGMENTO = re.compile(r"[;!?\n]+|(?<!\d)\.(?=\s+[^\d\s])")
_OUTRO_CODIGO = re.compile(r"\b(?:codigo|cpc|cc|ctn|cpm|cppm)\b")
_ANO_NOME = re.compile(r"\s*(?:/\s*|(?:,\s*)?de\s+)(\d{4}|\d{2})(?!\d)")
_PALAVRA = re.compile(r"[a-z0-9]+")
_VAZIAS = frozenset("a as ao aos o os e de da das do dos em na nas no nos para por "
                    "com sem um uma uns umas que se ou parte partes geral gerais "
                    "aspectos consideracoes disposicoes introducao nocoes".split())


def _normalizar(texto):
    # NFD mantém os ordinais º/ª necessários para a extração de artigos.
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold())
                   if unicodedata.category(c) != "Mn")


def _normas(texto):
    texto = _DL.sub("decreto lei", texto)
    resultado = set()
    for m in _NORMA.finditer(texto):
        tipo = m["tipo"]
        tipo = ("decreto_lei" if tipo.startswith("decreto") else
                "lei_complementar" if "complementar" in tipo else "lei")
        base = f"{tipo}:{int(m['numero'].replace('.', ''))}"
        ano = m["ano_barra"] or m["ano_extenso"]
        resultado.add(base + "/" + _ano_normalizado(ano) if ano else
                      _CONHECIDOS.get(base, base))
    for padrao, canonico in _PADROES:
        # Um qualificador militar não deve ser confundido com o código comum.
        for m in padrao.finditer(texto):
            if (canonico.startswith("decreto_lei:")
                    and re.match(r"\s+militar\b", texto[m.end():])):
                continue
            ano = _ANO_NOME.match(texto, m.end())
            if ano and _ano_normalizado(ano[1]) != canonico.rsplit("/", 1)[1]:
                continue
            resultado.add(canonico)
    return frozenset(resultado)


def _outro_codigo(texto):
    # Citações de códigos não cadastrados impedem atribuir-lhes por engano o
    # único código conhecido do segmento. O instrumento desconhecido não vira
    # evidência positiva e nenhuma identidade legal é inventada.
    restante = texto
    for padrao, canonico in _PADROES:
        def apagar(m):
            if canonico.startswith("decreto_lei:") and re.match(r"\s+militar\b", texto[m.end():]):
                return m[0]
            ano = _ANO_NOME.match(texto, m.end())
            return m[0] if ano and _ano_normalizado(ano[1]) != canonico.rsplit("/", 1)[1] else " "
        # Cada substituição consulta posições do mesmo texto de entrada.
        texto = restante
        restante = padrao.sub(apagar, restante)
    return bool(_OUTRO_CODIGO.search(restante) or
                re.search(r"\bcf\s*/\s*\d", restante))


def _citacoes(campos):
    instrumentos, pares = set(), set()
    for campo in campos:
        texto = _URL.sub(" ", _normalizar(campo))
        instrumentos.update(_normas(texto))
        for segmento in _SEGMENTO.split(texto):
            normas = _normas(segmento)
            # Coocorrência conservadora; com duas normas, não há atribuição.
            if len(normas) == 1 and not _outro_codigo(segmento):
                norma = next(iter(normas))
                pares.update(f"{norma}|{artigo}" for artigo in _artigos(segmento))
    return frozenset(instrumentos), frozenset(pares)


def _tokens(texto):
    return tuple(_PALAVRA.findall(_normalizar(_URL.sub(" ", texto))))


def _informativos(texto):
    return frozenset(t for t in _tokens(texto)
                     if len(t) > 1 and not t.isdigit() and t not in _VAZIAS)


def _unidades(textos):
    """Unigramas informativos e frases completas, sem radicalização inferida."""
    unidades = {(t,) for texto in textos for t in _informativos(texto)}
    unidades.update(tokens for texto in textos
                     if len(tokens := _tokens(texto)) > 1 and _informativos(texto))
    return frozenset(unidades)


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def _campos(q):
    if not isinstance(q, dict):
        raise TypeError("A consulta deve ser um dicionário de campos preparados.")
    corpo = tuple(q.get(campo) if isinstance(q.get(campo), str) else ""
                  for campo in ("enunciado", "comando"))
    alternativas = q.get("alternativas")
    # Identificadores das alternativas e quaisquer campos externos são ignorados.
    alternativas = tuple(sorted(v for v in alternativas.values() if isinstance(v, str))) \
        if isinstance(alternativas, dict) else ()
    return corpo, alternativas


class Sinais:
    """IDF temático fixo; a consulta é memorizada só pelo texto permitido.

    Atributos de normas usam apenas enunciado/comando. A sexta feature vale 1
    apenas quando ambos os lados citam a mesma e única norma, sem pares de
    artigos explicitamente disjuntos quando ambos os lados os fornecem. As coberturas
    lexicais são médias ponderadas por log((1+N)/(1+df))+1; df usa exclusivamente
    os candidatos ativos do catálogo. Frases não atravessam fronteiras de campo.
    Nenhum estado/objeto recebido é alterado, e cada saída é uma lista nova.
    """

    def __init__(self, taxonomia_enriquecida, documentos_catalogo, ancoras=None):
        temas = taxonomia_enriquecida["por_id"]
        candidatos = {i: t for i, t in temas.items()
                      if t["status"] == "active" and int(t["nivel"]) > 0}
        descritores = {}
        for documento in documentos_catalogo:
            for r in documento["registros"]:
                if r["tema_id"] in descritores or r["tema_id"] not in candidatos:
                    raise ValueError("Descritor duplicado ou fora dos candidatos.")
                if (not isinstance(r.get("termos"), list)
                        or any(not isinstance(t, str) for t in r["termos"])):
                    raise ValueError("Os termos do catálogo devem ser textos.")
                descritores[r["tema_id"]] = r
        if set(descritores) != set(candidatos) or not candidatos:
            raise ValueError("O catálogo deve cobrir todos os candidatos ativos.")
        self._temas = {}
        contagem = Counter()
        for i in sorted(candidatos):
            t, r = candidatos[i], descritores[i]
            if any(not isinstance(t.get(c), str) for c in ("titulo", "descricao")):
                raise ValueError("Título e descrição devem ser textos.")
            unidades = _unidades([t["titulo"], *r["termos"]])
            contagem.update(unidades)
            # Descrição já enriquecida pode conter todos os termos numa frase.
            # Usa-se o descritor original para preservar fronteiras dos termos.
            descricao = r.get("descricao", "")
            if not isinstance(descricao, str):
                raise ValueError("A descrição do catálogo deve ser texto.")
            citacoes = _citacoes([t["titulo"], descricao, *r["termos"]])
            self._temas[i] = (unidades, _informativos(t["titulo"]), citacoes)
        if ancoras is not None:
            if (ancoras.get("schema") != "ancoras_normativas_m8_v1"
                    or ancoras.get("questoes_ou_rotulos_consultados") is not False
                    or ancoras.get("procedimento") != "LLM_preparacao_somente_taxonomia_e_legislacao"):
                raise ValueError("Procedência das âncoras incompatível com preparação cega.")
            registrados = set()
            for ancora in ancoras["registros"]:
                i, norma = ancora["tema_id"], ancora["instrumento"]
                artigos = ancora["artigos"]
                if (i not in self._temas or (i, norma) in registrados
                        or norma not in _CONHECIDOS.values()
                        or type(ancora.get("ambiguo")) is not bool
                        or not isinstance(artigos, list)
                        or any(not isinstance(a, str) or not re.fullmatch(r"art:[1-9]\d*(?:-[A-Z])?", a)
                               for a in artigos)
                        or len(artigos) != len(set(artigos))
                        or ancora.get("fonte") != _FONTES_NORMAS.get(norma)
                        or not isinstance(ancora.get("nota"), str)):
                    raise ValueError("Âncora normativa inválida ou duplicada.")
                registrados.add((i, norma))
                # Ambiguidade declarada impede uma associação inventada.
                if ancora["ambiguo"]:
                    continue
                unidades, titulo, (normas, pares) = self._temas[i]
                self._temas[i] = (unidades, titulo, (
                    normas | {norma}, pares | {f"{norma}|{a}" for a in artigos}))
        self._idf = {u: math.log((1 + len(candidatos)) / (1 + df)) + 1
                     for u, df in contagem.items()}
        self._pesos = {i: math.fsum(self._idf[u] for u in sorted(item[0]))
                       for i, item in self._temas.items()}
        self._tamanhos = tuple(sorted({len(u) for u in contagem}))
        self._cache = {}

    def _representar(self, campos):
        presentes, palavras = set(), set()
        for campo in campos:
            tokens = _tokens(campo)
            palavras.update(tokens)
            for n in self._tamanhos:
                presentes.update(u for j in range(len(tokens)-n+1)
                                 if (u := tokens[j:j+n]) in self._idf)
        return frozenset(presentes), frozenset(palavras)

    def atributos(self, q: dict, tema_id: str) -> list[float]:
        if tema_id not in self._temas:
            raise ValueError("Tema não é candidato ativo do catálogo.")
        corpo, alternativas = _campos(q)
        chave = corpo, alternativas
        if chave not in self._cache:
            self._cache[chave] = (self._representar(corpo),
                                  self._representar(alternativas), _citacoes(corpo))
        (uc, pc), (ua, _), (nc, ac) = self._cache[chave]
        unidades, titulo, (nt, at) = self._temas[tema_id]
        peso = self._pesos[tema_id]
        cobertura = lambda presentes: (math.fsum(self._idf[u] for u in sorted(unidades & presentes))
                                      / peso if peso else 0.0)
        return [
            _jaccard(nc, nt),
            _jaccard(ac, at),
            cobertura(uc),
            cobertura(ua),
            len(titulo & pc) / len(titulo) if titulo else 0.0,
            float(len(nc) == len(nt) == 1 and nc == nt
                  and not (ac and at and not ac & at)),
        ]

    def suporte_catalogo(self):
        """Diagnóstico agregado sem texto, IDs, questões ou rótulos."""
        valores = list(self._temas.values())
        return {
            "temas": len(valores),
            "temas_com_instrumentos": sum(bool(c[0]) for _, _, c in valores),
            "temas_com_pares_artigo_instrumento": sum(bool(c[1]) for _, _, c in valores),
            "temas_com_norma_unica": sum(len(c[0]) == 1 for _, _, c in valores),
            "temas_com_unidades_distintivas": sum(bool(u) for u, _, _ in valores),
            "temas_com_termos_titulo": sum(bool(t) for _, t, _ in valores),
            "unidades_distintas": len(self._idf),
            "aliases_versao": VERSAO_ALIASES,
        }
