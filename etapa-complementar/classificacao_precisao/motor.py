"""Ranking numérico M8 com sinais específicos e embeddings previamente salvos."""

from copy import deepcopy
import math

from classificacao_catalogo.motor import Representacao, ancestral_comum
from classificacao_catalogo.ranking import ajustar, pontuar
from classificacao_experimentos.entradas import hash_texto
from classificacao_local.classificador import _normalizar_rotulo
from .sinais import Sinais

RECEITAS = ("baseline_m7", "sinais_small", "sinais_small_hierarquico",
            "large_rrf20", "sinais_large", "sinais_large_hierarquico")


class Motor:
    def __init__(self, taxonomia, cache_original, cache_enriquecido, documentos, cache_large=None, ancoras=None):
        self.base = Representacao(taxonomia, cache_original, cache_enriquecido)
        self.taxonomia = self.base.taxonomia
        self.temas = self.base.temas
        self.sinais = Sinais(taxonomia, documentos, ancoras) if ancoras is not None else Sinais(taxonomia, documentos)
        self.large = deepcopy(cache_large) if cache_large is not None else None
        self._consultas = {}
        self._normas_large = {}
        if self.large is not None:
            if (not isinstance(self.large, dict) or self.large.get("dimensoes") != 1024
                    or not isinstance(self.large.get("temas"), dict)
                    or not isinstance(self.large.get("questoes"), dict)
                    or set(self.large["temas"]) != set(self.temas)):
                raise ValueError("Cache large deve conter os mesmos temas, em1024 dimensões.")
            for secao in ("temas", "questoes"):
                for entrada in self.large[secao].values():
                    vetor = entrada.get("vetor") if isinstance(entrada, dict) else None
                    if (not isinstance(vetor, list) or len(vetor) != 1024
                            or any(type(v) not in (int, float) or not math.isfinite(v) for v in vetor)
                            or not math.isclose(math.hypot(*vetor), 1.0, abs_tol=1e-5)):
                        raise ValueError("Vetor large deve ter1024 valores finitos e norma unitária.")
            for i in self.temas:
                if self.large["temas"][i]["texto_sha256"] != hash_texto("tema", self.taxonomia["por_id"][i]):
                    raise ValueError("Tema large diverge do catálogo congelado.")
            self._normas_large = {i: math.sqrt(math.fsum(v*v for v in e["vetor"]))
                                  for i, e in self.large["temas"].items()}

    def atributos(self, q, large=False):
        chave = q["id"], hash_texto("questao", q), large
        if chave in self._consultas:
            return self._consultas[chave]
        originais, rl, rs = self.base.atributos(q)
        xs = {i: list(x) for i, x in originais.items()}
        if large:
            if self.large is None:
                raise ValueError("Receita large exige cache preparado separadamente.")
            e = self.large["questoes"].get(q["id"])
            if e is None or e["texto_sha256"] != chave[1]:
                raise ValueError("Questão large ausente ou texto divergente.")
            vq = e["vetor"]
            nq = math.sqrt(math.fsum(v*v for v in vq))
            sem = {i: min(1.0, max(0.0, math.fsum(a*b for a, b in zip(vq, self.large["temas"][i]["vetor"])) /
                                             (nq*self._normas_large[i]))) for i in self.temas}
            rs = {i: n for n, i in enumerate(sorted(self.temas, key=lambda i: (-sem[i], i)), 1)}
            for i, x in xs.items():
                x[1], x[4] = sem[i], 21/(20+rs[i])
                x[5], x[6] = x[0]*x[1], min(x[3], x[4])
        for i, x in xs.items():
            x.extend(self.sinais.atributos(q, i))
        self._consultas[chave] = xs, rl, rs
        return self._consultas[chave]

    def treinar(self, questoes, rotulos, receitas):
        if not receitas or any(n not in RECEITAS for n in receitas):
            raise ValueError("Grade não registrada.")
        qs = {q["id"]: q for q in questoes}
        rs = {r["id"]: _normalizar_rotulo(r, set(self.temas)) for r in rotulos}
        if not qs or len(qs) != len(questoes) or len(rs) != len(rotulos) or set(qs) != set(rs):
            raise ValueError("Treino exige questões e rótulos únicos correspondentes.")
        resultado = {"treino_ids": sorted(qs),
                     "treino_textos": sorted({hash_texto("questao", q) for q in questoes}),
                     "receitas": list(receitas), "rankers": {}}
        if "baseline_m7" in receitas:
            resultado["baseline"] = self.base.treinar(questoes, rotulos)
        for large, prefixo in ((False, "sinais_small"), (True, "sinais_large")):
            if not any(n.startswith(prefixo) for n in receitas):
                continue
            pares = []
            for i in sorted(qs):
                xs, _, _ = self.atributos(qs[i], large)
                pos = set() if rs[i]["fora_da_taxonomia"] else {rs[i]["tema_central_id"], *rs[i]["extras_ids"]}
                ordem = sorted(self.temas, key=lambda t: (-(xs[t][3]+xs[t][4]), t))
                pares.append([{"atributos": xs[t], "positivo": t in pos} for t in ordem])
            resultado["rankers"][prefixo] = ajustar(pares, 14)
        return resultado

    def predizer(self, q, modelo, receita):
        if receita not in RECEITAS or receita not in modelo["receitas"]:
            raise ValueError("Receita desconhecida ou não ajustada.")
        if q["id"] in modelo["treino_ids"] or hash_texto("questao", q) in modelo["treino_textos"]:
            raise ValueError("Ressubstituição recusada.")
        large = receita == "large_rrf20" or receita.startswith("sinais_large")
        xs, rl, rs = self.atributos(q, large)
        if receita == "baseline_m7":
            p = self.base.predizer(q, modelo["baseline"], "aprendido_hierarquico")
            p["receita"] = receita
        else:
            if receita == "large_rrf20":
                scores = {i: (x[3]+x[4])/2 for i, x in xs.items()}
            else:
                chave = "sinais_large" if large else "sinais_small"
                scores = {i: pontuar(modelo["rankers"][chave], x) for i, x in xs.items()}
            ordem = sorted(scores, key=lambda i: (-scores[i], i))
            escolhido = ordem[0]
            if receita.endswith("_hierarquico"):
                escolhido = ancestral_comum(ordem[:3], self.taxonomia) or escolhido
            p = {"id": q["id"], "receita": receita, "tema_sugerido_id": escolhido,
                 "score": scores[ordem[0]], "margem": scores[ordem[0]]-scores[ordem[1]],
                 "consenso": rl[ordem[0]] == rs[ordem[0]] == 1,
                 "sem_evidencia": max(x[0] for x in xs.values()) == 0 and max(x[1] for x in xs.values()) == 0,
                 "recuou_na_hierarquia": escolhido != ordem[0],
                 "nivel_sugerido": int(self.taxonomia["por_id"][escolhido]["nivel"]),
                 "top_candidatos": [{"tema_id": i, "score": scores[i]} for i in ordem[:5]]}
        escolhido = p["tema_sugerido_id"]
        x = xs[escolhido]
        # Pares:8base+6sinais. Confiança não usa IDs ou metadados da origem.
        evidencia = max(x[8], x[9], x[10], x[12])
        tema = self.taxonomia["por_id"][escolhido]
        acordo = sum(t["tema_id"] == escolhido or escolhido in self.taxonomia["por_id"][t["tema_id"]]["ancestrais_ids"]
                     or t["tema_id"] in tema["ancestrais_ids"] for t in p["top_candidatos"]) / len(p["top_candidatos"])
        lex = sorted((v[0] for v in xs.values()), reverse=True)
        sem = sorted((v[1] for v in xs.values()), reverse=True)
        p["evidencia_especifica"] = evidencia
        p["atributos_confianca"] = [p["score"], p["margem"], x[0], x[1], float(p["consenso"]),
                                    evidencia, acordo, lex[0]-lex[1], sem[0]-sem[1]]
        return p
