"""Reproduz M6 em cópia permitida, sem rede, encoder, .env ou site-packages.

Uso: python -B -S scripts/verificar_refinamento.py
     python -B -S scripts/verificar_refinamento.py --evidencia artefatos/checkpoints/reproducao_modulo6.json

A cópia usa o Python instalado e caches numéricos versionados. Não é clone Git,
máquina virtual, reprodução dos embeddings ou novo teste estatístico.
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
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid


_SPEC = importlib.util.spec_from_file_location(
    "verificar_entrega_helpers_m6", Path(__file__).with_name("verificar_entrega.py"))
m5 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m5)

ARTEFATOS = "artefatos/refinamento-v1"
MARCADOR = "AMBIENTE_M6="
CAMPOS_ISOLAMENTO = {
    "no_site", "ignore_environment", "dont_write_bytecode", "site_packages_no_path",
    "rede_env_encoder_pesos_bloqueados",
}
PROGRESSOS = (
    "OOF concluído; baseline M3 idêntica; iniciando avaliação aninhada.",
    "Avaliação aninhada: partição externa ",
    "Diagnóstico pós-seleção concluído; gerando sugestões experimentais para559.",
)
BOOTSTRAP = """import json, runpy, sys
from classificacao_decisao.__main__ import _bloquear_operacoes
_bloquear_operacoes(False)
ambiente = {
    'no_site': bool(sys.flags.no_site),
    'ignore_environment': bool(sys.flags.ignore_environment),
    'dont_write_bytecode': bool(sys.flags.dont_write_bytecode),
    'site_packages_no_path': not any('site-packages' in p or 'dist-packages' in p for p in sys.path),
    'rede_env_encoder_pesos_bloqueados': True,
}
if not all(ambiente.values()):
    raise RuntimeError('Isolamento Python incompleto.')
print('AMBIENTE_M6=' + json.dumps(ambiente, sort_keys=True), flush=True)
sys.argv = ['classificacao_refinamento', 'verificar']
runpy.run_module('classificacao_refinamento', run_name='__main__')
"""


def _nome_permitido(nome: str) -> bool:
    partes = PurePosixPath(nome).parts
    return not any(
        p in {".venv", "venv", ".cache-modelos", "__pycache__", ".git"}
        or p == ".env" or p.startswith(".env.") for p in partes
    ) and PurePosixPath(nome).suffix.lower() not in {".onnx", ".safetensors", ".pyc", ".pth", ".pt"}


def listar_arquivos(raiz: Path) -> list[str]:
    nomes = set(m5.listar_arquivos(raiz))
    fontes = json.loads(m5.caminho_local(raiz, "config/modulo6/fontes.json").read_text(encoding="utf-8"))
    assinaturas = fontes.get("sha256")
    if not isinstance(assinaturas, dict) or not assinaturas:
        raise ValueError("Manifesto M6 sem fontes assinadas.")
    nomes.update(assinaturas)
    for diretorio, padrao in (("classificacao_refinamento", "*.py"),
                             ("config/modulo6", "*.json"), (ARTEFATOS, "*")):
        caminho = m5.caminho_local(raiz, diretorio, arquivo=False)
        arquivos = list(caminho.glob(padrao))
        if not arquivos or any(not p.is_file() for p in arquivos):
            raise ValueError(f"Diretório M6 ausente, vazio ou com entrada inesperada: {diretorio}")
        nomes.update(p.relative_to(raiz).as_posix() for p in arquivos)
    nomes.add("scripts/verificar_refinamento.py")
    if f"{ARTEFATOS}/manifesto.json" not in nomes:
        raise ValueError("Manifesto de resultados M6 ausente.")
    for nome in nomes:
        if not isinstance(nome, str) or not _nome_permitido(nome):
            raise ValueError("Ambientes, credenciais e pesos não integram a cópia M6.")
        m5.caminho_local(raiz, nome)
    return sorted(nomes)


def ambiente_limpo(temporario: Path, herdado: dict | None = None) -> dict:
    origem = os.environ if herdado is None else herdado
    ambiente = {k: v for k, v in origem.items() if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    ambiente.update({"TEMP": str(temporario), "TMP": str(temporario)})
    return ambiente


def interpretar_saida(linhas: list[str]) -> tuple[dict, dict]:
    if len(linhas) < 2 or not linhas[0].startswith(MARCADOR):
        raise ValueError("Subprocesso M6 não comprovou isolamento.")
    isolamento = json.loads(linhas[0][len(MARCADOR):])
    if (not isinstance(isolamento, dict) or set(isolamento) != CAMPOS_ISOLAMENTO
            or any(v is not True for v in isolamento.values())):
        raise ValueError("Isolamento do subprocesso M6 inválido.")
    resumo = json.loads(linhas[-1])
    if (not isinstance(resumo, dict) or resumo.get("comando") != "verificar"
            or resumo.get("sugestoes_experimentais") != 559
            or not isinstance(resumo.get("receita_selecionada"), str)):
        raise ValueError("M6 não confirmou a reprodução e as 559 sugestões experimentais.")
    return isolamento, resumo


def executar_comando(raiz: Path, ambiente: dict, *, timeout: float = 1800) -> dict:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 1800:
        raise ValueError("Timeout deve estar entre zero e 1800 segundos.")
    python = getattr(sys, "_base_executable", sys.executable) or sys.executable
    comando = [python, "-B", "-S", "-E", "-X", "utf8", "-c", BOOTSTRAP]
    inicio = time.perf_counter()
    processo = subprocess.Popen(comando, cwd=raiz, env=ambiente, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="strict")
    eventos = queue.Queue()

    def ler():
        try:
            for linha in processo.stdout:
                eventos.put(linha.rstrip("\r\n"))
        except (OSError, UnicodeError) as erro:
            eventos.put(erro)
        finally:
            eventos.put(None)

    leitor = threading.Thread(target=ler, daemon=True)
    leitor.start()
    linhas, ultima_notificacao = [], inicio
    try:
        while True:
            agora = time.perf_counter()
            restante = timeout - (agora - inicio)
            if restante <= 0:
                raise RuntimeError(f"Reprodução M6 excedeu {timeout:g} segundos.")
            try:
                evento = eventos.get(timeout=min(30, restante))
            except queue.Empty:
                evento = ""
            if evento is None:
                break
            if isinstance(evento, Exception):
                raise RuntimeError("Falha ao ler a saída UTF-8 da reprodução M6.") from evento
            if evento:
                linhas.append(evento)
                if any(evento.startswith(prefixo) for prefixo in PROGRESSOS):
                    print(evento, flush=True)
                    ultima_notificacao = time.perf_counter()
            if time.perf_counter() - ultima_notificacao >= 30:
                print(f"Reprodução M6 em andamento: {time.perf_counter() - inicio:.0f}s.", flush=True)
                ultima_notificacao = time.perf_counter()
        try:
            codigo = processo.wait(timeout=max(0.01, timeout - (time.perf_counter() - inicio)))
        except subprocess.TimeoutExpired as erro:
            raise RuntimeError(f"Reprodução M6 excedeu {timeout:g} segundos.") from erro
        if codigo != 0:
            raise RuntimeError(f"Reprodução M6 falhou com código {codigo}; nenhuma evidência aprovada foi emitida.")
        isolamento, resumo = interpretar_saida(linhas)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
        leitor.join(timeout=1)
        processo.stdout.close()
    return {
        "modulo": "classificacao_refinamento", "operacao": "verificar",
        "argumentos_python": comando[1:7], "bootstrap_sha256": hashlib.sha256(BOOTSTRAP.encode()).hexdigest(),
        "exit_code": codigo, "segundos": round(time.perf_counter() - inicio, 3),
        "isolamento": isolamento, "resumo": resumo,
    }


def remover_temporario(raiz: Path, temporario: Path) -> None:
    limite = m5.caminho_local(raiz, "tmp", arquivo=False).resolve()
    solicitado = temporario.absolute()
    if m5._link(solicitado):
        raise ValueError("Remoção recusada: temporário é link ou junction.")
    # resolve também expande nomes curtos 8.3 usados por TEMP no Windows.
    absoluto = solicitado.resolve()
    if (absoluto.parent != limite or not absoluto.name.startswith("reproducao-m6-")
            or m5._link(absoluto)):
        raise ValueError("Remoção recusada: temporário não está diretamente no tmp permitido.")
    if absoluto.exists():
        if any(m5._link(p) for p in absoluto.rglob("*")):
            raise ValueError("Remoção recusada: temporário contém link ou junction.")
        shutil.rmtree(absoluto)


def verificar(raiz: Path, evidencia: str) -> dict:
    raiz = raiz.absolute()
    m5.destino_evidencia(raiz, evidencia)
    inicio, inicio_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    nomes = listar_arquivos(raiz)
    fontes = m5.inventario(raiz, nomes)
    tmp = m5.caminho_local(raiz, "tmp", arquivo=False)
    tmp.mkdir(exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="reproducao-m6-", dir=tmp))
    try:
        copia, ambiente_dir = base / "etapa-complementar", base / "ambiente"
        ambiente_dir.mkdir()
        m5.materializar(raiz, copia, fontes)
        print("Verificando M6 na cópia temporária; rede, .env e encoder bloqueados...", flush=True)
        resultado = executar_comando(copia, ambiente_limpo(ambiente_dir))
        m5.conferir_copia(copia, fontes)
        if listar_arquivos(raiz) != nomes or m5.inventario(raiz, nomes) != fontes:
            raise ValueError("Fontes originais mudaram durante a reprodução M6.")
    finally:
        remover_temporario(raiz, base)
    produtos = sum(n.startswith(ARTEFATOS + "/") for n in nomes)
    documento = {
        "schema": "reproducao_refinamento_m6_v1", "status": "aprovado",
        "inicio_utc": inicio_utc, "segundos": round(time.perf_counter() - inicio, 3),
        "ambiente": {"python": platform.python_version(), "implementacao": platform.python_implementation(),
                     "sistema": platform.system(), "arquitetura": platform.machine()},
        "materializacao": "Cópia temporária por lista permitida sob etapa/tmp; não é clone Git ou VM.",
        "limites": [
            "Reutiliza o interpretador instalado e sua biblioteca padrão.",
            "Recebe caches numéricos versionados; não reproduz os embeddings.",
            "M1 a M5 fornecem insumos conferidos por hashes; seus experimentos não são refeitos aqui.",
            "Não verifica layout do PDF, acesso remoto ou estado do Git.",
            "Reprodução computacional não é novo teste estatístico independente.",
        ],
        "arquivos_copiados": len(fontes), "bytes_copiados": sum(r["bytes"] for r in fontes.values()),
        "fontes_sha256_e_bytes": fontes, "fontes_originais_preservadas": True,
        "copia_final_identica": True, "execucao": resultado,
        "produtos_m6_reconstruidos_identicos": produtos, "dependencias_instaladas": 0,
        "encoder_executado": False, "rede_env_encoder_pesos_bloqueados": True,
        "credenciais_ambiente_herdadas": False,
    }
    saida = m5.destino_evidencia(raiz, evidencia)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("xb") as arquivo:
        arquivo.write(m5._json(documento))
    return {k: documento[k] for k in (
        "status", "segundos", "arquivos_copiados", "bytes_copiados",
        "produtos_m6_reconstruidos_identicos", "fontes_originais_preservadas")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidencia", help="Novo JSON em tmp/ ou artefatos/checkpoints/; nunca sobrescreve.")
    argumentos = parser.parse_args()
    raiz = Path(__file__).absolute().parent.parent
    evidencia = argumentos.evidencia or f"tmp/reproducao-modulo6-{uuid.uuid4().hex}.json"
    try:
        resultado = verificar(raiz, evidencia)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    print(json.dumps({**resultado, "evidencia": evidencia}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
