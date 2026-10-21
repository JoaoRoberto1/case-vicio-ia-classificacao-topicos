"""Reproduz M1 e M4 em cópia temporária, sem ambiente ou modelos de preparação.

Uso (na etapa-complementar):
    python -B -S scripts/verificar_entrega.py
    python -B -S scripts/verificar_entrega.py --evidencia tmp/nova-reproducao.json

A cópia por lista permitida não é um clone Git nem uma máquina virtual. O
interpretador instalado e sua biblioteca padrão são reutilizados. Os vetores
versionados são insumos: não se executa o encoder para reproduzi-los aqui.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import subprocess
import sys
import tempfile
import time
import uuid


PACOTES = (
    "classificacao_topicos", "classificacao_local",
    "classificacao_experimentos", "classificacao_decisao",
)
FIXOS = (
    "README-do-case.md", "case-ia-classificacao-de-topicos (2).pdf",
    "anexos/LEIA-ME.md", "anexos/questoes.jsonl", "anexos/temas.csv",
    "anexos/folha_verdade.csv", "anexos/entrega_modelo.csv",
    "requirements-preparacao.txt", "requirements-preparacao.lock.txt",
    "config/fontes_oficiais.json", "config/protocolo_avaliacao.json",
    "config/reuso_codigo.json", "config/modulo2/experimento_lexical.json",
    "config/modulo2/protocolo_desenvolvimento.json",
    "config/modulo3/embeddings.json", "config/modulo3/experimento.json",
    "config/modulo3/fontes.json", "config/modulo4/fontes.json",
    "config/modulo4/protocolo.json", "publicacao.csv", "previsao.txt",
    "scripts/verificar_entrega.py",
)
PRODUTOS = {
    "preparacao": (
        "questoes_preparadas.jsonl", "temas_preparados.json",
        "rotulos_referencia.jsonl", "particoes.json", "diagnostico.json",
        "manifesto.json",
    ),
    "lexical-v1": (
        "metricas_desenvolvimento.json", "modelo_lexical.json",
        "modelo_lexical_leis.json", "predicoes_desenvolvimento.jsonl",
        "protocolo.json", "sugestoes_avaliacao.jsonl", "manifesto.json",
    ),
    "embeddings-e5-v1": ("vetores.json", "manifesto.json"),
    "melhorias-v1": (
        "metricas_desenvolvimento.json", "modelo_selecionado.json",
        "predicoes_desenvolvimento.jsonl", "protocolo.json",
        "receita_congelada.json", "sugestoes_avaliacao.jsonl", "manifesto.json",
    ),
    "calibracao-v1": (
        "calibrador.json", "politica.json", "metricas_desenvolvimento.json",
        "predicoes_calibradas.jsonl", "congelamento.json", "manifesto.json",
    ),
    "embeddings-e5-m4-v1": ("vetores.json", "manifesto.json"),
    "reserva-v1": (
        "predicoes_reserva.jsonl", "metricas_reserva.json", "manifesto.json",
    ),
    "decisoes-v1": (
        "publicacao.csv", "previsao.txt", "previsao.json", "decisoes.jsonl",
        "modelo_final.json", "manifesto.json",
    ),
}
MARCADOR = "AMBIENTE_M5="
# -S desabilita site; -E ignora PYTHONPATH/PYTHONHOME/PYTHONSTARTUP; o ambiente
# herdado também é substituído. O guard M4 protege M1 antes de seus imports.
BOOTSTRAP = """import json, runpy, sys
from classificacao_decisao.__main__ import _bloquear_operacoes, main as main_decisao
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
print('AMBIENTE_M5=' + json.dumps(ambiente, sort_keys=True), flush=True)
modulo = sys.argv[1]
sys.argv = [modulo, 'verificar']
if modulo == 'classificacao_decisao':
    raise SystemExit(main_decisao())
runpy.run_module(modulo, run_name='__main__')
"""


def _json(valor: object) -> bytes:
    return (json.dumps(valor, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _link(caminho: Path) -> bool:
    """Recusa symlinks e qualquer reparse point Windows, inclusive junctions."""
    if caminho.is_symlink():
        return True
    if caminho.exists():
        atributos = getattr(caminho.lstat(), "st_file_attributes", 0)
        return bool(atributos & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))
    return False


def caminho_local(raiz: Path, relativo: str, *, arquivo: bool = True) -> Path:
    partes = PurePosixPath(relativo)
    if (not relativo or "\\" in relativo or ":" in relativo
            or partes.is_absolute() or any(p in {".", ".."} for p in relativo.split("/"))):
        raise ValueError("Caminho deve ser relativo e não pode escapar da raiz.")
    caminho = raiz
    if _link(caminho):
        raise ValueError("Raiz não pode ser link ou junction.")
    for parte in partes.parts:
        caminho = caminho / parte
        if _link(caminho):
            raise ValueError(f"Link ou junction não permitido: {relativo}")
    if not caminho.resolve().is_relative_to(raiz.resolve()):
        raise ValueError("Caminho escapa da raiz.")
    if arquivo and not caminho.is_file():
        raise ValueError(f"Arquivo necessário ausente: {relativo}")
    return caminho


def listar_arquivos(raiz: Path) -> list[str]:
    nomes = set(FIXOS)
    for pacote in PACOTES:
        diretorio = caminho_local(raiz, pacote, arquivo=False)
        fontes = list(diretorio.glob("*.py"))
        if not fontes:
            raise ValueError(f"Pacote sem código: {pacote}")
        nomes.update(p.relative_to(raiz).as_posix() for p in fontes)
    for diretorio, arquivos in PRODUTOS.items():
        nomes.update(f"artefatos/{diretorio}/{n}" for n in arquivos)
    for nome in nomes:
        caminho_local(raiz, nome)
    return sorted(nomes)


def inventario(raiz: Path, nomes: list[str]) -> dict:
    registros = {}
    for nome in nomes:
        conteudo = caminho_local(raiz, nome).read_bytes()
        registros[nome] = {"sha256": hashlib.sha256(conteudo).hexdigest(),
                           "bytes": len(conteudo)}
    return registros


def materializar(raiz: Path, destino: Path, registros: dict) -> None:
    if destino.exists() or _link(destino):
        raise ValueError("A cópia temporária exige um destino novo.")
    destino.mkdir()
    for nome, registro in registros.items():
        conteudo = caminho_local(raiz, nome).read_bytes()
        if (hashlib.sha256(conteudo).hexdigest() != registro["sha256"]
                or len(conteudo) != registro["bytes"]):
            raise ValueError(f"Fonte mudou durante a cópia: {nome}")
        arquivo = caminho_local(destino, nome, arquivo=False)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with arquivo.open("xb") as saida:
            saida.write(conteudo)
    conferir_copia(destino, registros)


def conferir_copia(destino: Path, registros: dict) -> None:
    encontrados = set()
    for p in destino.rglob("*"):
        if _link(p):
            raise ValueError("A cópia contém link ou junction.")
        if p.is_file():
            encontrados.add(p.relative_to(destino).as_posix())
    if encontrados != set(registros) or inventario(destino, sorted(encontrados)) != registros:
        raise ValueError("A cópia diverge do inventário original.")


def ambiente_limpo(temporario: Path, herdado: dict | None = None) -> dict:
    origem = os.environ if herdado is None else herdado
    # Somente diretórios essenciais do Windows, sem chaves, proxies ou PATH.
    ambiente = {k: v for k, v in origem.items()
                if k.upper() in {"SYSTEMROOT", "WINDIR"}}
    ambiente.update({
        "TEMP": str(temporario), "TMP": str(temporario),
        "HOME": str(temporario), "USERPROFILE": str(temporario),
    })
    return ambiente


def executar_comando(raiz: Path, modulo: str, ambiente: dict,
                     *, timeout: float = 1800) -> dict:
    if modulo not in {"classificacao_topicos", "classificacao_decisao"}:
        raise ValueError("Comando fora da lista permitida.")
    python = getattr(sys, "_base_executable", sys.executable) or sys.executable
    comando = [python, "-B", "-S", "-E", "-X", "utf8", "-c", BOOTSTRAP, modulo]
    inicio = time.perf_counter()
    try:
        resultado = subprocess.run(
            comando, cwd=raiz, env=ambiente, capture_output=True, text=True,
            encoding="utf-8", errors="strict", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as erro:
        raise RuntimeError(f"Verificação excedeu {timeout:g} segundos: {modulo}") from erro
    if resultado.returncode != 0:
        raise RuntimeError(
            f"Verificação falhou ({resultado.returncode}): {modulo}\n{resultado.stderr}"
        )
    linhas = resultado.stdout.splitlines()
    if not linhas or not linhas[0].startswith(MARCADOR):
        raise ValueError("Subprocesso não comprovou o isolamento.")
    isolamento = json.loads(linhas[0][len(MARCADOR):])
    if (set(isolamento) != {
            "no_site", "ignore_environment", "dont_write_bytecode",
            "site_packages_no_path", "rede_env_encoder_pesos_bloqueados"}
            or any(v is not True for v in isolamento.values())):
        raise ValueError("Isolamento do subprocesso inválido.")
    corpo = "\n".join(linhas[1:])
    resumo = json.loads(corpo if modulo == "classificacao_topicos" else linhas[-1])
    if modulo == "classificacao_topicos":
        if resumo.get("status") != "ok" or resumo.get("operacao") != "verificar":
            raise ValueError("M1 não confirmou a verificação.")
    elif (resumo.get("comando") != "verificar"
          or resumo.get("produtos_reconstruidos_identicos") != 15
          or resumo.get("entregas_raiz_identicas") != 2):
        raise ValueError("M4 não confirmou todos os produtos.")
    return {
        "modulo": modulo, "argumentos_python": comando[1:7],
        "bootstrap_sha256": hashlib.sha256(BOOTSTRAP.encode()).hexdigest(),
        "operacao": "verificar", "exit_code": resultado.returncode,
        "segundos": round(time.perf_counter() - inicio, 3),
        "isolamento": isolamento, "resumo": resumo,
        "stdout": resultado.stdout, "stderr": resultado.stderr,
    }


def destino_evidencia(raiz: Path, relativo: str) -> Path:
    caminho = caminho_local(raiz, relativo, arquivo=False)
    partes = PurePosixPath(relativo).parts
    permitido = (len(partes) >= 2 and partes[0] == "tmp") or (
        len(partes) == 3 and partes[:2] == ("artefatos", "checkpoints"))
    if not permitido or caminho.suffix != ".json":
        raise ValueError("Use artefatos/checkpoints/nome.json ou tmp/nome.json.")
    if caminho.exists():
        raise ValueError("Evidência já existe; preserve-a e escolha outro --evidencia.")
    return caminho


def verificar(raiz: Path, evidencia: str) -> dict:
    raiz = raiz.absolute()
    saida = destino_evidencia(raiz, evidencia)
    inicio = time.perf_counter()
    inicio_utc = datetime.now(timezone.utc).isoformat()
    nomes = listar_arquivos(raiz)
    fontes = inventario(raiz, nomes)
    with tempfile.TemporaryDirectory(prefix="vicio-m5-") as temporario:
        base = Path(temporario)
        copia = base / "etapa-complementar"
        ambiente_dir = base / "ambiente"
        ambiente_dir.mkdir()
        materializar(raiz, copia, fontes)
        ambiente = ambiente_limpo(ambiente_dir)
        resultados = []
        for modulo in ("classificacao_topicos", "classificacao_decisao"):
            print(f"Verificando {modulo} na cópia temporária...", flush=True)
            resultados.append(executar_comando(copia, modulo, ambiente))
        conferir_copia(copia, fontes)
    if listar_arquivos(raiz) != nomes or inventario(raiz, nomes) != fontes:
        raise ValueError("Fontes originais mudaram durante a reprodução.")
    documento = {
        "schema": "reproducao_entrega_m5_v1", "status": "aprovado",
        "inicio_utc": inicio_utc, "segundos": round(time.perf_counter() - inicio, 3),
        "ambiente": {"python": platform.python_version(),
                     "implementacao": platform.python_implementation(),
                     "sistema": platform.system(), "arquitetura": platform.machine()},
        "materializacao": "Cópia temporária por lista permitida; não é clone Git ou VM.",
        "limites": [
            "Reutiliza o interpretador instalado e sua biblioteca padrão.",
            "Recebe caches numéricos versionados; não reproduz os embeddings.",
            "M2/M3 têm hashes conferidos; seus experimentos não são refeitos aqui.",
            "Não valida documentos editoriais, PDF, acesso remoto ou estado do Git.",
            "Reproduzir a reserva não constitui nova avaliação estatística independente.",
        ],
        "arquivos_copiados": len(fontes), "bytes_copiados": sum(r["bytes"] for r in fontes.values()),
        "fontes_sha256_e_bytes": fontes, "fontes_originais_preservadas": True,
        "copia_final_identica": True, "execucoes": resultados,
        "produtos_m1_reconstruidos_identicos": len(PRODUTOS["preparacao"]),
        "produtos_m4_reconstruidos_identicos": 15,
        "exportacoes_raiz_identicas": 2,
        "dependencias_instaladas": 0, "encoder_executado": False,
        "rede_env_encoder_pesos_bloqueados": True,
        "credenciais_ambiente_herdadas": False,
    }
    saida = destino_evidencia(raiz, evidencia)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("xb") as arquivo:
        arquivo.write(_json(documento))
    return {k: documento[k] for k in (
        "status", "segundos", "arquivos_copiados", "bytes_copiados",
        "produtos_m1_reconstruidos_identicos", "produtos_m4_reconstruidos_identicos",
        "exportacoes_raiz_identicas", "fontes_originais_preservadas",
    )}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidencia", help=(
        "Novo JSON em artefatos/checkpoints/ ou tmp/. Sem esta opção, cria um "
        "arquivo único em tmp/ para preservar a evidência versionada."))
    argumentos = parser.parse_args()
    raiz = Path(__file__).absolute().parent.parent
    evidencia = argumentos.evidencia or f"tmp/reproducao-modulo5-{uuid.uuid4().hex}.json"
    try:
        resultado = verificar(raiz, evidencia)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as erro:
        parser.exit(1, f"Erro: {erro}\n")
    print(json.dumps({**resultado, "evidencia": evidencia}, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
