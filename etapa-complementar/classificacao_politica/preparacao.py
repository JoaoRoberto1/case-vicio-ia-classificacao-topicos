"""Reconstitui treinos internos; nunca recalibra a partir dos alvos externos."""

import hashlib
from pathlib import Path

from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_precisao.experimento import carregar_contexto, _oof, _corte
from classificacao_precisao.motor import Motor
from classificacao_refinamento.experimento import criar_internas, validar_particoes
from classificacao_topicos.pipeline import _json, _jsonl
from .politica import preparar

PROTOCOLO = "config/modulo9/protocolo.json"
PROTOCOLO_SHA = "f686c64cce60d1c100d318946f1d0e23659557cfbb3b6e233d76c0c0596162cf"
CACHE = "artefatos/politica-m9-preparacao-v1"
M8 = "artefatos/precisao-m8-v1"
RECEITAS = ("sinais_small", "large_rrf20", "sinais_large")
PRODUTOS = tuple(f"internas_bloco{i}.json" for i in (1, 2, 3)) + (
    "predicoes_20_concordancia.jsonl", "sugestoes_559_concordancia.jsonl",
)


def sha(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def salvar(pasta, nome, conteudo, verificar=False):
    """Não substitui evidências existentes por uma execução diferente."""
    destino = pasta / nome
    if destino.exists():
        if destino.read_bytes() != conteudo:
            raise ValueError(f"Artefato divergente: {destino}. Use uma nova versão.")
    elif verificar:
        raise ValueError(f"Artefato ausente: {destino}.")
    else:
        pasta.mkdir(parents=True, exist_ok=True)
        temporario = destino.with_name(destino.name + ".tmp")
        temporario.write_bytes(conteudo)
        temporario.replace(destino)


def autenticar_m8(raiz):
    if sha((raiz / PROTOCOLO).read_bytes()) != PROTOCOLO_SHA:
        raise ValueError("Protocolo M9 alterado após registro.")
    manifesto = ler_json(raiz, f"{M8}/manifesto.json")
    conferir_assinaturas(raiz, manifesto["entradas_implementacao_sha256"])
    conferir_assinaturas(raiz, {f"{M8}/{n}": h for n, h in manifesto["produtos_sha256"].items()})
    return manifesto


def carregar_cache(raiz):
    autenticar_m8(raiz)
    manifesto = ler_json(raiz, f"{CACHE}/manifesto.json")
    if set(manifesto["produtos_sha256"]) != set(PRODUTOS):
        raise ValueError("Inventário da preparação M9 incompleto.")
    conferir_assinaturas(raiz, manifesto["fontes_sha256"])
    conferir_assinaturas(raiz, {f"{CACHE}/{n}": h for n, h in manifesto["produtos_sha256"].items()})
    return manifesto


def reconstruir_internas(motor, qs, rs, grupos, fold, config):
    treino, teste = set(fold["treino_ids"]), set(fold["validacao_ids"])
    if treino & teste or not treino or not teste:
        raise ValueError("Divisão externa inválida.")
    internas = criar_internas(sorted(treino), grupos, fold["indice"], config)
    validar_particoes(internas, treino, grupos)
    # _oof recebe SOMENTE os rótulos e questões do treino externo.
    resultados = _oof(motor, {i: qs[i] for i in treino}, {i: rs[i] for i in treino}, internas, list(RECEITAS))
    if any({p["id"] for p in ps} != treino for ps in resultados.values()):
        raise ValueError("OOF internas não cobrem exatamente o treino externo.")
    return {"externa": fold, "internas": internas, "predicoes": resultados}


def ler_parcial(pasta, nome):
    """Retoma apenas um par produto/hash completo; nunca assina dados órfãos."""
    destino, assinatura = pasta / nome, pasta / (nome + ".sha256")
    if destino.exists() != assinatura.exists():
        raise ValueError(f"Checkpoint incompleto: {nome}; produto e hash devem existir juntos.")
    if not destino.exists():
        return None
    conteudo = destino.read_bytes()
    if assinatura.read_bytes() != (sha(conteudo) + "\n").encode():
        raise ValueError(f"Checkpoint alterado: {nome}.")
    return conteudo


def executar_preparacao(raiz: Path, verificar=False, progresso=print, forcar=False):
    """Preparação retomável por bloco; --verificar recompõe sem sobrescrever."""
    raiz = raiz.resolve()
    autenticar_m8(raiz)
    contexto, config, tax, docs, ancoras, cache, large, fontes = carregar_contexto(raiz, False)
    nomes = [PROTOCOLO, "classificacao_politica/preparacao.py", "classificacao_politica/politica.py",
             "classificacao_politica/__init__.py", f"{M8}/manifesto.json"]
    nomes += [f"{M8}/{n}" for n in ler_json(raiz, f"{M8}/manifesto.json")["produtos_sha256"]]
    fontes.update(assinar(raiz, nomes))
    pasta = raiz / CACHE
    if not (pasta / "fontes.json").exists() and pasta.exists() and any(pasta.iterdir()):
        raise ValueError("Parciais sem fontes.json prévio: retomada recusada.")
    salvar(pasta, "fontes.json", _json(fontes), verificar)
    protocolo = contexto["protocolo"]
    dev, reserva, avaliacao = [set(protocolo[c]) for c in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")]
    qs = {q["id"]: q for q in contexto["questoes"]}
    rs = {r["id"]: r for r in ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")}
    if (len(dev), len(reserva), len(avaliacao)) != (80, 20, 559) or set(rs) != dev | reserva:
        raise ValueError("Universos M9 incompatíveis.")
    if dev & reserva or (dev | reserva) & avaliacao or set(qs) != dev | reserva | avaliacao:
        raise ValueError("Universos sobrepostos ou incompletos.")
    grupos = ler_json(raiz, "artefatos/preparacao/particoes.json")["grupos"]
    motor = Motor(tax, contexto["cache"], cache, docs, large, ancoras)
    produtos = {}
    for fold in protocolo["particoes_internas"]:
        nome = f"internas_bloco{fold['indice']}.json"
        anterior = ler_parcial(pasta, nome)
        if anterior is not None and not verificar and not forcar:
            progresso(f"M9: reutilizando preparação do bloco {fold['indice']}.")
            produtos[nome] = anterior
        else:
            progresso(f"M9: reconstruindo treino interno do bloco {fold['indice']}.")
            dados = reconstruir_internas(motor, qs, rs, grupos, fold, config["validacao"]["interna"])
            produtos[nome] = _json(dados)
            salvar(pasta, nome, produtos[nome], verificar)
        # Há hash por checkpoint: retomada não aceita edições silenciosas.
        salvar(pasta, nome + ".sha256", (sha(produtos[nome]) + "\n").encode(), verificar)
    for nome, entrada, treino, teste in (
        (PRODUTOS[3], "predicoes_reserva_conhecida.jsonl", dev, reserva),
        (PRODUTOS[4], "sugestoes_avaliacao.jsonl", dev | reserva, avaliacao),
    ):
        anterior = ler_parcial(pasta, nome)
        if anterior is not None and not verificar and not forcar:
            progresso(f"M9: reutilizando concordância das {len(teste)} questões.")
            produtos[nome] = anterior
        else:
            progresso(f"M9: medindo concordância dos algoritmos nas {len(teste)} questões.")
            resultados, _ = _corte(motor, qs, {i: rs[i] for i in treino}, treino, teste, list(RECEITAS[:2]))
            resultados["sinais_large"] = ler_jsonl(raiz, f"{M8}/{entrada}")
            if {p["id"] for p in resultados["sinais_large"]} != teste:
                raise ValueError("Cache final M8 fora do universo esperado.")
            produtos[nome] = _jsonl(preparar(resultados))
            salvar(pasta, nome, produtos[nome], verificar)
        salvar(pasta, nome + ".sha256", (sha(produtos[nome]) + "\n").encode(), verificar)
    conferir_assinaturas(raiz, fontes)
    manifesto = {"schema": "preparacao_politica_m9_v1", "fontes_sha256": fontes,
                 "produtos_sha256": {n: sha(b) for n, b in produtos.items()},
                 "LLM_na_decisao": False, "encoder": False, "chamadas_API": 0,
                 "rotulos_externos_nos_treinos_internos": False}
    salvar(pasta, "manifesto.json", _json(manifesto), verificar)
    salvar(pasta, ".gitattributes", b"* -text\n", verificar)
    return manifesto
