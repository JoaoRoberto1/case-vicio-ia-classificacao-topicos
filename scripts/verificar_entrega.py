"""Reconstrucao offline da entrega em pasta temporaria, sem alterar as fontes.

Requer Git e Python 3.11+. --pdf requer requirements-relatorio.txt.
Os recibos e julgamentos salvos sao entradas: nao chama modelos nem refaz revisoes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

RAIZ = Path(__file__).resolve().parents[1]
RECONSTRUIR = (
    "artefatos/preparacao/", "artefatos/piloto/", "artefatos/piloto-v2/",
    "artefatos/lote-v2/", "artefatos/lote-desambiguacao-v1/",
    "artefatos/decisoes-v1/", "artefatos/auditoria-v1/",
    "artefatos/experimento-cobertura-v2/propostas/", "artefatos/decisoes-v2/",
)
EXPANDIDOS = {
    "artefatos/piloto/entradas.jsonl", "artefatos/piloto-v2/entradas.jsonl",
    "artefatos/lote-v2/entradas.jsonl", "artefatos/lote-desambiguacao-v1/entradas.jsonl",
}
# Cada subprocesso bloqueia rede e leitura do .env real da copia. Os testes
# podem criar configuracoes sinteticas em suas proprias pastas temporarias.
RUNNER = r'''
import os, pathlib, runpy, sys
raiz = pathlib.Path.cwd().resolve()
def auditar(evento, argumentos):
    if evento in {"socket.connect", "socket.getaddrinfo", "urllib.Request"}:
        raise RuntimeError("Rede bloqueada na verificacao offline.")
    if evento == "open" and isinstance(argumentos[0], (str, bytes, os.PathLike)):
        caminho = pathlib.Path(os.fsdecode(argumentos[0])).resolve()
        if caminho == raiz / ".env":
            raise RuntimeError("Leitura do .env bloqueada na verificacao offline.")
sys.addaudithook(auditar)
tipo, alvo, *args = sys.argv[1:]
sys.argv = [alvo, *args]
sys.path.insert(0, str(raiz))
if tipo == "modulo":
    runpy.run_module(alvo, run_name="__main__")
else:
    runpy.run_path(alvo, run_name="__main__")
'''


def hash_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def normalizar_fontes_avaliacao(relatorio: dict) -> dict:
    """Normaliza somente o prefixo local das chaves de fontes da avaliacao v1."""
    resultado = dict(relatorio)
    fontes = {}
    for nome, digest in relatorio["fontes_sha256"].items():
        nome = nome.replace("\\", "/")
        marcadores = [i for marca in ("artefatos/", "config/") if (i := nome.rfind(marca)) >= 0]
        if not marcadores:
            raise ValueError(f"Fonte de avaliacao sem caminho reconhecido: {nome}")
        relativo = nome[max(marcadores):]
        if relativo in fontes:
            raise ValueError("Fontes colidem apos normalizar o prefixo local.")
        fontes[relativo] = digest
    resultado["fontes_sha256"] = fontes
    return resultado


def conferir_inventario(versionados: set[str], gerados: set[str]) -> None:
    esperados = versionados | EXPANDIDOS
    if gerados != esperados:
        raise ValueError(f"Inventario reconstruido divergente; ausentes={sorted(esperados - gerados)}, "
                         f"extras={sorted(gerados - esperados)}")


def verificar(*, incluir_pdf: bool = False, incluir_testes: bool = False) -> dict:
    inicio = time.monotonic()
    nomes = subprocess.check_output(["git", "ls-files", "-z"], cwd=RAIZ).decode("utf-8").split("\0")
    nomes = [n for n in nomes if n]
    # O verificador e seus testes tambem podem ser exercitados antes do primeiro commit.
    for nome in ("scripts/verificar_entrega.py", "tests/test_verificar_entrega.py"):
        if nome not in nomes and (RAIZ / nome).is_file():
            nomes.append(nome)
    proibidos = [n for n in nomes if Path(n).name == ".env" or
                 (Path(n).name.startswith(".env.") and Path(n).name != ".env.example") or
                 n.startswith(("contexto_local/", ".venv/", "venv/"))]
    if proibidos:
        raise ValueError("Arquivo privado incluido no conjunto versionado; corrija antes de verificar.")
    originais = {}
    for nome in nomes:
        caminho = RAIZ / nome
        if caminho.is_symlink() or not caminho.resolve().is_relative_to(RAIZ) or not caminho.is_file():
            raise ValueError(f"Fonte ausente, simbolica ou externa: {nome}")
        originais[nome] = hash_bytes(caminho.read_bytes())
    resultado = {
        "schema_version": 1, "procedimento": "verificacao-entrega-v1",
        "base_git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True).strip(),
        "registrado_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "plataforma": sys.platform,
        "git_status_inicial": subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=RAIZ, text=True).splitlines(),
        "verificador_sha256_lf": hash_bytes(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "fontes_sha256": originais,
        "arquivos_fonte": len(nomes), "rede_e_env_bloqueados": True,
        "passos": [], "comparacoes": [], "chamadas_api": 0,
    }
    with TemporaryDirectory(prefix="vicio-reproducao-") as temporaria:
        copia = Path(temporaria).resolve()
        if copia == RAIZ or not copia.name.startswith("vicio-reproducao-"):
            raise ValueError("Destino temporario fora do escopo da verificacao.")
        for nome in nomes:
            if nome.startswith(RECONSTRUIR):
                continue
            destino = copia / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / nome, destino)
        if (copia / ".env").exists():
            raise ValueError("A copia isolada nao pode conter .env.")

        def executar(tipo: str, alvo: str, *args: str) -> None:
            momento = time.monotonic()
            comando = [sys.executable, "-B", "-X", "utf8", "-c", RUNNER, tipo, alvo, *args]
            proc = subprocess.run(comando, cwd=copia, capture_output=True, text=True, encoding="utf-8")
            if proc.returncode:
                raise RuntimeError(f"Falha em {alvo} {' '.join(args)}:\n{proc.stdout}\n{proc.stderr}")
            passo = {"tipo": tipo, "alvo": alvo, "argumentos": list(args),
                     "codigo_saida": proc.returncode, "duracao_segundos": round(time.monotonic() - momento, 3)}
            if alvo == "unittest":
                passo["resultado"] = proc.stderr.strip()
            resultado["passos"].append(passo)
            print(f"OK: {alvo} {' '.join(args)}", flush=True)

        def cli(*args: str) -> None:
            executar("modulo", "classificacao_topicos", *args)

        cli("preparar")
        cli("preparar-piloto")
        cli("preparar-piloto", "--saida", "artefatos/piloto-v2", "--prompt", "prompts/classificacao_v2.txt", "--versao-prompt", "classificacao-v2")
        cli("preparar-lote", "--piloto-desenvolvimento", "artefatos/piloto-v2", "--saida", "artefatos/lote-v2", "--prompt", "prompts/classificacao_v2.txt", "--versao-prompt", "classificacao-v2")
        cli("revalidar-recibo", "--lote", "artefatos/lote-v2", "--execucao", "artefatos/execucoes/lote-v2-35-flash-lite", "--id", "Q0005")
        cli("preparar-decisoes", "--lote", "artefatos/lote-v2", "--execucao", "artefatos/execucoes/lote-v2-35-flash-lite", "--politica", "config/politica_v1.json", "--confirmacoes-fora", "artefatos/revisao_fora-v1/confirmacoes_fora.jsonl", "--saida", "artefatos/decisoes-v1")
        cli("preparar-auditoria", "--lote", "artefatos/lote-v2", "--decisoes", "artefatos/decisoes-v1", "--saida", "artefatos/auditoria-v1")
        cli("avaliar-auditoria", "--auditoria", "artefatos/auditoria-v1", "--decisoes", "artefatos/decisoes-v1", "--revisoes", "artefatos/revisao_auditoria-v1/referencias", "--saida", "reproduzidos/avaliacao-v1")
        executar("modulo", "classificacao_topicos.diagnostico_cobertura", "--decisoes", "artefatos/decisoes-v1", "--saida", "reproduzidos/cobertura-v1.json")
        cli("preparar-lote", "--piloto-desenvolvimento", "artefatos/piloto-v2", "--saida", "artefatos/lote-desambiguacao-v1", "--prompt", "prompts/desambiguacao_v1.txt", "--versao-prompt", "desambiguacao-v1")
        executar("modulo", "classificacao_topicos.experimento_cobertura", "propor")
        executar("modulo", "classificacao_topicos.experimento_cobertura", "concluir")

        versionados = {nome for nome in nomes if nome.startswith(RECONSTRUIR)}
        gerados = {p.relative_to(copia).as_posix() for pasta in RECONSTRUIR
                   for p in (copia / pasta).rglob("*") if p.is_file()}
        conferir_inventario(versionados, gerados)
        resultado["inventario_reconstruido"] = {
            "arquivos_versionados": len(versionados), "prompts_expandidos": len(EXPANDIDOS),
            "arquivos_gerados": len(gerados), "sem_ausencias_ou_extras": True}
        pares = [(nome, nome) for nome in nomes if nome.startswith(RECONSTRUIR)]
        pares.extend([
            ("publicacao.csv", "artefatos/decisoes-v2/publicacao.csv"),
            ("artefatos/avaliacao-v1/comparacao_auditoria.csv", "reproduzidos/avaliacao-v1/comparacao_auditoria.csv"),
            ("artefatos/analises/cobertura-v1.json", "reproduzidos/cobertura-v1.json"),
        ])
        for fonte, gerado in pares:
            if (RAIZ / fonte).read_bytes() != (copia / gerado).read_bytes():
                raise ValueError(f"Reproducao divergente: {fonte}")
            resultado["comparacoes"].append({"arquivo": fonte, "metodo": "byte_a_byte", "sha256": originais[fonte]})
        original = json.loads((RAIZ / "artefatos/avaliacao-v1/relatorio_avaliacao.json").read_bytes())
        novo = json.loads((copia / "reproduzidos/avaliacao-v1/relatorio_avaliacao.json").read_bytes())
        if normalizar_fontes_avaliacao(original) != normalizar_fontes_avaliacao(novo):
            raise ValueError("Metricas ou hashes das fontes da avaliacao v1 divergentes.")
        resultado["comparacoes"].append({"arquivo": "artefatos/avaliacao-v1/relatorio_avaliacao.json",
            "metodo": "JSON integral apos normalizar somente prefixos locais nas chaves de fontes_sha256"})
        opcoes_pdf = ["--pdf"] if incluir_pdf else []
        executar("arquivo", "scripts/gerar_relatorio.py", "--saida", "reproduzidos/documentos", *opcoes_pdf)
        produtos = ["previsao.txt", "relatorio.md", "artefatos/entrega-v2/evidencias.json"]
        if incluir_pdf:
            produtos.append("relatorio.pdf")
        for nome in produtos:
            if (RAIZ / nome).read_bytes() != (copia / "reproduzidos/documentos" / nome).read_bytes():
                raise ValueError(f"Documento divergente: {nome}")
            resultado["comparacoes"].append({"arquivo": nome, "metodo": "byte_a_byte", "sha256": originais[nome]})
        if incluir_testes:
            executar("modulo", "unittest", "discover", "-s", "tests", "-q")
        for nome, digest in originais.items():
            if hash_bytes((RAIZ / nome).read_bytes()) != digest:
                raise ValueError(f"Fonte mudou durante a verificacao: {nome}")
    resultado.update(estado="aprovado", fontes_preservadas=True,
                     duracao_segundos=round(time.monotonic() - inicio, 3))
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--testes", action="store_true")
    parser.add_argument("--registro", type=Path, help="Salvar o resultado da verificacao em novo arquivo JSON.")
    args = parser.parse_args()
    if args.registro is not None and args.registro.exists():
        parser.error("O registro ja existe; use um caminho novo para preservar o historico.")
    try:
        resultado = verificar(incluir_pdf=args.pdf, incluir_testes=args.testes)
        if args.registro is not None:
            args.registro.parent.mkdir(parents=True, exist_ok=True)
            with args.registro.open("x", encoding="utf-8", newline="\n") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
                f.write("\n")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as erro:
        print(str(erro), file=sys.stderr)
        return 1
    print(json.dumps({"estado": resultado["estado"], "passos": len(resultado["passos"]),
        "comparacoes": len(resultado["comparacoes"]), "chamadas_api": 0}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
