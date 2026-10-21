"""Reproduz agregados do relatório sem executar ou alterar o classificador.

Somente biblioteca padrão e extrator textual M1 (também stdlib). Não imprime
IDs, textos, rótulos ou previsões individuais. Não acessa rede ou modelos.
Uso: python -B scripts/diagnosticar_entrega.py [--verificar]
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
SAIDA = BASE / "artefatos/entrega-m5-v1/diagnostico.json"
sys.path.insert(0, str(BASE))
from classificacao_topicos.texto import analisar_texto


def exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValueError(mensagem)


def gerar() -> bytes:
    fontes: dict[str, str] = {}

    def ler(caminho: str):
        conteudo = (BASE / caminho).read_bytes()
        fontes[caminho] = hashlib.sha256(conteudo).hexdigest()
        texto = conteudo.decode("utf-8-sig")
        if caminho.endswith(".jsonl"):
            return [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
        return json.loads(texto)

    temas = ler("artefatos/preparacao/temas_preparados.json")
    taxonomia = {t["tema_id"]: t for t in temas}
    referencias = ler("artefatos/preparacao/rotulos_referencia.jsonl")
    rotulos = {r["id"]: r for r in referencias}
    receita = ler("artefatos/melhorias-v1/receita_congelada.json")
    desenvolvimento = [
        p for p in ler("artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl")
        if p["receita"] == receita["receita"]
    ]
    reserva = ler("artefatos/reserva-v1/predicoes_reserva.jsonl")
    diagnostico = ler("artefatos/preparacao/diagnostico.json")
    originais = ler("anexos/questoes.jsonl")
    checkpoint3 = ler("artefatos/checkpoints/modulo3.json")
    checkpoint4 = ler("artefatos/checkpoints/modulo4.json")

    exigir(len(taxonomia) == len(temas), "IDs de temas duplicados.")
    exigir(len(rotulos) == len(referencias) == 100, "Referências distintas diferentes de 100.")
    for conjunto, esperados in ((desenvolvimento, receita["treino_ids"]),
                               (reserva, receita["reserva_ids"])):
        ids = [r["id"] for r in conjunto]
        exigir(len(ids) == len(set(ids)) and set(ids) == set(esperados),
               "Predições não coincidem com a partição congelada.")
    exigir(set(receita["treino_ids"]).isdisjoint(receita["reserva_ids"]),
           "Desenvolvimento e reserva se sobrepõem.")

    def resumir(registros):
        return {"n": len(registros),
                "acertos_ramo": sum(r["acertos"]["ramo"] for r in registros),
                "acertos_exato": sum(r["acertos"]["exato"] for r in registros),
                "acertos_top5": sum(r["acerto_top_k_ramo"] for r in registros)}

    aceitas = {"exato_central_ou_extra", "ancestral_de_referencia_aceito",
               "descendente_de_referencia_aceito"}

    def relacionar(registros):
        categorias = Counter()
        for p in registros:
            referencia = rotulos[p["id"]]
            sugerido = p["tema_sugerido_id"]
            exigir(sugerido in taxonomia and taxonomia[sugerido]["status"] == "active",
                   "Sugestão ausente ou inativa.")
            if referencia["fora_da_taxonomia"]:
                categoria = "referencia_fora"
            else:
                alvos = [referencia["tema_central_id"], *referencia["extras_ids"]]
                exigir(all(r in taxonomia and taxonomia[r]["status"] == "active"
                           for r in alvos), "Referência ausente ou inativa.")
                if sugerido in alvos:
                    categoria = "exato_central_ou_extra"
                elif any(sugerido in taxonomia[r]["ancestrais_ids"] for r in alvos):
                    categoria = "ancestral_de_referencia_aceito"
                elif any(r in taxonomia[sugerido]["ancestrais_ids"] for r in alvos):
                    categoria = "descendente_de_referencia_aceito"
                elif any(taxonomia[sugerido]["parent_id"] == taxonomia[r]["parent_id"]
                         and taxonomia[sugerido]["parent_id"] for r in alvos):
                    categoria = "irmao_de_referencia_erro"
                elif any(taxonomia[sugerido]["disciplina"] == taxonomia[r]["disciplina"]
                         for r in alvos):
                    categoria = "outro_ramo_mesma_disciplina_erro"
                else:
                    categoria = "outra_disciplina_erro"
            exigir(p["acertos"]["ramo"] == (categoria in aceitas),
                   "Relação estrutural diverge do acerto congelado.")
            exigir(p["acertos"]["exato"] == (categoria == "exato_central_ou_extra"),
                   "Relação exata diverge do acerto congelado.")
            categorias[categoria] += 1
        exigir(sum(categorias.values()) == len(registros), "Categorias não reconciliam.")
        return {
            "geral": resumir(registros),
            "relacoes_com_central_ou_extras": dict(sorted(categorias.items())),
            "central_visto_no_treino_dentro_taxonomia": resumir([
                r for r in registros if r["central_visto_treino"] and not r["referencia_fora"]]),
            "central_nao_visto_no_treino_dentro_taxonomia": resumir([
                r for r in registros if not r["central_visto_treino"] and not r["referencia_fora"]]),
            "fora": resumir([r for r in registros if r["referencia_fora"]]),
        }

    dev, teste = relacionar(desenvolvimento), relacionar(reserva)
    exigir(dev["geral"] == {"n": 80, "acertos_ramo": 37, "acertos_exato": 24,
                              "acertos_top5": 54}, "Desenvolvimento não reconcilia 37/80.")
    exigir(teste["geral"] == {"n": 20, "acertos_ramo": 6, "acertos_exato": 3,
                                "acertos_top5": 12}, "Reserva não reconcilia 6/20.")
    html = Counter()
    for q in originais:
        enunciado = analisar_texto(q["enunciado_html"])["tinha_html"]
        comando = analisar_texto(q["comando"])["tinha_html"]
        alternativas = any(analisar_texto(v)["tinha_html"] for v in q["alternativas"].values())
        html["questoes_com_html_em_qualquer_campo"] += enunciado or comando or alternativas
        html["enunciado_com_html"] += enunciado
        html["comando_com_html"] += comando
        html["questoes_com_html_em_alternativas"] += alternativas

    dados = diagnostico["dados"]
    prep3 = checkpoint3["cli"]["preparacao"]["segundos"]
    registros3 = checkpoint3["preparacao"]["diagnostico"]["registros_total"]
    prep4 = checkpoint4["cli"]["preparacao_reserva"]["segundos"]
    registros4 = checkpoint4["contagens"]["novos_vetores_questoes"]
    geracao = checkpoint4["cli"]["regeneracao"]["segundos"]
    avaliacao = checkpoint4["contagens"]["questoes_avaliacao_oficial"]
    for caminho in ("classificacao_topicos/__init__.py", "classificacao_topicos/texto.py"):
        fontes[caminho] = hashlib.sha256((BASE / caminho).read_bytes()).hexdigest()

    resultado = {
        "schema": "diagnostico_entrega_m5_v1",
        "gerador": "scripts/diagnosticar_entrega.py",
        "gerador_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fontes_sha256": dict(sorted(fontes.items())),
        "metodo": "Agregação estrutural das predições congeladas; sem inferência, julgamento semântico ou modificação de classificações.",
        "prioridade_relacoes": ["exato", "ancestral", "descendente", "irmao", "mesma_disciplina", "outra_disciplina"],
        "taxonomia": {
            "total": len(temas), "ativos": sum(t["status"] == "active" for t in temas),
            "inativos": sum(t["status"] == "inactive" for t in temas),
            "descricoes": {k: v["total"] for k, v in dados["taxonomia"]["descricoes"].items()},
            "grupos_titulos_repetidos": len(dados["taxonomia"]["titulos_repetidos"]),
        },
        "questoes": {**dict(html), "n": len(originais),
                     "comando_vazio_preparado": dados["questoes"]["comando_vazio_preparado"],
                     "enunciado_curto_aviso": dados["questoes"]["avisos"]["enunciado:curto_conferir_comando_e_alternativas"]},
        "suporte": {"rotulos": len(rotulos),
                    "centrais_distintos": len({r["tema_central_id"] for r in referencias if not r["fora_da_taxonomia"]}),
                    "referencias_com_extras": sum(bool(r["extras_ids"]) for r in referencias),
                    "referencias_fora": sum(r["fora_da_taxonomia"] for r in referencias),
                    "rotulos_recentes": diagnostico["contagens"]["rotulos_recentes"]},
        "desenvolvimento": dev, "reserva": teste,
        "contas_50_mil": {
            "quantidade_cenario": 50000,
            "preparacao_m3": {"segundos_observados": prep3, "registros_observados": registros3,
                               "projecao_horas": 50000 * prep3 / registros3 / 3600},
            "preparacao_m4": {"segundos_observados": prep4, "registros_observados": registros4,
                               "projecao_horas": 50000 * prep4 / registros4 / 3600},
            "geracao_m4": {"segundos_observados": geracao, "questoes_oficiais_observadas": avaliacao,
                            "projecao_horas": 50000 * geracao / avaliacao / 3600},
            "revisao": {"minutos_por_questao_assumidos": 2, "reais_por_hora_assumidos": 50,
                        "horas": 50000 * 2 / 60, "custo_reais_cenario": 50000 * 2 / 60 * 50},
            "premissas": [
                "Extrapolações aritméticas por fase a partir de execuções únicas; não são benchmark, garantia nem intervalo estatístico.",
                "M3 mistura questões e temas. M4 prepara só vinte questões e incorpora carga fixa do codificador; tokens e janelas variam.",
                "Regenerar inclui verificações, ajuste final, inferência e gravação; não mede isoladamente latência de inferência.",
                "Cache pronto dispensa preparação. CPU e energia não foram precificados. Zero chamadas API não implica custo total zero.",
                "Revisão humana usa premissas de cenário, sem duração real medida ou tarifa cotada.",
            ],
        },
        "limites": [
            "Categorias estruturais de erro não demonstram causas jurídicas ou textuais.",
            "Desenvolvimento orientou escolha entre receitas; não é avaliação independente após seleção.",
            "Reserva pequena e utilizada uma vez após congelamento; análises posteriores não autorizam ajustar e reutilizar esse teste como independente.",
            "Não há rótulos das questões recentes; reajuste final com cem referências não recebeu avaliação independente.",
            "Todos os temas estavam no catálogo; central não visto no treino não significa ausência completa de informação sobre o tema.",
            "HTML e campos vazios são sinais estruturais, não comprovação de questão inutilizável.",
        ],
    }
    for caminho, esperado in fontes.items():
        exigir(hashlib.sha256((BASE / caminho).read_bytes()).hexdigest() == esperado,
               "Fonte alterada durante a agregação.")
    return (json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true", help="Confere bytes sem gravar ou sobrescrever.")
    args = parser.parse_args()
    try:
        conteudo = gerar()
        if SAIDA.exists():
            exigir(SAIDA.read_bytes() == conteudo, "Diagnóstico divergente; arquivo não foi sobrescrito.")
        elif args.verificar:
            raise ValueError("Diagnóstico ausente; execute primeiro sem --verificar.")
        else:
            SAIDA.parent.mkdir(parents=True, exist_ok=True)
            with SAIDA.open("xb") as destino:
                destino.write(conteudo)
        print(json.dumps({"status": "ok", "operacao": "verificar" if args.verificar else "gerar",
                          "artefato": SAIDA.relative_to(BASE).as_posix(),
                          "sha256": hashlib.sha256(conteudo).hexdigest()}, ensure_ascii=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
