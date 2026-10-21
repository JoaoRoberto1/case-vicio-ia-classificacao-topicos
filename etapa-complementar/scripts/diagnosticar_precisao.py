"""Agrega relações da árvore e erros M8; não julga textos ou temas com IA."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def gerar(raiz):
    from classificacao_experimentos.contexto import ler_json, ler_jsonl, assinar, conferir_assinaturas
    from classificacao_topicos.pipeline import _json
    pasta = "artefatos/precisao-m8-v1"
    manifesto = ler_json(raiz, f"{pasta}/manifesto.json")
    conferir_assinaturas(raiz, manifesto["entradas_implementacao_sha256"])
    conferir_assinaturas(raiz, {f"{pasta}/{n}": h for n, h in manifesto["produtos_sha256"].items()})
    tax = {t["tema_id"]: t for t in ler_json(raiz, "artefatos/preparacao/temas_preparados.json")}
    rs = {r["id"]: r for r in ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")}
    politica = ler_json(raiz, f"{pasta}/politica.json")
    fontes = [f"{pasta}/{n}" for n in ("manifesto.json", "politica.json", "predicoes_desenvolvimento.jsonl",
                                       "predicoes_aninhadas.jsonl", "predicoes_reserva_conhecida.jsonl")]
    fontes += ["artefatos/preparacao/temas_preparados.json", "artefatos/preparacao/rotulos_referencia.jsonl",
               "scripts/diagnosticar_precisao.py"]
    resultados = {}
    for origem, arquivo in (("receita_escolhida80", "predicoes_desenvolvimento.jsonl"),
                            ("selecao_aninhada80", "predicoes_aninhadas.jsonl"),
                            ("reserva_conhecida20", "predicoes_reserva_conhecida.jsonl")):
        ps = ler_jsonl(raiz, f"{pasta}/{arquivo}")
        if origem == "receita_escolhida80":
            ps = [p for p in ps if p["receita"] == politica["receita"]]
        contagens = Counter()
        for p in ps:
            r, sugerido = rs[p["id"]], p["tema_sugerido_id"]
            alvos = [r["tema_central_id"], *r["extras_ids"]] if not r["fora_da_taxonomia"] else []
            if not alvos:
                categoria = "referencia_fora"
            elif sugerido in alvos:
                categoria = "exato"
            elif any(sugerido in tax[t]["ancestrais_ids"] for t in alvos):
                categoria = "ancestral"
            elif any(t in tax[sugerido]["ancestrais_ids"] for t in alvos):
                categoria = "descendente"
            elif any(tax[sugerido]["parent_id"] and tax[sugerido]["parent_id"] == tax[t]["parent_id"] for t in alvos):
                categoria = "irmao_erro"
            elif any(tax[sugerido]["disciplina"] == tax[t]["disciplina"] for t in alvos):
                categoria = "outro_ramo_mesma_disciplina_erro"
            else:
                categoria = "outra_disciplina_erro"
            if p["acertos"]["ramo"] != (categoria in {"exato", "ancestral", "descendente"}):
                raise ValueError("Diagnóstico estrutural diverge da avaliação numérica.")
            contagens[categoria] += 1
        resultados[origem] = {"n": len(ps), "relacoes": dict(sorted(contagens.items())),
            "erros_ordenacao_com_aceito_top5": sum(not p["acertos"]["ramo"] and p["acerto_top_k_ramo"] for p in ps),
            "sem_aceito_top5_incluindo_fora": sum(not p["acerto_top_k_ramo"] for p in ps),
            "central_visto_treino": {"n": sum(p["central_visto_treino"] and not p["referencia_fora"] for p in ps),
                                     "k": sum(p["central_visto_treino"] and p["acertos"]["ramo"] for p in ps)}}
    return _json({"schema": "diagnostico_precisao_m8_v1", "fontes_sha256": assinar(raiz, fontes),
                  "resultados": resultados,
                  "limite": "Agregação estrutural; não demonstra causas jurídicas nem constitui adjudicação por LLM."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args()
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(False)
    conteudo = gerar(RAIZ)
    destino = RAIZ / "artefatos/entrega-m8-v1/diagnostico.json"
    if destino.exists():
        if destino.read_bytes() != conteudo:
            raise ValueError("Diagnóstico divergente; não sobrescrever.")
    elif args.verificar:
        raise ValueError("Diagnóstico ausente.")
    else:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
    print(json.dumps({"sha256": hashlib.sha256(conteudo).hexdigest(), "status": "ok"}))


if __name__ == "__main__":
    main()
