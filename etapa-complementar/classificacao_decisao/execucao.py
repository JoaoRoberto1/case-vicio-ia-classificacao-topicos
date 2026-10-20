"""Avaliação congelada e regeneração da entrega; somente biblioteca padrão."""

from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from classificacao_experimentos.contexto import assinar, conferir_assinaturas, ler_json, ler_jsonl
from classificacao_experimentos.entradas import carregar_cache
from classificacao_experimentos.experimento import avaliar_predicao
from classificacao_experimentos.motor import predizer, treinar
from classificacao_local.experimento import publicar_produtos
from classificacao_topicos.pipeline import _conferir_existentes, _json, _jsonl, _sha, _validar_saida

from .cache import carregar_cache_completo, vincular_modelo_estendido
from .calibracao import prever, validar_modelo
from .desenvolvimento import (
    CACHE, CALIBRACAO, DECISOES, RESERVA, carregar_fontes, executar_calibracao, selo_congelamento,
)
from .entrega import gerar_csv, gerar_previsao, validar_csv
from .politica import decidir, dentro_dominio, elegibilidade, medir_decisoes


def _carregar(raiz: Path) -> dict:
    caminho, sha = selo_congelamento(raiz)
    cache, manifesto_cache = carregar_cache_completo(raiz, raiz / CACHE, caminho, sha)
    contexto, _ = carregar_fontes(raiz)
    calibrador = ler_json(raiz, f"{CALIBRACAO}/calibrador.json")
    politica = ler_json(raiz, f"{CALIBRACAO}/politica.json")
    config = ler_json(raiz, "config/modulo4/protocolo.json")
    validar_modelo(calibrador["modelo"])
    if (calibrador["schema"] != "ajuste_calibracao_m4_v1"
            or calibrador["alvo"] != "acerto_ramo"
            or politica["calibrador"] != calibrador["nome"]
            or set(calibrador["treino_ids"]) != set(contexto["protocolo"]["desenvolvimento_ids"])):
        raise ValueError("Calibrador não corresponde ao procedimento congelado.")
    fontes = assinar(raiz, [
        f"{CALIBRACAO}/manifesto.json", f"{CALIBRACAO}/congelamento.json",
        f"{CACHE}/manifesto.json", f"{CACHE}/vetores.json",
    ])
    return {
        **contexto, "cache": cache, "manifesto_cache": manifesto_cache,
        "calibrador": calibrador, "politica": politica, "config_m4": config,
        "congelamento_sha256": sha, "fontes": fontes,
        "motivos": elegibilidade(contexto["taxonomia"], politica["elegibilidade"]),
    }


def _calibrar(p: dict, contexto: dict, origem: str) -> dict:
    c = contexto["calibrador"]
    return {
        **p, "confianca": prever(c["modelo"], p),
        "dentro_dominio": dentro_dominio(p, c["dominio"]),
        "procedencia_probabilidade": origem,
    }


def _manifesto(contexto: dict, produtos: dict[str, bytes], etapa: str) -> bytes:
    return _json({
        "schema": f"manifesto_{etapa}_m4_v1",
        "congelamento_sha256": contexto["congelamento_sha256"],
        "entradas_sha256": contexto["fontes"],
        "produtos_sha256": {n: _sha(b) for n, b in produtos.items()},
        "modelo_linguagem_na_decisao": False, "chamadas_api": 0,
    })


def conferir_produtos(raiz: Path, diretorio: str, etapa: str, nomes: set[str]) -> dict:
    manifesto = ler_json(raiz, f"{diretorio}/manifesto.json")
    if (manifesto.get("schema") != f"manifesto_{etapa}_m4_v1"
            or set(manifesto["produtos_sha256"]) != nomes
            or {p.name for p in (raiz / diretorio).iterdir()} != nomes | {"manifesto.json"}):
        raise ValueError("Pacote existente incompleto ou incompatível.")
    _, sha = selo_congelamento(raiz)
    if manifesto["congelamento_sha256"] != sha:
        raise ValueError("Pacote gerado com outro congelamento.")
    conferir_assinaturas(raiz, manifesto["entradas_sha256"])
    conferir_assinaturas(raiz, {
        f"{diretorio}/{n}": h for n, h in manifesto["produtos_sha256"].items()
    })
    return manifesto


def construir_reserva(raiz: Path) -> tuple[dict[str, bytes], dict]:
    contexto = _carregar(raiz)
    qs = {q["id"]: q for q in contexto["questoes"]}
    protocolo = contexto["protocolo"]
    config_embeddings = ler_json(raiz, "config/modulo3/embeddings.json")
    cache_m3, _ = carregar_cache(
        raiz / "artefatos/embeddings-e5-v1", contexto["registros"], config_embeddings,
    )
    modelo = vincular_modelo_estendido(
        ler_json(raiz, "artefatos/melhorias-v1/modelo_selecionado.json"),
        cache_m3, contexto["cache"],
    )
    # Todos os temas e probabilidades são calculados antes de ler os rótulos
    # destinados à avaliação. A verificação estrutural M1 não fornece rótulos ao motor.
    preditas = [
        _calibrar(predizer(modelo, qs[i], contexto["cache"], top_k=5),
                  contexto, "calibrador80_teste_reservado")
        for i in sorted(protocolo["reserva_ids"])
    ]
    rotulos = {r["id"]: r for r in ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")}
    vistos = {r["tema_central_id"] for i, r in rotulos.items()
              if i in set(protocolo["desenvolvimento_ids"]) and not r["fora_da_taxonomia"]}
    resultados = []
    for p in preditas:
        avaliada = avaliar_predicao(p, rotulos[p["id"]], contexto["taxonomia"], vistos)
        resultados.append({
            **avaliada, "acerto": avaliada["acertos"]["ramo"],
            **decidir(p, contexto["politica"], contexto["motivos"]),
            "procedencia": "reserva20_modelo80_calibrador80",
        })
    relatorio = {
        "schema": "avaliacao_reserva_m4_v1",
        "natureza": "Teste reservado da receita completa congelada; nenhuma seleção usa este resultado.",
        "geral": medir_decisoes(resultados),
        "por_disciplina": {
            d: medir_decisoes([r for r in resultados if r["disciplina_referencia"] == d])
            for d in sorted({r["disciplina_referencia"] for r in resultados})
        },
        "politica_congelada": contexto["politica"],
        "receita_alterada_apos_teste": False,
        "curva_diagnostica_sem_selecao": [],
        "classificador_reajustado_100_avaliado": False,
    }
    for limiar in contexto["config_m4"]["limiares_publicacao"]:
        politica_diagnostica = {
            **contexto["politica"], "publicacao_habilitada": True, "limiar": limiar,
        }
        rs = [{**r, **decidir(r, politica_diagnostica, contexto["motivos"])} for r in resultados]
        relatorio["curva_diagnostica_sem_selecao"].append({
            "limiar": limiar, **medir_decisoes(rs)["publicacao"],
        })
    produtos = {
        "predicoes_reserva.jsonl": _jsonl(resultados),
        "metricas_reserva.json": _json(relatorio),
    }
    produtos["manifesto.json"] = _manifesto(contexto, produtos, "reserva")
    conferir_assinaturas(raiz, contexto["fontes"])
    selo_congelamento(raiz)
    return produtos, {
        "reserva": len(resultados), "acertos_ramo": relatorio["geral"]["classificacao"]["acertos"]["ramo"],
        "publicacao": relatorio["geral"]["publicacao"],
        "brier": relatorio["geral"]["calibracao"]["brier"],
    }


def executar_reserva(raiz: Path, verificar: bool = False) -> dict:
    saida = _validar_saida(raiz, raiz / RESERVA)
    if not verificar and saida.exists() and any(saida.iterdir()):
        conferir_produtos(raiz, RESERVA, "reserva", {"predicoes_reserva.jsonl", "metricas_reserva.json"})
        return {"reutilizado": True, "reserva": ler_json(raiz, f"{RESERVA}/metricas_reserva.json")["geral"]["total"]}
    produtos, resumo = construir_reserva(raiz)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
    else:
        publicar_produtos(saida, produtos)
    return resumo


def construir_entrega(raiz: Path) -> tuple[dict[str, bytes], dict]:
    conferir_produtos(raiz, RESERVA, "reserva", {"predicoes_reserva.jsonl", "metricas_reserva.json"})
    contexto = _carregar(raiz)
    contexto["fontes"].update(assinar(raiz, [
        f"{RESERVA}/manifesto.json", f"{RESERVA}/metricas_reserva.json",
        f"{RESERVA}/predicoes_reserva.jsonl",
    ]))
    protocolo = contexto["protocolo"]
    qs = {q["id"]: q for q in contexto["questoes"]}
    referencias = set(protocolo["desenvolvimento_ids"]) | set(protocolo["reserva_ids"])
    rotulos = {r["id"]: r for r in ler_jsonl(raiz, "artefatos/preparacao/rotulos_referencia.jsonl")}
    if set(rotulos) != referencias:
        raise ValueError("As referências devem corresponder a desenvolvimento e reserva.")
    receita = ler_json(raiz, "artefatos/melhorias-v1/receita_congelada.json")["parametros"]
    modelo = treinar(
        [qs[i] for i in sorted(referencias)], [rotulos[i] for i in sorted(referencias)],
        contexto["taxonomia"], receita, contexto["cache"],
    )
    modelo_bytes = _json(modelo)
    modelo = json.loads(modelo_bytes)
    registros = []
    for i in sorted(protocolo["avaliacao_ids"]):
        p = _calibrar(predizer(modelo, qs[i], contexto["cache"], top_k=5),
                      contexto, "calibrador80_aplicado_ajuste100")
        registros.append({
            **p, **decidir(p, contexto["politica"], contexto["motivos"]),
            "procedencia": "avaliacao559_modelo100_calibrador80",
        })
    desenvolvimento = [
        p for p in ler_jsonl(raiz, f"{CALIBRACAO}/predicoes_calibradas.jsonl")
        if p["calibrador"] == contexto["calibrador"]["nome"]
    ]
    if Counter(p["id"] for p in desenvolvimento) != Counter({
        i: 1 for i in protocolo["desenvolvimento_ids"]
    }):
        raise ValueError("Cobertura das referências de desenvolvimento inválida.")
    registros.extend({
        **p, **decidir(p, contexto["politica"], contexto["motivos"]),
        "procedencia": "desenvolvimento80_oof_modelo_e_crossfit_calibrador",
    } for p in desenvolvimento)
    reserva = ler_jsonl(raiz, f"{RESERVA}/predicoes_reserva.jsonl")
    if Counter(p["id"] for p in reserva) != Counter({i: 1 for i in protocolo["reserva_ids"]}):
        raise ValueError("Cobertura das referências reservadas inválida.")
    registros.extend(reserva)
    registros.sort(key=lambda r: r["id"])
    csv = gerar_csv(registros)
    contrato = validar_csv(csv, set(qs), contexto["taxonomia"])
    metricas_reserva = ler_json(raiz, f"{RESERVA}/metricas_reserva.json")
    previsao, texto = gerar_previsao(
        registros, set(protocolo["avaliacao_ids"]), metricas_reserva, len(referencias),
    )
    grupos = {
        "antigas_sem_referencia": [r for r in registros
                                 if r["id"] in set(protocolo["avaliacao_ids"]) and int(r["id"][1:]) <= 359],
        "recentes_sem_referencia": [r for r in registros
                                   if r["id"] in set(protocolo["avaliacao_ids"]) and int(r["id"][1:]) > 359],
    }
    previsao["decisoes_por_coorte_somente_diagnostico"] = {
        nome: {"total": len(rs), "decisoes": {d: sum(r["decisao"] == d for r in rs)
                                           for d in ("publicar", "revisar", "fora")}}
        for nome, rs in grupos.items()
    }
    previsao["procedencias_csv"] = dict(sorted(Counter(r["procedencia"] for r in registros).items()))
    produtos = {
        "publicacao.csv": csv, "previsao.txt": texto, "previsao.json": _json(previsao),
        "decisoes.jsonl": _jsonl(registros), "modelo_final.json": modelo_bytes,
    }
    produtos["manifesto.json"] = _manifesto(contexto, produtos, "entrega")
    conferir_assinaturas(raiz, contexto["fontes"])
    selo_congelamento(raiz)
    return produtos, {
        **contrato, "avaliacao": len(protocolo["avaliacao_ids"]),
        "publicadas_avaliacao": previsao["publicadas"],
        "cobertura_avaliacao": previsao["cobertura_prevista"],
        "precisao_prevista": previsao["precisao_prevista"],
        "ajuste_final_testado_independentemente": False,
    }


def _publicar_raiz(raiz: Path, produtos: dict[str, bytes]) -> None:
    """Publica somente os dois nomes de entrega, preservando outros arquivos."""
    nomes = ("publicacao.csv", "previsao.txt")
    for nome in nomes:
        destino = raiz / nome
        if (destino.is_symlink() or (destino.exists() and (
                not destino.is_file() or destino.read_bytes() != produtos[nome]))):
            raise ValueError(f"Entrega existente divergente: {nome}; preserve-a antes de gerar outra.")
    for nome in nomes:
        destino = raiz / nome
        if destino.exists():
            continue
        temporario = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=raiz, prefix=".produto-", suffix=".tmp", delete=False,
            ) as arquivo:
                temporario = Path(arquivo.name)
                arquivo.write(produtos[nome])
            if destino.exists():
                if destino.is_symlink() or destino.read_bytes() != produtos[nome]:
                    raise ValueError("Destino mudou durante a escrita da entrega.")
            else:
                os.replace(temporario, destino)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)


def executar_entrega(raiz: Path, verificar: bool = False) -> dict:
    saida = _validar_saida(raiz, raiz / DECISOES)
    produtos, resumo = construir_entrega(raiz)
    if verificar:
        _conferir_existentes(saida, produtos, exigir_completo=True)
        for nome in ("publicacao.csv", "previsao.txt"):
            if (raiz / nome).is_symlink() or not (raiz / nome).is_file() or (raiz / nome).read_bytes() != produtos[nome]:
                raise ValueError("Entrega da raiz diverge do artefato reproduzido.")
    else:
        publicar_produtos(saida, produtos)
        _publicar_raiz(raiz, produtos)
    return resumo


def verificar_tudo(raiz: Path) -> dict:
    executar_calibracao(raiz, verificar=True)
    print("Calibração e congelamento reproduzidos.", flush=True)
    executar_reserva(raiz, verificar=True)
    print("Avaliação reservada reproduzida sem alterar a política.", flush=True)
    resultado = executar_entrega(raiz, verificar=True)
    return {**resultado, "produtos_reconstruidos_identicos": 15, "entregas_raiz_identicas": 2}
