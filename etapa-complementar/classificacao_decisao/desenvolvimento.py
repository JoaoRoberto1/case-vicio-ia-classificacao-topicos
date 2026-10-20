"""Ajusta e congela a calibração usando somente as predições OOF de desenvolvimento."""

from collections import Counter
import json
import math
from pathlib import Path

from classificacao_experimentos.contexto import (
    assinar, carregar_contexto, conferir_assinaturas, ler_json, ler_jsonl,
)
from classificacao_local.experimento import publicar_produtos
from classificacao_topicos.pipeline import _conferir_existentes, _json, _jsonl, _sha, _validar_saida

from .calibracao import ajustar, metricas, prever
from .politica import decidir, dentro_dominio, dominio, elegibilidade, medir_decisoes, selecionar_politica


CALIBRACAO = "artefatos/calibracao-v1"
CACHE = "artefatos/embeddings-e5-m4-v1"
RESERVA = "artefatos/reserva-v1"
DECISOES = "artefatos/decisoes-v1"


def validar_config(config: dict) -> None:
    if (config.get("versao") != 1 or config.get("alvo") != "acerto_ramo"
            or config.get("receita_classificador") != "hibrido_catalogo"
            or config.get("criterio_calibrador") != ["brier", "logloss", "prioridade", "nome"]
            or config.get("criterio_limiar") != ["maior_quantidade_publicada", "menor_limiar"]
            or config.get("fora_automatico") is not False
            or config.get("extras_previstos") != []
            or config.get("exigir_dominio_calibrador") is not True
            or config.get("intervalo_proporcoes") != {"metodo": "wilson_bilateral", "confianca": 0.95}):
        raise ValueError("Protocolo M4 incompatível.")
    if config.get("reajuste_final") != {
        "classificador": "100_referencias_mesmos_parametros",
        "calibrador": "manter_ajustado_nas_80_predicoes_oof",
        "politica": "manter_congelada",
        "refs_desenvolvimento_csv": "temas_oof_m3_e_probabilidades_crossfit_m4",
        "refs_reserva_csv": "predicoes_do_teste_congelado",
        "avaliacao_csv": "559_predicoes_do_ajuste100",
    }:
        raise ValueError("Procedimento de reajuste não implementado.")
    grade = config.get("calibradores")
    if grade != {
        "constante": {"atributos": [], "prioridade": 0},
        "logistica_score": {"atributos": ["score"], "prioridade": 1},
        "logistica_score_margem": {"atributos": ["score", "margem"], "prioridade": 2},
    }:
        raise ValueError("Grade de calibradores diferente da pré-registrada.")
    if (config.get("regularizacao") != 1.0
            or config.get("limiares_publicacao") != [0.95, 0.975, 0.99]
            or config.get("precisao_minima_desenvolvimento") != 0.95
            or type(config.get("suporte_minimo_publicacao")) is not int
            or config["suporte_minimo_publicacao"] != 10):
        raise ValueError("Parâmetros de seleção diferentes do procedimento implementado.")
    e = config["elegibilidade"]
    if (set(e) != {"status", "nivel_minimo", "sem_descendente_ativo", "expressoes_titulo_generico"}
            or e["status"] != "active" or e["nivel_minimo"] != 1
            or e["sem_descendente_ativo"] is not True
            or not isinstance(e["expressoes_titulo_generico"], list)
            or not e["expressoes_titulo_generico"]
            or any(not isinstance(x, str) or not x.strip() for x in e["expressoes_titulo_generico"])):
        raise ValueError("Elegibilidade inválida.")


def processar_desenvolvimento(
    predicoes: list[dict], protocolo: dict, taxonomia: dict, config: dict,
) -> tuple[dict[str, bytes], dict]:
    validar_config(config)
    dev = set(protocolo["desenvolvimento_ids"])
    reserva, avaliacao = set(protocolo["reserva_ids"]), set(protocolo["avaliacao_ids"])
    if (len(dev) != len(protocolo["desenvolvimento_ids"])
            or len(reserva) != len(protocolo["reserva_ids"])
            or len(avaliacao) != len(protocolo["avaliacao_ids"])
            or not dev or not reserva or not avaliacao
            or dev & reserva or dev & avaliacao or reserva & avaliacao
            or Counter(p["id"] for p in predicoes) != Counter({i: 1 for i in dev})):
        raise ValueError("As predições devem cobrir somente o desenvolvimento, sem duplicação.")
    por_id = {}
    for p in predicoes:
        if (p["receita"] != config["receita_classificador"]
                or any(type(p["acertos"][m]) is not bool for m in ("ramo", "imediato", "exato"))
                or type(p["referencia_fora"]) is not bool
                or type(p["sem_evidencia"]) is not bool
                or any(isinstance(p[a], bool) or not isinstance(p[a], (int, float))
                       or not math.isfinite(p[a]) or not 0 <= p[a] <= 1
                       for a in ("score", "margem"))):
            raise ValueError("Registro de desenvolvimento inválido.")
        por_id[p["id"]] = {**p, "acerto": p["acertos"]["ramo"]}
    cobertura = Counter()
    for fold in protocolo["particoes_internas"]:
        treino, validacao = set(fold["treino_ids"]), set(fold["validacao_ids"])
        if (len(treino) != len(fold["treino_ids"]) or len(validacao) != len(fold["validacao_ids"])
                or not treino or not validacao or treino & validacao or treino | validacao != dev
                or any(por_id[i]["particao_interna"] != fold["indice"] for i in validacao)):
            raise ValueError("Partição de calibração inválida ou divergente da predição OOF.")
        cobertura.update(validacao)
    if cobertura != Counter({i: 1 for i in dev}):
        raise ValueError("Cada questão deve participar uma vez da validação do calibrador.")
    resultados, resumos = {}, {}
    for nome, receita in sorted(config["calibradores"].items(), key=lambda x: x[1]["prioridade"]):
        registros = []
        for fold in protocolo["particoes_internas"]:
            treino = [por_id[i] for i in sorted(fold["treino_ids"])]
            calibrador = ajustar(treino, receita["atributos"], config["regularizacao"])
            faixas = dominio(treino, receita["atributos"])
            for i in sorted(fold["validacao_ids"]):
                p = por_id[i]
                registros.append({
                    **p, "calibrador": nome, "confianca": prever(calibrador, p),
                    "dentro_dominio": dentro_dominio(p, faixas),
                    "procedencia_probabilidade": "crossfit_desenvolvimento",
                })
        registros.sort(key=lambda r: r["id"])
        resultados[nome] = registros
        resumos[nome] = {
            **metricas([p["confianca"] for p in registros], [p["acerto"] for p in registros]),
            "fora_dominio": sum(not p["dentro_dominio"] for p in registros),
            "probabilidade_minima": min(p["confianca"] for p in registros),
            "probabilidade_maxima": max(p["confianca"] for p in registros),
        }
    escolhido = min(resumos, key=lambda n: (
        resumos[n]["brier"], resumos[n]["logloss"], config["calibradores"][n]["prioridade"], n,
    ))
    selecionados = resultados[escolhido]
    motivos = elegibilidade(taxonomia, config["elegibilidade"])
    politica, curvas = selecionar_politica(selecionados, motivos, config)
    politica["calibrador"] = escolhido
    decisoes = [{**p, **decidir(p, politica, motivos)} for p in selecionados]
    todos = [por_id[i] for i in sorted(dev)]
    atributos = config["calibradores"][escolhido]["atributos"]
    calibrador = {
        "schema": "ajuste_calibracao_m4_v1", "nome": escolhido,
        "modelo": ajustar(todos, atributos, config["regularizacao"]),
        "dominio": dominio(todos, atributos),
        "treino_ids": sorted(dev), "alvo": "acerto_ramo",
        "procedencia": "Predições OOF M3; ajuste do calibrador final nas 80 referências.",
    }
    relatorio = {
        "schema": "metricas_desenvolvimento_m4_v1",
        "natureza": "Exploratória: escolha de receita M3 e calibrador/política M4 nas mesmas referências.",
        "calibrador_selecionado": escolhido, "calibradores": resumos,
        "score_bruto_como_probabilidade_diagnostico": metricas(
            [r["score"] for r in todos], [r["acerto"] for r in todos]),
        "politica": politica, "curva_limiares": curvas,
        "decisoes_crossfit": medir_decisoes(decisoes),
        "elegibilidade_catalogo": {
            "total": len(motivos), "elegiveis": sum(not v for v in motivos.values()),
            "bloqueios": dict(sorted(Counter(v for v in motivos.values() if v).items())),
        },
        "reserva_consultada": False, "reajuste_final": config["reajuste_final"],
    }
    produtos = {
        "calibrador.json": _json(calibrador), "politica.json": _json(politica),
        "metricas_desenvolvimento.json": _json(relatorio),
        "predicoes_calibradas.jsonl": _jsonl(
            [p for nome in sorted(resultados) for p in resultados[nome]]),
    }
    resumo = {
        "calibrador": escolhido, "brier_crossfit": resumos[escolhido]["brier"],
        "desenvolvimento": len(dev), "predicoes_calibradas": sum(map(len, resultados.values())),
        "publicacao_habilitada": politica["publicacao_habilitada"], "limiar": politica["limiar"],
        "publicadas_desenvolvimento": relatorio["decisoes_crossfit"]["publicacao"]["n"],
        "reserva_consultada": False,
    }
    return produtos, resumo


def carregar_fontes(raiz: Path) -> tuple[dict, dict]:
    fixadas = ler_json(raiz, "config/modulo4/fontes.json")
    conferir_assinaturas(raiz, fixadas["sha256"])
    contexto = carregar_contexto(raiz)
    m3 = ler_json(raiz, "artefatos/melhorias-v1/manifesto.json")
    conferir_assinaturas(raiz, m3["entradas_e_implementacao_sha256"])
    conferir_assinaturas(raiz, {
        "artefatos/melhorias-v1/" + n: h for n, h in m3["produtos_sha256"].items()
    })
    receita = ler_json(raiz, "artefatos/melhorias-v1/receita_congelada.json")
    if receita["receita"] != "hibrido_catalogo" or not receita["classificador_congelado_para_modulo4"]:
        raise ValueError("A receita M3 não corresponde ao classificador congelado.")
    return contexto, fixadas


def construir_calibracao(raiz: Path) -> tuple[dict[str, bytes], dict]:
    raiz = raiz.resolve()
    contexto, fixadas = carregar_fontes(raiz)
    config = ler_json(raiz, "config/modulo4/protocolo.json")
    nomes = [
        *[p.relative_to(raiz).as_posix() for p in (raiz / "classificacao_decisao").glob("*.py")],
        *[p.relative_to(raiz).as_posix() for p in (raiz / "config/modulo4").glob("*.json")],
        *fixadas["sha256"].keys(),
    ]
    assinaturas = assinar(raiz, sorted(set(nomes)))
    predicoes = [
        p for p in ler_jsonl(raiz, "artefatos/melhorias-v1/predicoes_desenvolvimento.jsonl")
        if p["receita"] == config["receita_classificador"]
    ]
    produtos, resumo = processar_desenvolvimento(
        predicoes, contexto["protocolo"], contexto["taxonomia"], config,
    )
    congelamento = {
        "schema": "congelamento_m4_v1",
        "classificador_congelado": True, "calibrador_congelado": True, "politica_congelada": True,
        "fontes_sha256": {
            **assinaturas, **{f"{CALIBRACAO}/{n}": _sha(b) for n, b in produtos.items()},
        },
        **{c: contexto["protocolo"][c]
           for c in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")},
        "receita_classificador": config["receita_classificador"],
        "calibrador": resumo["calibrador"],
        "reajuste_final": config["reajuste_final"],
        "intervalo_proporcoes": config["intervalo_proporcoes"],
        "incerteza_previsao": config["incerteza_previsao"],
        "reserva_ja_avaliada_ao_congelar": False,
    }
    produtos["congelamento.json"] = _json(congelamento)
    produtos["manifesto.json"] = _json({
        "schema": "manifesto_calibracao_m4_v1",
        "entradas_e_implementacao_sha256": assinaturas,
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "modelo_linguagem_na_decisao": False, "reserva_consultada": False,
    })
    conferir_assinaturas(raiz, assinaturas)
    return produtos, resumo


def executar_calibracao(raiz: Path, verificar: bool = False) -> dict:
    saida = _validar_saida(raiz, raiz / CALIBRACAO)
    produtos, resumo = construir_calibracao(raiz)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
    else:
        publicar_produtos(saida, produtos)
    return resumo


def selo_congelamento(raiz: Path) -> tuple[Path, str]:
    from .cache import validar_congelamento
    manifesto = ler_json(raiz, f"{CALIBRACAO}/manifesto.json")
    if manifesto.get("schema") != "manifesto_calibracao_m4_v1":
        raise ValueError("Manifesto de calibração inválido.")
    conferir_assinaturas(raiz, manifesto["entradas_e_implementacao_sha256"])
    conferir_assinaturas(raiz, {
        f"{CALIBRACAO}/{n}": h for n, h in manifesto["produtos_sha256"].items()
    })
    caminho = raiz / CALIBRACAO / "congelamento.json"
    sha = manifesto["produtos_sha256"]["congelamento.json"]
    validar_congelamento(raiz, caminho, sha)
    return caminho, sha
