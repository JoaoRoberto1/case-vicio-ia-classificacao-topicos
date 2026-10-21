"""Reproduz M8 e seus três arquivos finais em cópia permitida, sem encoder/rede.

Uso: python -E -B -S -X utf8 scripts/verificar_precisao.py
     python -E -B -S -X utf8 scripts/verificar_precisao.py --evidencia tmp/outra-prova.json

A evidência padrão é artefatos/checkpoints/reproducao_modulo8.json e nunca é
sobrescrita. PDF e Markdown editoriais, quando presentes, têm somente os
bytes preservados; sua renderização não faz parte desta reprodução.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time


_SPEC = importlib.util.spec_from_file_location(
    "verificar_catalogo_helpers_m8", Path(__file__).with_name("verificar_catalogo.py"))
m7 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m7)
m6, m5 = m7.m6, m7.m5

ARTEFATOS = "artefatos/precisao-m8-v1"
CACHE = "artefatos/embeddings-e5-large-m8"
ENTREGA = "entrega-final-v2"
ARQUIVOS_ENTREGA = frozenset({"publicacao.csv", "previsao.txt", "previsao.json"})
MARCADOR = "AMBIENTE_M8="
CONCLUSAO = "ENTREGA_M8="
EVIDENCIA_PADRAO = "artefatos/checkpoints/reproducao_modulo8.json"
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
print('AMBIENTE_M8=' + json.dumps(ambiente, sort_keys=True), flush=True)
sys.argv = ['scripts/entregar_precisao.py', '--verificar']
runpy.run_path('scripts/entregar_precisao.py', run_name='__main__')
"""


def _produtos(raiz: Path, pasta: str) -> set[str]:
    nomes = set(m7._fontes(raiz, f"{pasta}/manifesto.json", "produtos_sha256"))
    if any(not n or "/" in n or "\\" in n or ":" in n or n in {".", "..", "manifesto.json"}
           for n in nomes):
        raise ValueError("Produtos do manifesto devem ser arquivos diretos, sem caminhos externos.")
    return nomes | {"manifesto.json"}


def listar_arquivos(raiz: Path) -> list[str]:
    nomes = set(m7.listar_arquivos(raiz))
    checkpoint = "artefatos/checkpoints/modulo7.json"
    nomes.add(checkpoint)
    nomes.update(m7._fontes(raiz, checkpoint, "artefatos_sha256"))
    nomes.update(m7._fontes(raiz, f"{ARTEFATOS}/manifesto.json", "entradas_implementacao_sha256"))
    nomes.update(m7._fontes(raiz, f"{CACHE}/manifesto.json", "fontes_sha256"))
    for pasta in (ARTEFATOS, CACHE):
        produtos = _produtos(raiz, pasta)
        nomes.update(f"{pasta}/{n}" for n in produtos)
        if pasta == ARTEFATOS:
            presentes = {p.name for p in m5.caminho_local(raiz, pasta, arquivo=False).iterdir()}
            if presentes != produtos:
                raise ValueError("Produtos M8 ausentes ou inesperados em relação ao manifesto.")
    for diretorio, padrao in (("classificacao_precisao", "*.py"), ("config/modulo8", "*.json")):
        encontrados = list(m5.caminho_local(raiz, diretorio, arquivo=False).glob(padrao))
        if not encontrados or any(not p.is_file() for p in encontrados):
            raise ValueError(f"Diretório M8 vazio ou inválido: {diretorio}")
        nomes.update(p.relative_to(raiz).as_posix() for p in encontrados)
    nomes.update({"classificacao_precisao/.gitattributes", "scripts/entregar_precisao.py",
                  "scripts/verificar_precisao.py"})
    nomes.update(f"{ENTREGA}/{n}" for n in ARQUIVOS_ENTREGA)
    # Conteúdo editorial é preservado por hash, sem executar geradores ou ler seu significado.
    for diretorio, padrao in ((ENTREGA, "*.md"), (ENTREGA, "*.pdf"),
                             ("docs", "*MODULO8*.md"), ("docs", "*M8*.md")):
        pasta = m5.caminho_local(raiz, diretorio, arquivo=False)
        if pasta.exists():
            nomes.update(p.relative_to(raiz).as_posix() for p in pasta.glob(padrao) if p.is_file())
    for nome in nomes:
        if not isinstance(nome, str) or not m6._nome_permitido(nome.casefold()):
            raise ValueError("Credenciais, ambientes e pesos não integram a cópia M8.")
        m5.caminho_local(raiz, nome)
    return sorted(nomes)


def interpretar_saida(linhas: list[str], produtos_esperados: int) -> tuple[dict, dict]:
    if type(produtos_esperados) is not int or produtos_esperados < 2:
        raise ValueError("A contagem de produtos deve vir do manifesto M8.")
    if not linhas or not linhas[0].startswith(MARCADOR) or not linhas[-1].startswith(CONCLUSAO):
        raise ValueError("Subprocesso M8 não comprovou isolamento e entrega completa.")
    isolamento = json.loads(linhas[0][len(MARCADOR):])
    if (not isinstance(isolamento, dict) or set(isolamento) != m6.CAMPOS_ISOLAMENTO
            or any(v is not True for v in isolamento.values())):
        raise ValueError("Isolamento do subprocesso M8 inválido.")
    resumo = json.loads(linhas[-1][len(CONCLUSAO):])
    if (not isinstance(resumo, dict) or resumo.get("verificado") is not True
            or type(resumo.get("produtos_experimento")) is not int
            or resumo["produtos_experimento"] != produtos_esperados
            or type(resumo.get("arquivos_entrega")) is not int or resumo["arquivos_entrega"] != 3
            or type(resumo.get("questoes")) is not int or resumo["questoes"] != 659
            or resumo.get("encoder_executado") is not False
            or type(resumo.get("chamadas_api")) is not int or resumo["chamadas_api"] != 0
            or not isinstance(resumo.get("receita"), str) or not resumo["receita"]):
        raise ValueError("M8 não confirmou os produtos do manifesto, três entregas e 659 questões.")
    avaliacao = resumo.get("avaliacao559")
    if (not isinstance(avaliacao, dict) or type(avaliacao.get("total")) is not int
            or avaliacao["total"] != 559 or avaliacao.get("precisao_observada") is not None):
        raise ValueError("Resumo M8 deve identificar 559 questões sem precisão observada.")
    return isolamento, resumo


def executar_comando(raiz: Path, ambiente: dict, *, timeout: float = 1800) -> dict:
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 1800):
        raise ValueError("Timeout deve estar entre zero e 1800 segundos.")
    produtos_esperados = len(_produtos(raiz, ARTEFATOS))
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
                raise RuntimeError(f"Reprodução M8 excedeu {timeout:g} segundos.")
            try:
                evento = eventos.get(timeout=min(30, restante))
            except queue.Empty:
                evento = ""
            if evento is None:
                break
            if isinstance(evento, Exception):
                raise RuntimeError("Falha ao ler a saída UTF-8 da reprodução M8.") from evento
            if evento:
                linhas.append(evento)
            if time.perf_counter() - ultima_notificacao >= 30:
                print(f"Reprodução M8 em andamento: {time.perf_counter() - inicio:.0f}s.", flush=True)
                ultima_notificacao = time.perf_counter()
        try:
            codigo = processo.wait(timeout=max(0.01, timeout - (time.perf_counter() - inicio)))
        except subprocess.TimeoutExpired as erro:
            raise RuntimeError(f"Reprodução M8 excedeu {timeout:g} segundos.") from erro
        if codigo != 0:
            raise RuntimeError(f"Reprodução M8 falhou com código {codigo}; nenhuma evidência aprovada foi emitida.")
        isolamento, resumo = interpretar_saida(linhas, produtos_esperados)
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
        leitor.join(timeout=1)
        processo.stdout.close()
    return {
        "script": "scripts/entregar_precisao.py", "operacao": "--verificar",
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
    if (absoluto.parent != limite or not absoluto.name.startswith("reproducao-m8-")
            or m5._link(absoluto)):
        raise ValueError("Remoção recusada: temporário fora do tmp permitido.")
    if absoluto.exists():
        if any(m5._link(p) for p in absoluto.rglob("*")):
            raise ValueError("Remoção recusada: temporário contém link ou junction.")
        shutil.rmtree(absoluto)


def verificar(raiz: Path, evidencia: str = EVIDENCIA_PADRAO) -> dict:
    raiz = raiz.absolute()
    m5.destino_evidencia(raiz, evidencia)
    inicio, inicio_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    nomes = listar_arquivos(raiz)
    fontes = m5.inventario(raiz, nomes)
    esperados = len(_produtos(raiz, ARTEFATOS))
    tmp = m5.caminho_local(raiz, "tmp", arquivo=False)
    tmp.mkdir(exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="reproducao-m8-", dir=tmp))
    try:
        copia, ambiente_dir = base / "etapa-complementar", base / "ambiente"
        ambiente_dir.mkdir()
        m5.materializar(raiz, copia, fontes)
        print("Verificando M8 e entrega na cópia permitida; rede, .env e encoder bloqueados...", flush=True)
        resultado = executar_comando(copia, m6.ambiente_limpo(ambiente_dir))
        if resultado.get("resumo", {}).get("produtos_experimento") != esperados:
            raise ValueError("Quantidade reproduzida difere do manifesto original.")
        m5.conferir_copia(copia, fontes)
        if listar_arquivos(raiz) != nomes or m5.inventario(raiz, nomes) != fontes:
            raise ValueError("Fontes originais mudaram durante a reprodução M8.")
    finally:
        remover_temporario(raiz, base)
    documento = {
        "schema": "reproducao_precisao_m8_v1", "status": "aprovado",
        "inicio_utc": inicio_utc, "segundos": round(time.perf_counter() - inicio, 3),
        "ambiente": {"python": platform.python_version(), "implementacao": platform.python_implementation(),
                     "sistema": platform.system(), "arquitetura": platform.machine()},
        "materializacao": "Cópia temporária por lista permitida sob etapa/tmp; não é clone Git ou VM.",
        "limites": [
            "Reutiliza o interpretador instalado e sua biblioteca padrão.",
            "Recebe caches numéricos versionados; não reproduz embeddings ou enriquecimento do catálogo.",
            "M1 a M7 fornecem insumos conferidos por hashes; seus experimentos não são refeitos aqui.",
            "PDF e Markdown editoriais são preservados por hash; layout não é avaliado nesta rotina.",
            "Não verifica acesso remoto ou estado do Git; reprodução não é nova avaliação estatística independente.",
        ],
        "arquivos_copiados": len(fontes), "bytes_copiados": sum(r["bytes"] for r in fontes.values()),
        "fontes_sha256_e_bytes": fontes, "fontes_originais_preservadas": True,
        "copia_final_identica": True, "execucao": resultado,
        "produtos_m8_reconstruidos_identicos": esperados,
        "arquivos_entrega_reconstruidos_identicos": 3, "dependencias_instaladas": 0,
        "encoder_executado": False, "rede_env_encoder_pesos_bloqueados": True,
        "credenciais_ambiente_herdadas": False,
    }
    saida = m5.destino_evidencia(raiz, evidencia)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("xb") as arquivo:
        arquivo.write(m5._json(documento))
    return {k: documento[k] for k in (
        "status", "segundos", "arquivos_copiados", "bytes_copiados",
        "produtos_m8_reconstruidos_identicos", "arquivos_entrega_reconstruidos_identicos",
        "fontes_originais_preservadas")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidencia", default=EVIDENCIA_PADRAO,
                        help="Novo JSON em tmp/ ou artefatos/checkpoints/; nunca sobrescreve.")
    argumentos = parser.parse_args()
    raiz = Path(__file__).absolute().parent.parent
    try:
        resultado = verificar(raiz, argumentos.evidencia)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    print(json.dumps({**resultado, "evidencia": argumentos.evidencia}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
