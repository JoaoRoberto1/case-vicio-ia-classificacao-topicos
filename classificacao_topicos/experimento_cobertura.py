"""Experimento 5C: propostas congeladas, avaliação cega e adoção de um lote.

Somente operações offline. A seleção da versão usa a avaliação e é desenvolvimento,
não validação independente. A confiança original nunca é recalibrada por concordância.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path

from .analise_piloto import _tentativas
from .auditoria import _csv_decisoes
from .avaliacao import _ancestrais, _carregar_revisoes, _comparar
from .decisoes import _COLUNAS, _saida_existente
from .execucao import _canonico, _hash_bytes, _json, _ler, _validar_cache, _validar_entradas
from .piloto import esquema_resposta
from .politica import aplicar_politica


_EXPERIMENTO = Path("artefatos/experimento-cobertura-v2")
_BASE = Path("artefatos/decisoes-v1")


def _json_bytes(objeto: object) -> bytes:
    return (json.dumps(objeto, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _jsonl(linhas: list[dict]) -> bytes:
    return b"".join(_canonico(linha) + b"\n" for linha in linhas)


def _linhas(conteudo: bytes) -> list[dict]:
    return [_json(linha) for linha in conteudo.decode("utf-8-sig").split("\n") if linha.strip()]


def _relativo(raiz: Path, nome: str) -> Path:
    caminho = Path(nome)
    if caminho.is_absolute() or caminho.drive or ".." in caminho.parts:
        raise ValueError("Fonte deve ser relativa à raiz do projeto.")
    destino = raiz / caminho
    if destino.is_symlink() or not destino.resolve().is_relative_to(raiz.resolve()):
        raise ValueError("Fonte fora da raiz ou link simbólico.")
    return destino


def _conferir(raiz: Path, hashes: dict) -> None:
    for nome, esperado in hashes.items():
        if _hash_bytes(_ler(_relativo(raiz, nome))) != esperado:
            raise ValueError(f"Hash congelado divergente: {nome}.")


def _salvar(saida: Path, produtos: dict[str, bytes]) -> None:
    """Congela uma pasta: repetição idêntica é idempotente, divergência não escreve."""
    saida = saida.absolute()
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in (saida, *saida.parents)):
        raise ValueError("Saída e ancestrais não podem ser links ou junções.")
    if saida.exists() and not saida.is_dir():
        raise ValueError("Saída deve ser uma pasta.")
    if saida.exists() and any(saida.iterdir()):
        existentes = {p.name: _ler(p) for p in saida.iterdir()}
        if existentes != produtos:
            raise ValueError("Saída existente diverge; preserve-a e use uma nova pasta.")
        return
    saida.mkdir(parents=True, exist_ok=True)
    # Não substitui arquivos existentes. Um manifesto só é escrito por último.
    for nome, conteudo in produtos.items():
        with (saida / nome).open("xb") as arquivo:
            arquivo.write(conteudo)


def _contexto(raiz: Path) -> tuple:
    caminho = raiz / _EXPERIMENTO / "preregistro.json"
    conteudo = _ler(caminho)
    registro = _json(conteudo)
    if registro.get("procedimento") != "preregistro-desambiguacao-v1":
        raise ValueError("Pré-registro não suportado.")
    hashes = dict(registro["fontes_sha256"])
    hashes[(_EXPERIMENTO / "preregistro.json").as_posix()] = _hash_bytes(conteudo)
    _conferir(raiz, hashes)
    politica = _json(_ler(raiz / "config/politica_v2.json"))
    base = _json(_ler(raiz / "config/politica_v1.json"))
    if (politica.get("versao") != "politica-v2"
            or politica.get("procedimento") != "desambiguacao-controlada-v1"
            or politica["avaliacao"]["limiar_numerador"] != 95
            or politica["avaliacao"]["limiar_denominador"] != 100
            or politica["avaliacao"]["max_divergencias_explicitas"] != 0):
        raise ValueError("Política não corresponde ao experimento implementado.")
    temas = {t["tema_id"]: t for t in _json(_ler(raiz / "artefatos/preparacao/temas_preparados.json"))}
    questoes = _linhas(_ler(raiz / "artefatos/preparacao/questoes_preparadas.jsonl"))
    ids_questoes = [q["id"] for q in questoes]
    existentes = _saida_existente(raiz / _BASE, ids_questoes, temas)
    if existentes is None or "publicacao.csv" not in existentes:
        raise ValueError("Base v1 deve estar completa e congelada.")
    trilha = _linhas(existentes["trilha_decisoes.jsonl"])
    if [t["id"] for t in trilha] != ids_questoes:
        raise ValueError("Trilha base diverge da preparação.")
    selecionados = [t["id"] for t in trilha if t["decisao"]["decisao"] == "revisar"
                    and t["decisao"]["sinais"] == ["temas_alternativos"]]
    if (selecionados != registro["ids"] or len(selecionados) != politica["selecao"]["quantidade"]
            or selecionados != _json(_ler(raiz / _EXPERIMENTO / "ids_selecionados.json"))):
        raise ValueError("Seleção diverge da regra e do pré-registro.")
    for nome, ids in registro["distribuicao"].items():
        entradas = _linhas(_ler(raiz / _EXPERIMENTO / "entradas_cegas" / (nome + ".jsonl")))
        por_id = {q["id"]: q for q in questoes}
        esperadas = [{k: por_id[i][k] for k in ("id", "enunciado", "comando", "alternativas")} for i in ids]
        if entradas != esperadas:
            raise ValueError("Entradas cegas divergem da preparação.")
    return registro, politica, base, temas, trilha, hashes


def decidir_proposta(original: dict, segunda: dict | None, temas: dict, base: dict) -> dict:
    """Só a remoção sustentada do bloqueio por alternativas pode propor publicação."""
    if (original["decisao"]["decisao"] != "revisar"
            or original["decisao"]["sinais"] != ["temas_alternativos"]):
        raise ValueError("Questão fora do grupo com alternativas como único bloqueio.")
    if segunda is None:
        return {"propor_publicar": False, "bloqueios": ["falha_tecnica_segundo_passe"],
                "politica_segundo_passe": None}
    if segunda.get("id") != original["id"]:
        raise ValueError("Segunda sugestão pertence a outra questão.")
    politica = aplicar_politica(segunda, temas, set(base["ids_ambiguos"]),
                               confianca_minima=base["confianca_minima"],
                               max_extras_publicar=base["max_extras_publicar"])
    bloqueios = list(politica["sinais"])
    if segunda["tema_central_id"] != original["decisao"]["tema_central_id"]:
        bloqueios.append("central_divergente_entre_passes")
    if set(segunda["extras_ids"]) != set(original["decisao"]["extras_ids"]):
        bloqueios.append("extras_divergentes_entre_passes")
    return {"propor_publicar": politica["decisao"] == "publicar" and not bloqueios,
            "bloqueios": bloqueios, "politica_segundo_passe": politica}


def _calcular_propostas(raiz: Path) -> tuple[dict[str, bytes], dict]:
    registro, politica, base, temas, trilha, hashes = _contexto(raiz)
    lote = _relativo(raiz, registro["execucao"]["lote"])
    execucao = _relativo(raiz, registro["execucao"]["recibos"])
    if (execucao / ".execucao.lock").exists():
        raise ValueError("Execução ainda ativa; não congelar propostas.")
    entradas, temas_validados, questoes, hash_preparacao, _ = _validar_entradas(
        lote, raiz / "artefatos/preparacao", procedimento_esperado="lote-v1")
    if temas_validados != temas:
        raise ValueError("Taxonomias divergentes.")
    manifesto_bytes = _ler(lote / "manifesto_lote.json")
    manifesto = _json(manifesto_bytes)
    if (manifesto["prompt_version"] != politica["prompt_version"]
            or manifesto["prompt_sha256"] != hashes[politica["prompt"]]):
        raise ValueError("Segundo passe pertence a outro prompt.")
    hashes[(Path(registro["execucao"]["lote"]) / "manifesto_lote.json").as_posix()] = _hash_bytes(manifesto_bytes)
    entradas = {e["id"]: e for e in entradas}
    esperados = {i + ".json" for i in registro["ids"]}
    if {p.name for p in execucao.iterdir()} != esperados:
        raise ValueError("É necessário um recibo por ID selecionado, sem arquivos extras.")
    por_id = {t["id"]: t for t in trilha}
    schema_hash = _hash_bytes(_canonico(esquema_resposta()))
    propostas, tentativas = [], []
    for identificador in registro["ids"]:
        caminho = execucao / (identificador + ".json")
        digest = _hash_bytes(_ler(caminho))
        recibo = _validar_cache(caminho, entradas[identificador], politica["modelo"], schema_hash,
                               hash_preparacao, temas, questoes[identificador])
        historico = _tentativas(recibo)
        if len(historico) > politica["execucao"]["max_tentativas_por_id"]:
            raise ValueError("Limite de tentativas por questão excedido.")
        tentativas.extend(historico)
        hashes[(Path(registro["execucao"]["recibos"]) / caminho.name).as_posix()] = digest
        segunda = recibo.get("sugestao") if recibo["status"] == "sucesso" else None
        propostas.append({"id": identificador, "decisao_v1": por_id[identificador]["decisao"],
                          "sha256_recibo": digest, "status_recibo": recibo["status"],
                          "sugestao_segundo_passe": segunda,
                          **decidir_proposta(por_id[identificador], segunda, temas, base)})
    if len(tentativas) > politica["execucao"]["max_chamadas"]:
        raise ValueError("Limite total de chamadas excedido.")
    produtos = {"propostas.jsonl": _jsonl(propostas)}
    usos = [t.get("usage_metadata", {}).get("totalTokenCount") for t in tentativas]
    resumo = {"schema_version": 1, "procedimento": "propostas-desambiguacao-v1",
              "ids": registro["ids"], "propostos_ids": [p["id"] for p in propostas if p["propor_publicar"]],
              "tentativas": len(tentativas), "sucessos_tecnicos": sum(p["status_recibo"] == "sucesso" for p in propostas),
              "tokens_totais_conhecidos": sum(n for n in usos if type(n) is int),
              "tentativas_sem_uso": sum(type(n) is not int for n in usos),
              "fontes_sha256": hashes,
              "produtos_sha256": {n: _hash_bytes(b) for n, b in produtos.items()},
              "referencias_consultadas": False}
    produtos["manifesto_propostas.json"] = _json_bytes(resumo)
    _conferir(raiz, hashes)
    if (execucao / ".execucao.lock").exists() or {p.name for p in execucao.iterdir()} != esperados:
        raise ValueError("Recibos mudaram durante o congelamento.")
    return produtos, resumo


def propor(raiz: Path, saida: Path | None = None) -> dict:
    raiz = Path(raiz).resolve()
    produtos, resumo = _calcular_propostas(raiz)
    _salvar(Path(saida) if saida else raiz / _EXPERIMENTO / "propostas", produtos)
    return resumo


def congelar_referencias(raiz: Path) -> dict:
    """Valida e congela referências só depois de existirem propostas congeladas."""
    raiz = Path(raiz).resolve()
    registro, _, _, temas, _, _ = _contexto(raiz)
    pasta = raiz / _EXPERIMENTO
    recalculados, _ = _calcular_propostas(raiz)
    for nome, esperado in recalculados.items():
        if _ler(pasta / "propostas" / nome) != esperado:
            raise ValueError("Propostas não coincidem com a versão congelada.")
    digest_propostas = _hash_bytes(recalculados["manifesto_propostas.json"])
    referencias, hashes = _carregar_revisoes(pasta / "referencias", set(registro["ids"]), temas)
    if any(temas[i]["nivel"] in (0, "0") for ref in referencias.values()
           for i in ref["temas_centrais_aceitaveis"]):
        raise ValueError("Referências do experimento não podem indicar temas de nível zero.")
    for nome, ids in registro["distribuicao"].items():
        arquivo = pasta / "referencias" / (nome + ".jsonl")
        if [r["id"] for r in _linhas(_ler(arquivo))] != ids:
            raise ValueError("Referências fora da distribuição congelada.")
        fonte = pasta / "fontes" / (nome + ".json")
        hashes[fonte] = _hash_bytes(_ler(fonte))
    destino = pasta / "manifesto_referencias.json"
    resumo = {"schema_version": 1, "procedimento": "referencias-desambiguacao-v1",
              "ids": registro["ids"], "manifesto_propostas_sha256": digest_propostas,
              "fontes_sha256": {p.relative_to(raiz).as_posix(): h for p, h in hashes.items()},
              "congeladas_antes_da_comparacao": True}
    if destino.exists():
        anterior = _json(_ler(destino))
        if {k: v for k, v in anterior.items() if k != "registrado_utc"} != resumo:
            raise ValueError("Referências existentes divergem do congelamento.")
        return anterior
    resumo["registrado_utc"] = datetime.now(timezone.utc).isoformat()
    with destino.open("xb") as arquivo:
        arquivo.write(_json_bytes(resumo))
    return resumo


def avaliar_grupo(propostas: list[dict], referencias: dict, temas: dict) -> tuple[dict, list[dict]]:
    """Gate de lote, sem retirar individualmente discordâncias do denominador."""
    ancestrais = _ancestrais(temas)
    comparacoes = []
    for proposta in propostas:
        ref = referencias[proposta["id"]]
        central = proposta["decisao_v1"]["tema_central_id"]
        categoria, detalhe, _ = _comparar(central, ref, temas, ancestrais)
        estrita = (ref["situacao"] == "provisorio" and ref["sem_tema"] is False
                   and ref["temas_centrais_aceitaveis"] == [central])
        comparacoes.append({"id": proposta["id"], "propor_publicar": proposta["propor_publicar"],
                            "tema_central_id": central, "referencia": ref,
                            "comparacao_v1": categoria, "detalhe": detalhe,
                            "coincidencia_estrita": estrita})
    novos = [c for c in comparacoes if c["propor_publicar"]]
    n = len(novos)
    estritos = sum(c["coincidencia_estrita"] for c in novos)
    categorias = Counter(c["comparacao_v1"] for c in novos)
    aprovado = n > 0 and estritos * 100 >= n * 95 and categorias["divergencia"] == 0
    return {"propostas": n, "coincidencias_estritas": estritos,
            "concordancia_estrita": estritos / n if n else None,
            "comparacoes_regra_v1": {k: categorias[k] for k in ("exata", "pai_filho_direto", "divergencia", "inconclusivo")},
            "concordancia_regra_v1": (categorias["exata"] + categorias["pai_filho_direto"]) / n if n else None,
            "nao_confirmados_ids": [c["id"] for c in novos if not c["coincidencia_estrita"]],
            "divergentes_ids": [c["id"] for c in novos if c["comparacao_v1"] == "divergencia"],
            "adotar_lote": aprovado}, comparacoes


def concluir(raiz: Path, saida: Path | None = None) -> dict:
    raiz = Path(raiz).resolve()
    registro, politica, _, temas, trilha, hashes = _contexto(raiz)
    recalculados, resumo_propostas = _calcular_propostas(raiz)
    hashes.update(resumo_propostas["fontes_sha256"])
    pasta = raiz / _EXPERIMENTO
    for nome, esperado in recalculados.items():
        caminho = pasta / "propostas" / nome
        if _ler(caminho) != esperado:
            raise ValueError("Propostas não coincidem com a versão congelada.")
        hashes[caminho.relative_to(raiz).as_posix()] = _hash_bytes(esperado)
    propostas = _linhas(recalculados["propostas.jsonl"])
    mr_bytes = _ler(pasta / "manifesto_referencias.json")
    mr = _json(mr_bytes)
    if (mr.get("procedimento") != "referencias-desambiguacao-v1" or mr.get("ids") != registro["ids"]
            or mr.get("manifesto_propostas_sha256") != _hash_bytes(recalculados["manifesto_propostas.json"])
            or mr.get("congeladas_antes_da_comparacao") is not True):
        raise ValueError("Referências não estão vinculadas às propostas congeladas.")
    _conferir(raiz, mr["fontes_sha256"])
    referencias, hashes_refs = _carregar_revisoes(pasta / "referencias", set(registro["ids"]), temas)
    esperadas_refs = {p.relative_to(raiz).as_posix(): h for p, h in hashes_refs.items()}
    if any(mr["fontes_sha256"].get(p) != h for p, h in esperadas_refs.items()):
        raise ValueError("Conjunto de referências diverge do manifesto.")
    hashes.update(mr["fontes_sha256"])
    hashes[(_EXPERIMENTO / "manifesto_referencias.json").as_posix()] = _hash_bytes(mr_bytes)
    avaliacao, comparacoes = avaliar_grupo(propostas, referencias, temas)
    promovidos = {p["id"] for p in propostas if p["propor_publicar"]} if avaliacao["adotar_lote"] else set()
    achado = politica["achado_conhecido"]
    alteracoes, final = [], []
    for item in trilha:
        novo = deepcopy(item)
        antes = deepcopy(item["decisao"])
        depois = novo["decisao"]
        motivo = None
        if item["id"] == achado["id"]:
            if antes["decisao"] != "publicar" or antes["tema_central_id"] != "5554":
                raise ValueError("Achado conhecido não corresponde à base registrada.")
            motivo = "achado_conhecido_auditoria_v1"
            depois.update(decisao="revisar", sinais=[motivo], motivo=achado["motivo"])
        elif item["id"] in promovidos:
            motivo = "desambiguacao_em_segundo_passe"
            depois.update(decisao="publicar", sinais=[],
                          motivo="Central e extras confirmados no segundo passe; lote aprovado no experimento 5C com referencia provisoria de IA.")
        novo["intervencao_v2"] = motivo
        if motivo:
            alteracoes.append({"id": item["id"], "antes": antes, "depois": deepcopy(depois),
                               "motivo_intervencao": motivo, "responsavel": "Codex - coordenador do experimento 5C",
                               "data_preregistro_utc": registro["registrado_utc"]})
        final.append(novo)
    if not any(a["id"] == achado["id"] for a in alteracoes):
        raise ValueError("Achado conhecido ausente da trilha.")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_COLUNAS, lineterminator="\n")
    writer.writeheader()
    for item in final:
        decisao = item["decisao"]
        writer.writerow({"id": item["id"], **{k: decisao[k] for k in _COLUNAS if k not in {"id", "extras_ids"}},
                         "extras_ids": ";".join(decisao["extras_ids"])})
    csv_bytes = buffer.getvalue().encode("utf-8")
    _csv_decisoes(csv_bytes, [t["id"] for t in trilha], temas)
    contagens = Counter(t["decisao"]["decisao"] for t in final)
    avaliacao.update({"schema_version": 1, "procedimento": "avaliacao-desambiguacao-v1",
                      "grupo_avaliado": len(propostas), "novos_publicados_ids": sorted(promovidos),
                      "decisoes_finais": dict(contagens), "cobertura_final": contagens["publicar"] / len(final),
                      "cobertura_base": sum(t["decisao"]["decisao"] == "publicar" for t in trilha) / len(final),
                      "ganho_liquido_questoes": len(promovidos) - 1,
                      "achado_conhecido_separado": achado,
                      "limites": ["Referencia de IA sem especialista; nao comprova precisao juridica.",
                                  "Gate usa avaliacao para escolher a versao: desenvolvimento, nao validacao independente da versao escolhida.",
                                  "Metricas do grupo proposto preservam o denominador anterior a adocao.",
                                  "Q0180 e achado conhecido; retirada nao representa novo acerto validado."]})
    produtos = {"publicacao.csv": csv_bytes, "trilha_decisoes.jsonl": _jsonl(final),
                "alteracoes.jsonl": _jsonl(alteracoes), "comparacao_experimento.jsonl": _jsonl(comparacoes),
                "relatorio_experimento.json": _json_bytes(avaliacao)}
    manifesto = {"schema_version": 1, "procedimento": "decisoes-v2", "politica_versao": "politica-v2",
                 "completo": True, "total_questoes": len(final), "decisoes": dict(contagens),
                 "base_preservada": _BASE.as_posix(), "fontes_sha256": hashes,
                 "produtos_sha256": {n: _hash_bytes(b) for n, b in produtos.items()},
                 "origem_confianca": "Preservada da v1, sem recalibracao; concordancia nao e probabilidade.",
                 "modo": "segundo_passe_e_selecao_de_lote_por_referencia_IA; Q0180 retida por achado conhecido"}
    produtos["manifesto_decisoes.json"] = _json_bytes(manifesto)
    _conferir(raiz, hashes)
    _salvar(Path(saida) if saida else raiz / "artefatos/decisoes-v2", produtos)
    return avaliacao


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etapa", choices=("propor", "congelar-referencias", "concluir"))
    parser.add_argument("--raiz", type=Path, default=Path("."))
    parser.add_argument("--saida", type=Path, help="Nova pasta para reproduzir propostas ou conclusao.")
    args = parser.parse_args()
    if args.etapa == "congelar-referencias":
        if args.saida is not None:
            parser.error("congelar-referencias usa o destino registrado")
        resultado = congelar_referencias(args.raiz)
    else:
        resultado = {"propor": propor, "concluir": concluir}[args.etapa](args.raiz, args.saida)
    print(json.dumps({k: v for k, v in resultado.items() if k not in {"fontes_sha256", "produtos_sha256"}}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
