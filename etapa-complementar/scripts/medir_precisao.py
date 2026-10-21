"""Mede a inferência M8 já ajustada, usando somente os caches numéricos.

Uso: python -B -S -E -X utf8 scripts/medir_precisao.py
     python -B -S -E -X utf8 scripts/medir_precisao.py --evidencia artefatos/checkpoints/benchmark_modulo8.json

Não treina, não recalibra e não executa encoder. Confere as 559 sugestões
inteiras antes de emitir uma nova evidência; nunca sobrescreve evidências.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import time
import uuid


_SPEC = importlib.util.spec_from_file_location(
    "verificar_entrega_helpers_benchmark_m8", Path(__file__).with_name("verificar_entrega.py"))
m5 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m5)
ARTEFATOS = "artefatos/precisao-m8-v1"
PRODUTOS_NECESSARIOS = {"modelo100.json", "politica.json", "calibradores.json", "sugestoes_avaliacao.jsonl"}
PACOTES = ("classificacao_topicos", "classificacao_local", "classificacao_experimentos",
           "classificacao_decisao", "classificacao_refinamento", "classificacao_catalogo", "classificacao_precisao")
_OPERACOES_BLOQUEADAS = False


def _jsonl(registros: list[dict]) -> bytes:
    return b"".join((json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
                    for r in registros)


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _conferir_hashes(raiz: Path, assinaturas: dict) -> None:
    if not isinstance(assinaturas, dict) or not assinaturas:
        raise ValueError("Manifesto sem assinaturas.")
    for nome, sha in assinaturas.items():
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("Assinatura inválida no manifesto.")
        if _sha(m5.caminho_local(raiz, nome).read_bytes()) != sha:
            raise ValueError("Fonte ou produto diverge do manifesto; benchmark recusado.")


def _universos(contexto: dict, modelo: dict, politica: dict, esperados: list[dict]) -> list[dict]:
    protocolo = contexto["protocolo"]
    listas = [protocolo[c] for c in ("desenvolvimento_ids", "reserva_ids", "avaliacao_ids")]
    dev, reserva, avaliacao = map(set, listas)
    qs = {q["id"]: q for q in contexto["questoes"]}
    treino = modelo["treino_ids"]
    ids_esperados = [p["id"] for p in esperados]
    if (tuple(map(len, listas)) != (80, 20, 559) or tuple(map(len, (dev, reserva, avaliacao))) != (80, 20, 559)
            or dev & reserva or (dev | reserva) & avaliacao
            or len(contexto["questoes"]) != 659 or set(qs) != dev | reserva | avaliacao
            or len(treino) != 100 or set(treino) != dev | reserva
            or len(ids_esperados) != 559 or set(ids_esperados) != avaliacao
            or politica["receita"] not in modelo["receitas"]
            or any(p["receita"] != politica["receita"] for p in esperados)):
        raise ValueError("Universos, modelo ou receita incompatíveis com a entrega M8 completa.")
    return [qs[i] for i in sorted(avaliacao)]


def carregar(raiz: Path) -> dict:
    """Valida os manifestos e instancia um motor sem consultas pré-computadas."""
    from classificacao_precisao.experimento import carregar_contexto
    from classificacao_precisao.motor import Motor

    manifesto_nome = f"{ARTEFATOS}/manifesto.json"
    manifesto_bytes = m5.caminho_local(raiz, manifesto_nome).read_bytes()
    manifesto = json.loads(manifesto_bytes)
    produtos = manifesto["produtos_sha256"]
    if (manifesto.get("schema") != "manifesto_precisao_m8_v1"
            or manifesto.get("llm_na_decisao") is not False
            or manifesto.get("encoder_na_decisao") is not False
            or type(manifesto.get("chamadas_api")) is not int or manifesto["chamadas_api"] != 0
            or not isinstance(produtos, dict) or not PRODUTOS_NECESSARIOS <= produtos.keys()
            or any(not isinstance(n, str) or PurePosixPath(n).name != n or n == "manifesto.json" for n in produtos)):
        raise ValueError("Manifesto M8 completo inválido ou incompatível com execução offline.")
    fontes = manifesto["entradas_implementacao_sha256"]
    produtos_locais = {f"{ARTEFATOS}/{n}": sha for n, sha in produtos.items()}
    _conferir_hashes(raiz, fontes)
    _conferir_hashes(raiz, produtos_locais)
    contexto, _, tax, docs, ancoras, cache, large, fontes_atuais = carregar_contexto(raiz, False)
    if fontes_atuais != fontes:
        raise ValueError("Entradas atuais divergem das entradas do experimento M8.")
    def ler(nome):
        return json.loads(m5.caminho_local(raiz, f"{ARTEFATOS}/{nome}").read_text(encoding="utf-8"))
    modelo, politica = ler("modelo100.json"), ler("politica.json")
    calibrador = ler("calibradores.json")["final80OOF"]
    esperados = [json.loads(linha) for linha in m5.caminho_local(raiz, f"{ARTEFATOS}/sugestoes_avaliacao.jsonl")
                 .read_text(encoding="utf-8").splitlines() if linha]
    questoes = _universos(contexto, modelo, politica, esperados)
    motor = Motor(tax, contexto["cache"], cache, docs, large, ancoras)
    scripts = {"scripts/medir_precisao.py", "scripts/verificar_entrega.py"}
    scripts.update(p.relative_to(raiz).as_posix() for pacote in PACOTES for p in (raiz / pacote).glob("*.py"))
    implementacao = {n: _sha(m5.caminho_local(raiz, n).read_bytes()) for n in sorted(scripts)}
    assinaturas = {**fontes, **produtos_locais, **implementacao, manifesto_nome: _sha(manifesto_bytes)}
    return {"motor": motor, "modelo": modelo, "politica": politica, "calibrador": calibrador,
            "questoes": questoes, "esperados": esperados, "fontes": fontes, "produtos": produtos_locais,
            "implementacao": implementacao, "assinaturas": assinaturas}


def comparar(atuais: list[dict], esperados: list[dict]) -> dict:
    """Compara todos os campos, inclusive listas e tipos JSON, sem revelar linhas."""
    if len(atuais) != len(esperados):
        raise ValueError("Quantidade de predições reproduzidas divergente.")
    if len({p["id"] for p in atuais}) != len(atuais) or len({p["id"] for p in esperados}) != len(esperados):
        raise ValueError("Predições duplicadas; benchmark recusado.")
    atuais, esperados = [sorted(ps, key=lambda p: p["id"]) for ps in (atuais, esperados)]
    divergentes = sum(_jsonl([a]) != _jsonl([b]) for a, b in zip(atuais, esperados))
    if divergentes:
        raise ValueError(f"Predições divergentes em {divergentes} registros; nenhuma linha foi exposta.")
    return {"registros_identicos": len(atuais), "todos_os_campos_identicos": True,
            "jsonl_canonico_sha256": _sha(_jsonl(atuais)),
            "publicaria_politica_candidata": sum(p["publicaria_politica_candidata"] for p in atuais)}


def medir(raiz: Path, evidencia: str) -> dict:
    """Executa apenas a inferência final; o CLI instala o bloqueio antes da carga."""
    from classificacao_precisao.confianca import prever, aplicar

    raiz = raiz.absolute()
    m5.destino_evidencia(raiz, evidencia)
    inicio_utc = datetime.now(timezone.utc).isoformat()
    inicio = time.perf_counter()
    bundle = carregar(raiz)
    carga = time.perf_counter() - inicio
    inicio_predicoes = time.perf_counter()
    atuais, ultima_notificacao = [], inicio_predicoes
    for q in bundle["questoes"]:
        p = bundle["motor"].predizer(q, bundle["modelo"], bundle["politica"]["receita"])
        p = {**p, "confianca": prever(bundle["calibrador"], p)}
        atuais.append({**p, "publicaria_politica_candidata": aplicar(p, bundle["politica"])})
        agora = time.perf_counter()
        if agora - ultima_notificacao >= 30:
            print(f"Benchmark M8: {len(atuais)}/{len(bundle['questoes'])} predições concluídas.", flush=True)
            ultima_notificacao = agora
    inferencia = time.perf_counter() - inicio_predicoes
    resultado = comparar(atuais, bundle["esperados"])
    esperado_sha = bundle["produtos"][f"{ARTEFATOS}/sugestoes_avaliacao.jsonl"]
    if resultado["jsonl_canonico_sha256"] != esperado_sha:
        raise ValueError("Serialização reproduzida diverge do produto assinado.")
    _conferir_hashes(raiz, bundle["assinaturas"])
    total = len(atuais)
    ambiente = {"python": platform.python_version(), "implementacao": platform.python_implementation(),
                "sistema": platform.system(), "versao_sistema": platform.version(), "arquitetura": platform.machine(),
                "processador": platform.processor(), "cpus_logicas": os.cpu_count(),
                "no_site": bool(sys.flags.no_site), "ignore_environment": bool(sys.flags.ignore_environment),
                "dont_write_bytecode": bool(sys.flags.dont_write_bytecode),
                "rede_env_encoder_pesos_bloqueados": _OPERACOES_BLOQUEADAS}
    documento = {
        "schema": "benchmark_precisao_m8_v1", "status": "aprovado", "inicio_utc": inicio_utc,
        "ambiente": ambiente, "ambiente_sha256": _sha(m5._json(ambiente)),
        "fontes_sha256": bundle["fontes"], "produtos_sha256": bundle["produtos"],
        "implementacao_benchmark_sha256": bundle["implementacao"], "arquivos_verificados_sha256": bundle["assinaturas"],
        "fontes_e_produtos_preservados": True, "receita": bundle["politica"]["receita"],
        "modelo": "modelo100.json", "calibrador": "final80OOF", "encoder_executado": False,
        "treino_executado": False, "recalibracao_executada": False,
        "tempos_segundos": {"carga_e_verificacao_inicial": carga, "inferencia_559": inferencia,
                            "total_com_verificacoes_finais": time.perf_counter() - inicio},
        "resultado": resultado, "resultado_sha256": _sha(m5._json(resultado)),
        "estimativa_linear_50000": {"segundos_so_inferencia": inferencia / total * 50000,
                                    "segundos_com_uma_carga": carga + inferencia / total * 50000,
                                    "medida_em_producao": False, "observacoes_base": total},
        "limites": [
            "Uma execução em ambiente compartilhado; tempos variam com hardware, carga e sistema de arquivos.",
            "Motor novo, sem consultas pré-computadas; o cache de arquivos do sistema operacional não foi esvaziado.",
            "A carga inclui manifestos, caches, artefatos e construção do motor; a inferência inclui ranking, confiança e política.",
            "A verificação final e a escrita da evidência ficam fora do tempo de inferência.",
            "A estimativa para 50 mil é linear e pressupõe vetores prontos; não mede produção nem inclui preparação, treino ou recalibração.",
            "As 559 questões não têm rótulos oficiais disponíveis; igualdade computacional não mede precisão nem cria teste independente.",
        ],
    }
    saida = m5.destino_evidencia(raiz, evidencia)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("xb") as arquivo:
        arquivo.write(m5._json(documento))
    return {"status": documento["status"], "tempos_segundos": documento["tempos_segundos"],
            "registros_identicos": resultado["registros_identicos"],
            "estimativa_linear_50000": documento["estimativa_linear_50000"]}


def main() -> int:
    global _OPERACOES_BLOQUEADAS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidencia", help="Novo JSON em tmp/ ou artefatos/checkpoints/; nunca sobrescreve.")
    argumentos = parser.parse_args()
    raiz = Path(__file__).absolute().parent.parent
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))
    from classificacao_decisao.__main__ import _bloquear_operacoes
    _bloquear_operacoes(False)
    _OPERACOES_BLOQUEADAS = True
    evidencia = argumentos.evidencia or f"tmp/benchmark-modulo8-{uuid.uuid4().hex}.json"
    try:
        resultado = medir(raiz, evidencia)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError, ImportError) as erro:
        # Erros de dependências podem carregar conteúdo dos insumos; não o imprimir.
        parser.exit(1, f"Benchmark recusado ({type(erro).__name__}); nenhuma evidência aprovada foi emitida.\n")
    print(json.dumps({**resultado, "evidencia": evidencia}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
