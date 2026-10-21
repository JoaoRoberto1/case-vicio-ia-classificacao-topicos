"""Recuperação e ranker próprios; só aritmética sobre vetores já preparados."""

from copy import deepcopy
import math
import unicodedata

from classificacao_experimentos.entradas import hash_texto
from classificacao_local.classificador import CONFIG_PADRAO, _texto_tema, _texto_questao, _normalizar_rotulo
from classificacao_local.lexical import ajustar as ajustar_idf, transformar, similaridade
from .ranking import ajustar, pontuar

RECEITAS = ("enriquecido_lexical", "enriquecido_semantico", "enriquecido_rrf5",
            "enriquecido_rrf20", "aprendido", "aprendido_hierarquico")
GENERICOS = ("aspectos gerais", "consideracoes gerais", "disposicoes gerais",
             "introducao", "nocoes gerais", "principios gerais")


def _normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold())
                   if not unicodedata.combining(c))


def _cos(a, b):
    return min(1.0, max(0.0, math.fsum(x * y for x, y in zip(a, b)) /
                       math.sqrt(math.fsum(x*x for x in a) * math.fsum(y*y for y in b))))


def ancestral_comum(ids, taxonomia):
    """Recua somente quando os três candidatos concordam num ramo específico."""
    comuns = set.intersection(*(set(taxonomia["por_id"][i]["ancestrais_ids"]) | {i} for i in ids))
    validos = [i for i in comuns if taxonomia["por_id"][i]["status"] == "active"
               and int(taxonomia["por_id"][i]["nivel"]) > 0
               and not any(g in _normalizar(taxonomia["por_id"][i]["titulo"]) for g in GENERICOS)]
    return min(validos, key=lambda i: (-int(taxonomia["por_id"][i]["nivel"]), i)) if validos else None


class Representacao:
    """O ajuste não recebe questões: IDF fixado só no catálogo enriquecido.

    Memória de consultas acelera folds sem aprender delas. Rótulos só entram
    em treinar(), em pares de treino. Nenhum encoder é importado neste módulo.
    Caches devem ser verificados pelo carregador antes de construir o objeto.
    """

    def __init__(self, taxonomia, cache_original, cache_enriquecido):
        self.taxonomia = deepcopy(taxonomia)
        self.temas = sorted(i for i, t in self.taxonomia["por_id"].items()
                            if t["status"] == "active" and int(t["nivel"]) > 0)
        self.cache_original = cache_original
        self.cache_enriquecido = cache_enriquecido
        if set(self.temas) != set(cache_enriquecido["temas"]) or set(self.temas) != set(cache_original["temas"]):
            raise ValueError("Caches devem cobrir exatamente os candidatos.")
        textos = [_texto_tema(self.taxonomia["por_id"][i], CONFIG_PADRAO) for i in self.temas]
        self.idf = ajustar_idf(textos)
        self.catalogo = dict(zip(self.temas, [transformar(t, self.idf) for t in textos]))
        for i in self.temas:
            if cache_enriquecido["temas"][i]["texto_sha256"] != hash_texto("tema", self.taxonomia["por_id"][i]):
                raise ValueError("Descrição enriquecida diverge do cache preparado.")
        self.consultas = {}

    def atributos(self, q):
        assinatura = hash_texto("questao", q)
        vq = self.cache_original["questoes"].get(q["id"])
        if vq is None or vq["texto_sha256"] != assinatura:
            raise ValueError("Questão ausente ou texto diferente do cache preparado.")
        chave = q["id"], assinatura
        if chave not in self.consultas:
            lexq = transformar(_texto_questao(q, CONFIG_PADRAO), self.idf)
            lex = {i: similaridade(lexq, self.catalogo[i]) for i in self.temas}
            sem = {i: _cos(vq["vetor"], self.cache_enriquecido["temas"][i]["vetor"]) for i in self.temas}
            antigo = {i: _cos(vq["vetor"], self.cache_original["temas"][i]["vetor"]) for i in self.temas}
            rl = {i: n for n, i in enumerate(sorted(self.temas, key=lambda i: (-lex[i], i)), 1)}
            rs = {i: n for n, i in enumerate(sorted(self.temas, key=lambda i: (-sem[i], i)), 1)}
            xs = {i: [lex[i], sem[i], antigo[i], 21/(20+rl[i]), 21/(20+rs[i]),
                      lex[i]*sem[i], min(21/(20+rl[i]), 21/(20+rs[i])),
                      int(self.taxonomia["por_id"][i]["nivel"])/6] for i in self.temas}
            self.consultas[chave] = (xs, rl, rs)
        return self.consultas[chave]

    def treinar(self, questoes, rotulos):
        qs = {q["id"]: q for q in questoes}
        rs = {r["id"]: _normalizar_rotulo(r, set(self.temas)) for r in rotulos}
        if not qs or len(qs) != len(questoes) or len(rs) != len(rotulos) or set(qs) != set(rs):
            raise ValueError("Treino deve conter questões e rótulos únicos correspondentes.")
        pares = []
        for i in sorted(qs):
            xs, _, _ = self.atributos(qs[i])
            positivos = set() if rs[i]["fora_da_taxonomia"] else {rs[i]["tema_central_id"], *rs[i]["extras_ids"]}
            ordem = sorted(self.temas, key=lambda t: (-(xs[t][3]+xs[t][4]), t))
            pares.append([{"atributos": xs[t], "positivo": t in positivos} for t in ordem])
        return {"ranker": ajustar(pares, 8), "treino_ids": sorted(qs),
                "treino_textos": sorted({hash_texto("questao", q) for q in questoes})}

    def predizer(self, q, modelo, receita):
        if receita not in RECEITAS:
            raise ValueError("Receita não registrada.")
        if q["id"] in modelo["treino_ids"] or hash_texto("questao", q) in modelo["treino_textos"]:
            raise ValueError("Ressubstituição recusada: consulta faz parte do treino.")
        xs, rl, rs = self.atributos(q)
        if receita == "enriquecido_lexical":
            scores = {i: x[0] for i, x in xs.items()}
        elif receita == "enriquecido_semantico":
            scores = {i: x[1] for i, x in xs.items()}
        elif receita in ("enriquecido_rrf5", "enriquecido_rrf20"):
            k = 5 if receita.endswith("rrf5") else 20
            scores = {i: .5*(k+1)/(k+rl[i]) + .5*(k+1)/(k+rs[i]) for i in xs}
        else:
            scores = {i: pontuar(modelo["ranker"], x) for i, x in xs.items()}
        ordem = sorted(scores, key=lambda i: (-scores[i], i))
        escolhido = ordem[0]
        promovido = None
        if receita == "aprendido_hierarquico":
            promovido = ancestral_comum(ordem[:3], self.taxonomia)
            escolhido = promovido or escolhido
        # A margem é entre os dois primeiros da recuperação, inclusive na
        # variante hierárquica. É sinal bruto; a validação mede sua utilidade.
        return {"id": q["id"], "receita": receita, "tema_sugerido_id": escolhido,
                "score": scores[ordem[0]], "margem": scores[ordem[0]]-scores[ordem[1]],
                "consenso": rl[ordem[0]] == rs[ordem[0]] == 1,
                "sem_evidencia": max(x[0] for x in xs.values()) == 0 and max(x[1] for x in xs.values()) == 0,
                "recuou_na_hierarquia": escolhido != ordem[0],
                "nivel_sugerido": int(self.taxonomia["por_id"][escolhido]["nivel"]),
                "top_candidatos": [{"tema_id": i, "score": scores[i]} for i in ordem[:5]]}
