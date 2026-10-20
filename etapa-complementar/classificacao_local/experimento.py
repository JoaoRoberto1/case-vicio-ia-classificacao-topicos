"""Experimento reproduzível: desenvolvimento separado da reserva final.

Os rótulos são exclusivamente os fornecidos pela equipe do case. A avaliação
compara IDs e relações da árvore por código, sem julgamento de uma IA.
"""

from __future__ import annotations

from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import tempfile

from classificacao_topicos.avaliacao import tema_aceito
from classificacao_topicos.pipeline import (
    _arquivo_local, _conferir_existentes, _json, _jsonl, _sha, _validar_saida,
    verificar_preparacao,
)
from .classificador import predizer, treinar, validar_config


CRITERIO = [
    "acertos_ramo_decrescente", "acertos_exato_decrescente", "receita_id_crescente",
]
PREPARACAO = Path("artefatos/preparacao")


def _ids(valores: list, nome: str) -> set[str]:
    if (not isinstance(valores, list)
            or any(not isinstance(v, str) or not v for v in valores)
            or len(set(valores)) != len(valores)):
        raise ValueError(f"IDs inválidos ou repetidos: {nome}.")
    return set(valores)


def selecionar_protocolo(particoes: dict, config: dict) -> dict:
    """Fixa uma única reserva e verifica cobertura, disjunção e grupos."""
    indice = config["particao_externa_reservada"]
    folds = [f for f in particoes["folds"] if f["indice"] == indice]
    if len(folds) != 1:
        raise ValueError("A partição externa reservada deve existir uma única vez.")
    fold = folds[0]
    dev = _ids(fold["treino_ids"], "desenvolvimento")
    reserva = _ids(fold["teste_ids"], "reserva")
    avaliacao = _ids(particoes["avaliacao_ids"], "avaliação")
    rotulados = _ids(particoes["rotulados_ids"], "rotulados")
    if dev & reserva or (dev | reserva) != rotulados or rotulados & avaliacao:
        raise ValueError("Desenvolvimento, reserva e avaliação devem ser disjuntos.")
    internas = fold["internas"]
    contagens = {
        "desenvolvimento": len(dev), "reserva": len(reserva),
        "avaliacao": len(avaliacao), "particoes_internas": len(internas),
    }
    if contagens != config["contagens"] or min(contagens.values()) < 1:
        raise ValueError("Contagens incompatíveis com o protocolo fixado.")
    vistos: Counter[str] = Counter()
    indices = set()
    cortes = [(dev, reserva, avaliacao)]
    for interna in internas:
        if interna["indice"] in indices:
            raise ValueError("Índice repetido nas partições internas.")
        indices.add(interna["indice"])
        treino = _ids(interna["treino_ids"], "treino interno")
        validacao = _ids(interna["validacao_ids"], "validação interna")
        if not treino or not validacao or treino & validacao or treino | validacao != dev:
            raise ValueError("Treino e validação devem particionar só o desenvolvimento.")
        vistos.update(validacao)
        cortes.append((treino, validacao, reserva, avaliacao))
    if set(vistos) != dev or any(n != 1 for n in vistos.values()):
        raise ValueError("Cada referência deve ser validada exatamente uma vez.")
    agrupados = set()
    for grupo in particoes["grupos"]:
        membros = _ids(grupo["ids"], "grupo")
        if not membros or agrupados & membros:
            raise ValueError("Grupos vazios ou com membros repetidos.")
        agrupados.update(membros)
        # Grupos sem rótulos podem conter questões da avaliação oficial; grupos
        # mistos são recusados para não medir uma cópia de exemplo de treino.
        if any(sum(bool(membros & bloco) for bloco in corte) > 1 for corte in cortes):
            raise ValueError("Um grupo de questões semelhantes atravessa uma partição.")
    if agrupados != rotulados | avaliacao:
        raise ValueError("Os grupos devem cobrir todas as questões.")
    return {
        "versao": config["versao"],
        "particao_externa_reservada": indice,
        "desenvolvimento_ids": sorted(dev),
        "reserva_ids": sorted(reserva),
        "avaliacao_ids": sorted(avaliacao),
        "particoes_internas": [
            {"indice": f["indice"], "treino_ids": sorted(f["treino_ids"]),
             "validacao_ids": sorted(f["validacao_ids"])}
            for f in sorted(internas, key=lambda f: f["indice"])
        ],
        "contagens": contagens,
        "reserva_inferida_ou_avaliada": False,
        "regra": config["uso_reserva"],
        "natureza_metricas": "Exploratórias de desenvolvimento; não são avaliação final.",
    }


def validar_experimento(config: dict) -> None:
    if config.get("versao") != 1 or config.get("criterio_selecao") != CRITERIO:
        raise ValueError("Versão ou critério de seleção não suportado.")
    if type(config.get("top_k")) is not int or not 1 <= config["top_k"] <= 20:
        raise ValueError("top_k deve ser inteiro entre 1 e 20.")
    receitas = config.get("receitas")
    if not isinstance(receitas, dict) or not receitas:
        raise ValueError("O experimento exige receitas.")
    for nome, parametros in receitas.items():
        if not isinstance(nome, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", nome):
            raise ValueError("Identificador de receita inválido.")
        validar_config(parametros)
    limiares = config.get("limiares_diagnosticos_score")
    if (not isinstance(limiares, list) or not limiares
            or any(isinstance(t, bool) or not isinstance(t, (int, float))
                   or not math.isfinite(t) or not 0 <= t <= 1 for t in limiares)
            or limiares != sorted(set(limiares))):
        raise ValueError("Limiares diagnósticos devem ser únicos, crescentes e entre 0 e 1.")


def resumir(predicoes: list[dict]) -> dict:
    total = len(predicoes)
    acertos = {modo: sum(p["acertos"][modo] for p in predicoes)
               for modo in ("ramo", "imediato", "exato")}
    top_k = sum(p["acerto_top_k_ramo"] for p in predicoes)
    return {
        "total": total, "acertos": acertos,
        "taxas_acerto": {m: n / total if total else None for m, n in acertos.items()},
        "acertos_top_k_ramo": top_k,
        "taxa_top_k_ramo": top_k / total if total else None,
        "sem_evidencia": sum(p["sem_evidencia"] for p in predicoes),
    }


def processar_experimento(
    questoes: list[dict], rotulos: list[dict], taxonomia: dict,
    protocolo: dict, config: dict,
) -> tuple[dict[str, bytes], dict]:
    """Núcleo testável: ajusta só treino interno/80; nunca prediz a reserva."""
    validar_experimento(config)
    qs = {q["id"]: q for q in questoes}
    rs = {r["id"]: r for r in rotulos}
    dev = set(protocolo["desenvolvimento_ids"])
    reserva = set(protocolo["reserva_ids"])
    avaliacao = set(protocolo["avaliacao_ids"])
    if (len(qs) != len(questoes) or len(rs) != len(rotulos)
            or dev & reserva or (dev | reserva) & avaliacao
            or set(qs) != dev | reserva | avaliacao or set(rs) != dev | reserva):
        raise ValueError("Os dados não correspondem aos IDs disjuntos do protocolo.")
    # A reserva é removida da coleção de rótulos antes de qualquer ajuste ou
    # avaliação. Sua existência pública não equivale a cegamento físico.
    rs = {i: rs[i] for i in sorted(dev)}
    qs = {i: q for i, q in qs.items() if i not in reserva}
    predicoes = []
    metricas = {}
    modelos = {}
    for receita, parametros in sorted(config["receitas"].items()):
        resultados = []
        for fold in protocolo["particoes_internas"]:
            treino, validacao = fold["treino_ids"], fold["validacao_ids"]
            if set(treino) & set(validacao) or set(treino) | set(validacao) != dev:
                raise ValueError("Partição interna inválida ou com reserva.")
            modelo = treinar([qs[i] for i in treino], [rs[i] for i in treino],
                             taxonomia, parametros)
            centrais_vistos = {rs[i]["tema_central_id"] for i in treino
                              if not rs[i]["fora_da_taxonomia"]}
            for identificador in validacao:
                p = predizer(modelo, qs[identificador], top_k=config["top_k"])
                r = rs[identificador]
                p.update({
                    "receita": receita, "particao_interna": fold["indice"],
                    "acertos": {modo: tema_aceito(p["tema_sugerido_id"], r, taxonomia, modo)
                                for modo in ("ramo", "imediato", "exato")},
                    "acerto_top_k_ramo": any(
                        tema_aceito(t["tema_id"], r, taxonomia)
                        for t in p["top_candidatos"]),
                    "referencia_fora": r["fora_da_taxonomia"],
                    "disciplina_referencia": r["disciplina"],
                    "central_visto_treino": r["tema_central_id"] in centrais_vistos,
                })
                resultados.append(p)
        if Counter(p["id"] for p in resultados) != Counter({i: 1 for i in dev}):
            raise ValueError("Cobertura inválida das predições fora da amostra.")
        resultados.sort(key=lambda p: p["id"])
        predicoes.extend(resultados)
        metricas[receita] = {
            "geral": resumir(resultados),
            "dentro_taxonomia": resumir([p for p in resultados if not p["referencia_fora"]]),
            "fora_taxonomia": resumir([p for p in resultados if p["referencia_fora"]]),
            "por_disciplina": {
                d: resumir([p for p in resultados if p["disciplina_referencia"] == d])
                for d in sorted({p["disciplina_referencia"] for p in resultados})
            },
            "central_visto_treino": resumir(
                [p for p in resultados if p["central_visto_treino"]]),
            "central_nao_visto_treino_dentro_taxonomia": resumir([
                p for p in resultados
                if not p["central_visto_treino"] and not p["referencia_fora"]]),
            "curva_diagnostica_score": [
                {"limiar": t, "fracao_retida": len(retidos) / len(resultados),
                 **resumir(retidos)}
                for t in config["limiares_diagnosticos_score"]
                for retidos in [[p for p in resultados
                                 if p["score"] >= t and not p["sem_evidencia"]]]
            ],
        }
        modelos[receita] = treinar(
            [qs[i] for i in sorted(dev)], [rs[i] for i in sorted(dev)],
            taxonomia, parametros,
        )
    selecionada = min(metricas, key=lambda nome: (
        -metricas[nome]["geral"]["acertos"]["ramo"],
        -metricas[nome]["geral"]["acertos"]["exato"], nome,
    ))
    # Inferência após serializar/carregar prova o uso do artefato persistido.
    modelo_selecionado = json.loads(_json(modelos[selecionada]))
    sugestoes = [
        {**predizer(modelo_selecionado, qs[i], top_k=config["top_k"]),
         "receita": selecionada, "uso": "sugestao_intermediaria"}
        for i in sorted(avaliacao)
    ]
    relatorio = {
        "versao": 1, "receita_selecionada": selecionada,
        "criterio_selecao": config["criterio_selecao"],
        "natureza": "Exploratória. A seleção usa estas mesmas métricas; não é teste final.",
        "score_e_probabilidade": False,
        "curva_define_publicacao": False,
        "top_k": config["top_k"],
        "reservados_sem_predicao": len(reserva),
        "questoes_avaliacao_sem_rotulo": len(avaliacao),
        "referencias_desenvolvimento": {
            "total": len(dev),
            "fora": sum(r["fora_da_taxonomia"] for r in rs.values()),
            "centrais_distintos": len({r["tema_central_id"] for r in rs.values()
                                      if not r["fora_da_taxonomia"]}),
        },
        "receitas": metricas,
    }
    produtos = {
        "protocolo.json": _json(protocolo),
        "metricas_desenvolvimento.json": _json(relatorio),
        "predicoes_desenvolvimento.jsonl": _jsonl(predicoes),
        "sugestoes_avaliacao.jsonl": _jsonl(sugestoes),
        **{f"modelo_{nome}.json": _json(modelo) for nome, modelo in modelos.items()},
    }
    return produtos, {
        "desenvolvimento": len(dev), "reserva_sem_predicao": len(reserva),
        "predicoes_desenvolvimento": len(predicoes), "sugestoes": len(sugestoes),
        "receita_selecionada": selecionada,
        "acertos_ramo_desenvolvimento": metricas[selecionada]["geral"]["acertos"]["ramo"],
    }


def _assinaturas(raiz: Path) -> dict:
    caminhos = sorted([
        *(raiz / "classificacao_local").glob("*.py"),
        *(raiz / "config/modulo2").glob("*.json"),
        *(raiz / PREPARACAO).iterdir(),
    ])
    return {p.relative_to(raiz).as_posix(): _sha(
        _arquivo_local(raiz, p.relative_to(raiz).as_posix()).read_bytes())
        for p in caminhos}


def construir_produtos(raiz: Path) -> tuple[dict[str, bytes], dict]:
    raiz = raiz.resolve()
    # Confere fontes oficiais, código M1 e todos os produtos preparados antes
    # de consumir dados. Uma simples troca do manifesto não contorna o controle.
    verificar_preparacao(raiz, raiz / PREPARACAO)
    assinaturas = _assinaturas(raiz)
    def ler(nome: str):
        return json.loads(_arquivo_local(raiz, nome).read_text(encoding="utf-8"))
    config_protocolo = ler("config/modulo2/protocolo_desenvolvimento.json")
    config = ler("config/modulo2/experimento_lexical.json")
    for nome, esperado in config_protocolo["preparacao_sha256"].items():
        if nome not in {"particoes.json", "manifesto.json"}:
            raise ValueError("Arquivo de preparação fixado inesperado.")
        if assinaturas[f"{PREPARACAO.as_posix()}/{nome}"] != esperado:
            raise ValueError(f"A preparação mudou em relação ao protocolo: {nome}.")
    if set(config_protocolo["preparacao_sha256"]) != {"particoes.json", "manifesto.json"}:
        raise ValueError("Fixe os hashes das partições e do manifesto da preparação.")
    protocolo = selecionar_protocolo(ler(f"{PREPARACAO.as_posix()}/particoes.json"),
                                    config_protocolo)
    def ler_linhas(nome: str):
        # Iteração por linhas físicas preserva U+0085/U+2028 dentro de strings;
        # str.splitlines() trataria esses caracteres válidos como novos registros.
        with _arquivo_local(raiz, f"{PREPARACAO.as_posix()}/{nome}").open(
            encoding="utf-8",
        ) as arquivo:
            return [json.loads(linha) for linha in arquivo]
    temas = ler(f"{PREPARACAO.as_posix()}/temas_preparados.json")
    produtos, resumo = processar_experimento(
        ler_linhas("questoes_preparadas.jsonl"), ler_linhas("rotulos_referencia.jsonl"),
        {"registros": temas, "por_id": {t["tema_id"]: t for t in temas}},
        protocolo, config,
    )
    origem = ler(f"{PREPARACAO.as_posix()}/manifesto.json")
    produtos["manifesto.json"] = _json({
        "versao": 1, "procedimento": "desenvolvimento-lexical-v1",
        "entradas_e_implementacao_sha256": assinaturas,
        "preparacao_manifesto_sha256": _sha(_json(origem)),
        "upstream_commit": origem["upstream_commit"],
        "fontes_sha256": origem["fontes_sha256"],
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "origem_rotulos": "anexos/folha_verdade.csv",
        "modelo_de_linguagem_utilizado": False,
        "rede_necessaria": False,
        "reserva_inferida_ou_avaliada": False,
        "receita_selecionada": resumo["receita_selecionada"],
    })
    if assinaturas != _assinaturas(raiz):
        raise ValueError("Entradas, código ou configurações mudaram durante o experimento.")
    return produtos, resumo


def publicar_produtos(saida: Path, produtos: dict[str, bytes]) -> None:
    """Publica arquivos novos atomicamente; recusa sobrescrever divergências."""
    _conferir_existentes(saida, produtos, exigir_completo=False)
    saida.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in produtos.items():
        destino = saida / nome
        if destino.exists():
            continue
        temporario = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".produto-", suffix=".tmp", dir=saida, delete=False,
            ) as arquivo:
                temporario = Path(arquivo.name)
                arquivo.write(conteudo)
            if destino.exists():
                if destino.is_symlink() or destino.read_bytes() != conteudo:
                    raise ValueError(f"O destino mudou durante a escrita: {nome}.")
            else:
                os.replace(temporario, destino)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
    _conferir_existentes(saida, produtos, exigir_completo=True)


def executar_experimento(raiz: Path, saida: Path, verificar: bool = False) -> dict:
    saida = _validar_saida(raiz, saida)
    produtos, resumo = construir_produtos(raiz)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
    else:
        publicar_produtos(saida, produtos)
    return resumo
