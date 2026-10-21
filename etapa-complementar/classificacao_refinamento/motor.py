"""Ranking numérico por campos e prior suave, com entradas previamente preparadas.

Não há geração de vetores, rede ou adjudicação de rótulos. O ajuste usa somente
catálogo e textos/rótulos de treino. Os escores são de ranking, não confiança.
O estado guarda cópias privadas das entradas: alterar um dict do chamador não
altera um motor já construído. A assinatura dos bytes do cache é conferida pelo
carregador; aqui são conferidos seu contrato, seus vetores e os textos usados.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import math
import re
import unicodedata

from classificacao_experimentos.entradas import hash_texto, texto_questao
from classificacao_local.classificador import (
    CONFIG_PADRAO, _normalizar_rotulo, _texto_tema,
)
from classificacao_local.lexical import termos as termos_palavras


_TOKEN = re.compile(r"[a-z0-9]+")
_CAMPOS_RECEITA = {"modo", "peso_char", "peso_semantico", "rrf_k", "peso_prior"}


def _tokens(texto: str) -> list[str]:
    normalizado = "".join(
        c for c in unicodedata.normalize("NFKD", texto.casefold())
        if not unicodedata.combining(c)
    )
    return _TOKEN.findall(normalizado)


def termos_caracteres(texto: str) -> list[str]:
    """char_wb 3–5: cada token [a-z0-9]+ recebe um espaço em cada ponta.

    Acentos e caixa são normalizados; não removemos palavras funcionais nesse
    espaço. Janelas nunca atravessam tokens, e tokens curtos não são repetidos
    para preencher n-gramas maiores que seu comprimento delimitado.
    """
    if not isinstance(texto, str):
        raise ValueError("Texto de caracteres deve ser uma string.")
    return [
        delimitado[inicio:inicio + n]
        for token in _tokens(texto)
        for delimitado in [" " + token + " "]
        for n in (3, 4, 5)
        for inicio in range(len(delimitado) - n + 1)
    ]


def _ajustar(documentos: list[str], tokenizador) -> dict[str, float]:
    frequencias: Counter = Counter()
    for texto in documentos:
        frequencias.update(set(tokenizador(texto)))
    return {
        t: math.log((1 + len(documentos)) / (1 + frequencias[t])) + 1.0
        for t in sorted(frequencias)
    }


def _transformar(texto: str, idf: dict, tokenizador) -> dict[str, float]:
    contagens = Counter(tokenizador(texto))
    vetor = {
        t: (1.0 + math.log(contagens[t])) * idf[t]
        for t in sorted(contagens) if t in idf
    }
    norma = math.sqrt(math.fsum(v * v for v in vetor.values()))
    return {t: v / norma for t, v in vetor.items()} if norma else {}


def _esparso(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return min(1.0, max(0.0, math.fsum(a[t] * b.get(t, 0.0) for t in sorted(a))))


def _cos(a: tuple, b: tuple, *, positivo: bool = True) -> float:
    normas = math.sqrt(math.fsum(x * x for x in a) * math.fsum(x * x for x in b))
    if not normas:
        return 0.0
    valor = math.fsum(x * y for x, y in zip(a, b)) / normas
    return min(1.0, max(0.0 if positivo else -1.0, valor))


def _sha_valido(valor) -> bool:
    return isinstance(valor, str) and bool(re.fullmatch(r"[0-9a-f]{64}", valor))


def _campos(q: dict) -> tuple[str, str, str]:
    # A rotina compartilhada valida ID, enunciado, comando e alternativas.
    texto = texto_questao(q)
    corpo = "\n".join((q["enunciado"], q["comando"]))
    alternativas = "\n".join(sorted(q["alternativas"].values()))
    assinatura = hashlib.sha256(" ".join(_tokens(texto)).encode("utf-8")).hexdigest()
    return corpo, alternativas, assinatura


def validar_receita(receita: dict) -> dict:
    if not isinstance(receita, dict) or set(receita) != _CAMPOS_RECEITA:
        raise ValueError("Receita deve fornecer exatamente os cinco parâmetros do refinamento.")
    if receita["modo"] != "campos":
        raise ValueError("O modo do refinamento deve ser campos.")
    escolhas = {"peso_char": (0.0, 0.3), "peso_semantico": (0.0, 0.5),
                "peso_prior": (0.0, 0.15)}
    for campo, valores in escolhas.items():
        valor = receita[campo]
        if (isinstance(valor, bool) or not isinstance(valor, (float, int))
                or not math.isfinite(valor) or valor not in valores):
            raise ValueError(f"Valor não registrado para {campo}.")
    if type(receita["rrf_k"]) is not int or receita["rrf_k"] not in (5, 20):
        raise ValueError("rrf_k deve ser 5 ou 20.")
    if receita["peso_prior"] and (
        receita["peso_char"] != 0.3 or receita["peso_semantico"] != 0.5
    ):
        raise ValueError("O prior foi registrado somente para a combinação palavra/char/E5.")
    return receita.copy()


class Motor:
    """Ajusta uma vez e reutiliza representações numéricas entre receitas.

    O cache pode conter questões fora do treino. Seus textos/vetores nunca entram
    no IDF ou nos centróides; cada consulta só é acessada quando predita. Apenas
    o tema central humano de treino fornece disciplina ao centróide supervisionado.
    Extras e metadados de origem não são atributos dessa receita.
    """

    __slots__ = (
        "_cache", "_dimensoes", "_cache_sha", "_ids_treino", "_textos_treino",
        "_temas", "_disciplinas", "_idf_palavras", "_idf_char", "_catalogo_palavras",
        "_catalogo_char", "_centroides", "_origem_centroides", "_consultas",
    )

    def __init__(self, questoes_treino: list, rotulos_treino: list,
                 taxonomia: dict, cache: dict):
        if (not isinstance(cache, dict) or not _sha_valido(cache.get("sha256"))
                or cache.get("schema") != "embeddings_e5_v1"
                or type(cache.get("dimensoes")) is not int or cache["dimensoes"] < 1):
            raise ValueError("Cache exige schema, dimensões e SHA256 previamente conferido.")
        self._dimensoes, self._cache_sha = cache["dimensoes"], cache["sha256"]
        self._cache = {}
        for grupo in ("questoes", "temas"):
            entradas = cache.get(grupo)
            if not isinstance(entradas, dict):
                raise ValueError(f"Índice de cache inválido: {grupo}.")
            self._cache[grupo] = {}
            for identificador, entrada in entradas.items():
                if (not isinstance(identificador, str) or not identificador
                        or identificador != identificador.strip()
                        or not isinstance(entrada, dict)
                        or not _sha_valido(entrada.get("texto_sha256"))):
                    raise ValueError("Entrada de cache com ID ou assinatura inválida.")
                vetor = entrada.get("vetor")
                if (not isinstance(vetor, list) or len(vetor) != self._dimensoes
                        or any(isinstance(v, bool) or not isinstance(v, (int, float))
                               or not math.isfinite(v) for v in vetor)
                        or not math.isclose(math.fsum(v * v for v in vetor), 1.0,
                                            abs_tol=1e-5, rel_tol=0.0)):
                    raise ValueError("Vetor de cache inválido ou não normalizado.")
                self._cache[grupo][identificador] = (entrada["texto_sha256"], tuple(vetor))
        if not isinstance(taxonomia, dict) or not isinstance(taxonomia.get("por_id"), dict):
            raise ValueError("Taxonomia deve fornecer por_id.")
        textos_temas, self._temas = [], {}
        for tema_id, tema in sorted(taxonomia["por_id"].items()):
            if (not isinstance(tema, dict) or tema.get("tema_id") != tema_id
                    or not isinstance(tema_id, str) or not tema_id
                    or tema.get("status") not in {"active", "inactive"}
                    or not isinstance(tema.get("nivel"), str) or not tema["nivel"].isdecimal()):
                raise ValueError("Registro inválido na taxonomia.")
            if tema["status"] != "active" or int(tema["nivel"]) == 0:
                continue
            disciplina = tema.get("disciplina")
            if not isinstance(disciplina, str) or not disciplina.strip():
                raise ValueError("Tema candidato deve fornecer disciplina da taxonomia.")
            texto = _texto_tema(tema, CONFIG_PADRAO)
            vetor = self._vetor("temas", tema_id, hash_texto("tema", tema))
            self._temas[tema_id] = (disciplina, vetor)
            textos_temas.append(texto)
        if not self._temas or set(self._cache["temas"]) != set(self._temas):
            raise ValueError("Cache deve cobrir exatamente os temas candidatos ativos.")
        self._disciplinas = tuple(sorted({d for d, _ in self._temas.values()}))
        if not isinstance(questoes_treino, list) or not isinstance(rotulos_treino, list):
            raise ValueError("Treino deve fornecer listas de questões e rótulos humanos.")
        questoes, campos = {}, {}
        for q in questoes_treino:
            corpo, alternativas, assinatura = _campos(q)
            if q["id"] in questoes:
                raise ValueError("ID repetido nas questões de treino.")
            questoes[q["id"]] = self._vetor("questoes", q["id"], hash_texto("questao", q))
            campos[q["id"]] = (corpo, alternativas, assinatura)
        rotulos = {}
        for r in rotulos_treino:
            normalizado = _normalizar_rotulo(r, set(self._temas))
            if normalizado["id"] in rotulos:
                raise ValueError("ID repetido nos rótulos de treino.")
            rotulos[normalizado["id"]] = normalizado
        if set(questoes) != set(rotulos):
            raise ValueError("Questões e rótulos de treino devem ter os mesmos IDs.")
        self._ids_treino = frozenset(questoes)
        self._textos_treino = frozenset(v[2] for v in campos.values())
        documentos = textos_temas + [
            texto for i in sorted(campos) for texto in campos[i][:2] if texto.strip()
        ]
        self._idf_palavras = _ajustar(documentos, termos_palavras)
        self._idf_char = _ajustar(documentos, termos_caracteres)
        self._catalogo_palavras = {
            i: _transformar(texto, self._idf_palavras, termos_palavras)
            for i, texto in zip(self._temas, textos_temas)
        }
        self._catalogo_char = {
            i: _transformar(texto, self._idf_char, termos_caracteres)
            for i, texto in zip(self._temas, textos_temas)
        }
        self._centroides, self._origem_centroides = {}, {}
        for disciplina in self._disciplinas:
            vetores = [questoes[i] for i in sorted(rotulos)
                       if not rotulos[i]["fora_da_taxonomia"]
                       and self._temas[rotulos[i]["tema_central_id"]][0] == disciplina]
            origem = "humanos_treino"
            if not vetores:
                vetores = [v for d, v in self._temas.values() if d == disciplina]
                origem = "catalogo_sem_suporte_humano"
            media = tuple(math.fsum(v[j] for v in vetores) / len(vetores)
                          for j in range(self._dimensoes))
            self._centroides[disciplina] = media
            self._origem_centroides[disciplina] = origem
        self._consultas = {}

    def _vetor(self, grupo: str, identificador: str, texto_sha: str) -> tuple:
        entrada = self._cache[grupo].get(identificador)
        if entrada is None or entrada[0] != texto_sha:
            raise ValueError(f"Texto ausente ou divergente no cache: {grupo}/{identificador}.")
        return entrada[1]

    def _similaridades(self, corpo: str, alternativas: str, idf: dict,
                        tokenizador, catalogo: dict) -> dict:
        partes = [(_transformar(corpo, idf, tokenizador), 0.75),
                  (_transformar(alternativas, idf, tokenizador), 0.25)]
        partes = [(v, peso) for v, peso in partes if v]
        denominador = math.fsum(peso for _, peso in partes)
        return {
            i: (math.fsum(peso * _esparso(v, tema) for v, peso in partes) / denominador
                if denominador else 0.0)
            for i, tema in catalogo.items()
        }

    def _consulta(self, questao: dict) -> tuple:
        corpo, alternativas, assinatura = _campos(questao)
        if questao["id"] in self._ids_treino or assinatura in self._textos_treino:
            raise ValueError("Ressubstituição recusada: ID ou texto coincide com o treino.")
        texto_sha = hash_texto("questao", questao)
        vetor = self._vetor("questoes", questao["id"], texto_sha)
        chave = (questao["id"], texto_sha)
        if chave not in self._consultas:
            palavras = self._similaridades(corpo, alternativas, self._idf_palavras,
                                          termos_palavras, self._catalogo_palavras)
            caracteres = self._similaridades(corpo, alternativas, self._idf_char,
                                             termos_caracteres, self._catalogo_char)
            semanticos = {i: _cos(vetor, v) for i, (_, v) in self._temas.items()}
            logits = {d: _cos(vetor, v, positivo=False) / 0.05
                      for d, v in self._centroides.items()}
            maior = max(logits.values())
            exponenciais = {d: math.exp(v - maior) for d, v in logits.items()}
            total = math.fsum(exponenciais.values())
            prior = {d: v / total for d, v in exponenciais.items()}
            self._consultas[chave] = (palavras, caracteres, semanticos, prior)
        return self._consultas[chave]

    def predizer(self, questao: dict, receita: dict, top_k: int = 5) -> dict:
        receita = validar_receita(receita)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k deve ser inteiro positivo.")
        palavras, caracteres, semanticos, prior = self._consulta(questao)
        pc, ps, pp = (receita[c] for c in ("peso_char", "peso_semantico", "peso_prior"))
        lexicais = {i: (1 - pc) * palavras[i] + pc * caracteres[i] for i in self._temas}
        ranks_lexicais = {i: n for n, i in enumerate(sorted(
            lexicais, key=lambda i: (-lexicais[i], i)), 1)}
        ranks_semanticos = {i: n for n, i in enumerate(sorted(
            semanticos, key=lambda i: (-semanticos[i], i)), 1)}
        candidatos, k = [], receita["rrf_k"]
        for i, (disciplina, _) in self._temas.items():
            score_catalogo = (
                math.fsum([(1 - ps) * (k + 1) / (k + ranks_lexicais[i]),
                           ps * (k + 1) / (k + ranks_semanticos[i])])
                if ps else lexicais[i]
            )
            score = (1 - pp) * score_catalogo + pp * prior[disciplina]
            candidatos.append({
                "tema_id": i, "score": score, "score_catalogo": score_catalogo,
                "similaridade_palavras": palavras[i], "similaridade_caracteres": caracteres[i],
                "similaridade_catalogo": lexicais[i], "similaridade_semantica": semanticos[i],
                "rank_lexical": ranks_lexicais[i], "rank_semantico": ranks_semanticos[i],
                "prior_disciplina": prior[disciplina] if pp else None,
            })
        candidatos.sort(key=lambda c: (-c["score"], c["tema_id"]))
        melhor = candidatos[0]
        evidencia = (melhor["similaridade_catalogo"] > 0
                     or ps > 0 and melhor["similaridade_semantica"] > 0)
        return {
            "id": questao["id"], "tema_sugerido_id": melhor["tema_id"],
            "score": melhor["score"],
            "margem": melhor["score"] - (candidatos[1]["score"] if len(candidatos) > 1 else 0.0),
            "sem_evidencia": not evidencia, "top_candidatos": candidatos[:top_k],
            "probabilidades_disciplinas": dict(prior) if pp else {},
            "origem_centroides": dict(self._origem_centroides) if pp else {},
        }
