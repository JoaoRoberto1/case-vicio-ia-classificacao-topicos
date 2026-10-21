"""Reproduz os onze produtos M7 em cópia permitida, sem rede, .env ou encoder.

Uso: python -E -B -S -X utf8 scripts/verificar_catalogo.py
     python -E -B -S -X utf8 scripts/verificar_catalogo.py --evidencia artefatos/checkpoints/reproducao_modulo7.json

Reutiliza o Python instalado e vetores versionados. Não regenera embeddings,
não cria uma máquina virtual e não constitui nova avaliação estatística.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
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
    "verificar_refinamento_helpers_m7", Path(__file__).with_name("verificar_refinamento.py"))
m6 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m6)
m5 = m6.m5

ARTEFATOS = "artefatos/catalogo-m7-v1"
CACHE = "artefatos/catalogo-m7-embeddings"
MARCADOR = "AMBIENTE_M7="
CONCLUSAO = "RESULTADO_M7="
CONFIRMACAO = "Reprodução M7: todos os11 arquivos idênticos byte a byte."
BOOTSTRAP = """import json, pathlib, runpy, sys
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
print('AMBIENTE_M7=' + json.dumps(ambiente, sort_keys=True), flush=True)
sys.argv = ['classificacao_catalogo', 'verificar']
runpy.run_module('classificacao_catalogo', run_name='__main__')
diretorio = pathlib.Path('artefatos/catalogo-m7-v1')
manifesto = json.loads((diretorio / 'manifesto.json').read_text(encoding='utf-8'))
metricas = json.loads((diretorio / 'metricas.json').read_text(encoding='utf-8'))
resumo = {
    'comando': 'verificar',
    'produtos_reconstruidos_identicos': len(manifesto['produtos_sha256']) + 1,
    'sugestoes_experimentais': metricas['avaliacao559']['total'],
    'receita_selecionada': metricas['receita_selecionada'],
}
print('RESULTADO_M7=' + json.dumps(resumo, sort_keys=True), flush=True)
"""


def _fontes(raiz: Path, nome: str, campo: str) -> dict:
    documento = json.loads(m5.caminho_local(raiz, nome).read_text(encoding="utf-8"))
    fontes = documento.get(campo)
    if (not isinstance(fontes, dict) or not fontes
            or any(not isinstance(n, str) or not isinstance(h, str)
                   or len(h) != 64 or any(c not in "0123456789abcdef" for c in h)
                   for n, h in fontes.items())):
        raise ValueError(f"Manifesto sem fontes SHA-256 válidas: {nome}")
    return fontes


def listar_arquivos(raiz: Path) -> list[str]:
    nomes = set(m6.listar_arquivos(raiz))
    for modulo in (5, 6):
        nome = f"artefatos/checkpoints/modulo{modulo}.json"
        nomes.add(nome)
        nomes.update(_fontes(raiz, nome, "artefatos_sha256"))
    nomes.update(_fontes(raiz, f"{CACHE}/manifesto.json", "fontes_sha256"))
    nomes.update(_fontes(raiz, f"{ARTEFATOS}/manifesto.json", "entradas_implementacao_sha256"))
    for diretorio, padrao in (("classificacao_catalogo", "*.py"),
                             ("config/modulo7", "*.json"), (CACHE, "*"), (ARTEFATOS, "*")):
        caminho = m5.caminho_local(raiz, diretorio, arquivo=False)
        arquivos = list(caminho.glob(padrao))
        if not arquivos or any(not p.is_file() for p in arquivos):
            raise ValueError(f"Diretório M7 vazio, ausente ou com entrada inesperada: {diretorio}")
        nomes.update(p.relative_to(raiz).as_posix() for p in arquivos)
    nomes.update({"classificacao_catalogo/.gitattributes", "scripts/verificar_catalogo.py"})
    for nome in nomes:
        if not isinstance(nome, str) or not m6._nome_permitido(nome.casefold()):
            raise ValueError("Credenciais, ambientes e pesos não integram a cópia M7.")
        m5.caminho_local(raiz, nome)
    produtos = {n.removeprefix(ARTEFATOS + "/") for n in nomes if n.startswith(ARTEFATOS + "/")}
    esperados = set(_fontes(raiz, f"{ARTEFATOS}/manifesto.json", "produtos_sha256")) | {"manifesto.json"}
    if produtos != esperados or len(produtos) != 11:
        raise ValueError("M7 deve conter exatamente os onze produtos do manifesto.")
    return sorted(nomes)


def interpretar_saida(linhas: list[str]) -> tuple[dict, dict]:
    if (not linhas or not linhas[0].startswith(MARCADOR)
            or not linhas[-1].startswith(CONCLUSAO) or CONFIRMACAO not in linhas):
        raise ValueError("Subprocesso M7 não comprovou isolamento e reprodução completa.")
    isolamento = json.loads(linhas[0][len(MARCADOR):])
    if (not isinstance(isolamento, dict) or set(isolamento) != m6.CAMPOS_ISOLAMENTO
            or any(v is not True for v in isolamento.values())):
        raise ValueError("Isolamento do subprocesso M7 inválido.")
    resumo = json.loads(linhas[-1][len(CONCLUSAO):])
    if (not isinstance(resumo, dict) or resumo.get("comando") != "verificar"
            or resumo.get("produtos_reconstruidos_identicos") != 11
            or resumo.get("sugestoes_experimentais") != 559
            or not isinstance(resumo.get("receita_selecionada"), str)):
        raise ValueError("M7 não confirmou os onze produtos e as 559 sugestões.")
    return isolamento, resumo


def executar_comando(raiz: Path, ambiente: dict, *, timeout: float = 1800) -> dict:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 1800:
        raise ValueError("Timeout deve estar entre zero e 1800 segundos.")
    python = getattr(sys, "_base_executable", sys.executable) or sys.executable
    comando = [python, "-E", "-B", "-S", "-X", "utf8", "-c", BOOTSTRAP]
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
            restante = timeout - (time.perf_counter() - inicio)
            if restante <= 0:
                raise RuntimeError(f"Reprodução M7 excedeu {timeout:g} segundos.")
            try:
                evento = eventos.get(timeout=min(30, restante))
            except queue.Empty:
                evento = ""
            if evento is None:
                break
            if isinstance(evento, Exception):
                raise RuntimeError("Falha ao ler a saída UTF-8 da reprodução M7.") from evento
            if evento:
                linhas.append(evento)
            if time.perf_counter() - ultima_notificacao >= 30:
                print(f"Reprodução M7 em andamento: {time.perf_counter() - inicio:.0f}s.", flush=True)
                ultima_notificacao = time.perf_counter()
        try:
            codigo = processo.wait(timeout=max(0.01, timeout - (time.perf_counter() - inicio)))
        except subprocess.TimeoutExpired as erro:
            raise RuntimeError(f"Reprodução M7 excedeu {timeout:g} segundos.") from erro
        if codigo != 0:
            raise RuntimeError(f"Reprodução M7 falhou com código {codigo}; nenhuma evidência aprovada foi emitida.")
        isolamento, resumo = interpretar_saida(linhas)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
        leitor.join(timeout=1)
        processo.stdout.close()
    return {
        "modulo": "classificacao_catalogo", "operacao": "verificar",
        "argumentos_python": comando[1:7], "bootstrap_sha256": hashlib.sha256(BOOTSTRAP.encode()).hexdigest(),
        "exit_code": codigo, "segundos": round(time.perf_counter() - inicio, 3),
        "isolamento": isolamento, "resumo": resumo,
    }


def remover_temporario(raiz: Path, temporario: Path) -> None:
    limite = m5.caminho_local(raiz, "tmp", arquivo=False).resolve()
    solicitado = temporario.absolute()
    if m5._link(solicitado):
        raise ValueError("Remoção recusada: temporário é link ou junction.")
    absoluto = solicitado.resolve()
    if (absoluto.parent != limite or not absoluto.name.startswith("reproducao-m7-")
            or m5._link(absoluto)):
        raise ValueError("Remoção recusada: temporário fora do tmp permitido.")
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
    base = Path(tempfile.mkdtemp(prefix="reproducao-m7-", dir=tmp))
    try:
        copia, ambiente_dir = base / "etapa-complementar", base / "ambiente"
        ambiente_dir.mkdir()
        m5.materializar(raiz, copia, fontes)
        print("Verificando M7 na cópia permitida; rede, .env e encoder bloqueados...", flush=True)
        resultado = executar_comando(copia, m6.ambiente_limpo(ambiente_dir))
        m5.conferir_copia(copia, fontes)
        if listar_arquivos(raiz) != nomes or m5.inventario(raiz, nomes) != fontes:
            raise ValueError("Fontes originais mudaram durante a reprodução M7.")
    finally:
        remover_temporario(raiz, base)
    documento = {
        "schema": "reproducao_catalogo_m7_v1", "status": "aprovado",
        "inicio_utc": inicio_utc, "segundos": round(time.perf_counter() - inicio, 3),
        "ambiente": {"python": platform.python_version(), "implementacao": platform.python_implementation(),
                     "sistema": platform.system(), "arquitetura": platform.machine()},
        "materializacao": "Cópia temporária por lista permitida sob etapa/tmp; não é clone Git ou VM.",
        "limites": [
            "Reutiliza o interpretador instalado e sua biblioteca padrão.",
            "Recebe caches numéricos versionados; não reproduz embeddings nem enriquecimento do catálogo.",
            "M1 a M6 fornecem insumos conferidos por hashes; seus experimentos não são refeitos aqui.",
            "Não verifica layout do PDF, acesso remoto ou estado do Git.",
            "Reprodução computacional não é novo teste estatístico independente.",
        ],
        "arquivos_copiados": len(fontes), "bytes_copiados": sum(r["bytes"] for r in fontes.values()),
        "fontes_sha256_e_bytes": fontes, "fontes_originais_preservadas": True,
        "copia_final_identica": True, "execucao": resultado,
        "produtos_m7_reconstruidos_identicos": 11, "dependencias_instaladas": 0,
        "encoder_executado": False, "rede_env_encoder_pesos_bloqueados": True,
        "credenciais_ambiente_herdadas": False,
    }
    saida = m5.destino_evidencia(raiz, evidencia)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("xb") as arquivo:
        arquivo.write(m5._json(documento))
    return {k: documento[k] for k in (
        "status", "segundos", "arquivos_copiados", "bytes_copiados",
        "produtos_m7_reconstruidos_identicos", "fontes_originais_preservadas")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidencia", help="Novo JSON em tmp/ ou artefatos/checkpoints/; nunca sobrescreve.")
    argumentos = parser.parse_args()
    raiz = Path(__file__).absolute().parent.parent
    evidencia = argumentos.evidencia or f"tmp/reproducao-modulo7-{uuid.uuid4().hex}.json"
    try:
        resultado = verificar(raiz, evidencia)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    print(json.dumps({**resultado, "evidencia": evidencia}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
