"""Preparação determinística dos dados, sem modelos ou alterações nas fontes."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from .taxonomia import carregar_taxonomia, exportar_arvore
from .texto import analisar_texto


CAMPOS_QUESTAO = {
    "id", "enunciado_html", "comando", "alternativas",
    "disciplina_origem", "assunto_origem",
}


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def carregar_questoes(caminho: Path) -> list[dict]:
    """Leia todas as linhas e recuse dados incompletos ou IDs repetidos."""
    registros: list[dict] = []
    ids: set[str] = set()
    def objeto_sem_duplicatas(pares: list[tuple]) -> dict:
        objeto: dict = {}
        for chave, valor in pares:
            if chave in objeto:
                raise ValueError(f"Chave JSON duplicada: {chave!r}.")
            objeto[chave] = valor
        return objeto

    # A iteração física não divide U+2028/U+0085 dentro de strings JSON.
    with caminho.open(encoding="utf-8-sig") as arquivo:
        linhas = list(arquivo)
    for numero, linha in enumerate(linhas, 1):
        if not linha.strip():
            raise ValueError(f"Linha {numero} vazia em {caminho.name}.")
        try:
            registro = json.loads(linha, object_pairs_hook=objeto_sem_duplicatas)
        except json.JSONDecodeError as erro:
            raise ValueError(f"JSON inválido em {caminho.name}, linha {numero}.") from erro
        if not isinstance(registro, dict) or set(registro) != CAMPOS_QUESTAO:
            raise ValueError(f"Campos inesperados em {caminho.name}, linha {numero}.")
        for campo in CAMPOS_QUESTAO - {"alternativas"}:
            if not isinstance(registro[campo], str):
                raise ValueError(f"Campo {campo} deve ser texto na linha {numero}.")
        identificador = registro["id"]
        if not identificador.strip() or identificador != identificador.strip() or identificador in ids:
            raise ValueError(f"ID vazio, com espaços ou duplicado na linha {numero}: {identificador!r}.")
        alternativas = registro["alternativas"]
        if not isinstance(alternativas, dict) or len(alternativas) < 2:
            raise ValueError(f"Questão {identificador}: esperadas pelo menos duas alternativas.")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str)
               for k, v in alternativas.items()):
            raise ValueError(f"Questão {identificador}: alternativas devem mapear rótulos para textos.")
        ids.add(identificador)
        registros.append(registro)
    if not registros:
        raise ValueError(f"Nenhuma questão em {caminho.name}.")
    return registros


def preparar_questao(original: dict, numero_linha: int) -> dict:
    campos = {
        "enunciado": analisar_texto(original["enunciado_html"]),
        "comando": analisar_texto(original["comando"]),
    }
    alternativas = {rotulo: analisar_texto(texto)
                    for rotulo, texto in original["alternativas"].items()}
    avisos: list[str] = []
    for campo, resultado in campos.items():
        avisos.extend(f"{campo}:{aviso}" for aviso in resultado["avisos"])
        if not resultado["texto"]:
            avisos.append(f"{campo}:vazio_apos_preparacao")
    for rotulo, resultado in alternativas.items():
        avisos.extend(f"alternativa_{rotulo}:{aviso}" for aviso in resultado["avisos"])
        if not resultado["texto"]:
            avisos.append(f"alternativa_{rotulo}:vazia_apos_preparacao")
    for campo in ("disciplina_origem", "assunto_origem"):
        if not original[campo].strip():
            avisos.append(f"{campo}:vazio")
    enunciado = campos["enunciado"]["texto"]
    comando = campos["comando"]["texto"]
    # Texto curto é apenas um sinal estrutural; nunca determina fora/revisar.
    if len(enunciado) < 80:
        avisos.append("enunciado:curto_conferir_comando_e_alternativas")
    textos_alternativas = {rotulo: item["texto"] for rotulo, item in alternativas.items()}
    texto_completo = (
        f"ENUNCIADO\n{enunciado}\n\nCOMANDO\n{comando}\n\nALTERNATIVAS\n"
        + "\n".join(f"{rotulo}) {texto}" for rotulo, texto in textos_alternativas.items())
    )
    resultados = [*campos.values(), *alternativas.values()]
    canonico = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "id": original["id"],
        "enunciado": enunciado,
        "comando": comando,
        "alternativas": textos_alternativas,
        "texto_completo": texto_completo,
        "disciplina_origem": original["disciplina_origem"],
        "assunto_origem": original["assunto_origem"],
        "referencia_origem": {
            "arquivo": "questoes.jsonl", "linha": numero_linha,
            "sha256_registro_canonico": hashlib.sha256(canonico.encode("utf-8")).hexdigest(),
        },
        "caracteres_brutos": sum(r["caracteres_brutos"] for r in resultados),
        "caracteres_limpos": sum(r["caracteres_limpos"] for r in resultados),
        "avisos": sorted(set(avisos)),
    }


def _json_texto(objeto: object) -> str:
    return json.dumps(objeto, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _gravar(caminho: Path, conteudo: str) -> None:
    caminho.write_text(conteudo, encoding="utf-8", newline="\n")


def executar_preparacao(entrada: Path, saida: Path) -> dict:
    entrada, saida = entrada.resolve(), saida.resolve()
    if saida == entrada or saida in entrada.parents:
        raise ValueError("A saída deve ser uma pasta distinta da raiz dos materiais.")
    for nome in (".git", "contexto_local", "classificacao_topicos", "tests", "docs", "prompts"):
        protegido = (entrada / nome).resolve()
        if saida == protegido or protegido in saida.parents:
            raise ValueError(f"A pasta {nome} é protegida e não pode receber os produtos.")
    fontes = [entrada / nome for nome in ("questoes.jsonl", "temas.csv", "LEIA-ME.md", "entrega_modelo.csv")]
    for caminho in fontes:
        if not caminho.is_file():
            raise ValueError(f"Arquivo de entrada ausente: {caminho.name}.")
    hashes_antes = {p.name: sha256(p) for p in fontes}
    originais = carregar_questoes(entrada / "questoes.jsonl")
    taxonomia = carregar_taxonomia(entrada / "temas.csv")
    questoes = [preparar_questao(q, i) for i, q in enumerate(originais, 1)]
    aviso_contagem = Counter(aviso for q in questoes for aviso in q["avisos"])
    diagnostico = {
        "schema_version": 1,
        "questoes": {
            "total": len(questoes),
            "ids_duplicados": 0,
            "comando_vazio_original": sum(not q["comando"].strip() for q in originais),
            "comando_vazio_preparado": sum(not q["comando"] for q in questoes),
            "assunto_origem_vazio": sum(not q["assunto_origem"].strip() for q in originais),
            "disciplina_origem_vazia": sum(not q["disciplina_origem"].strip() for q in originais),
            "quantidade_alternativas": dict(sorted(Counter(str(len(q["alternativas"])) for q in originais).items())),
            "disciplinas_origem": dict(sorted(Counter(q["disciplina_origem"] for q in originais).items())),
            "caracteres_brutos": sum(q["caracteres_brutos"] for q in questoes),
            "caracteres_limpos": sum(q["caracteres_limpos"] for q in questoes),
            "questoes_com_avisos": sum(bool(q["avisos"]) for q in questoes),
            "avisos": dict(sorted(aviso_contagem.items())),
        },
        "taxonomia": taxonomia["diagnostico"],
        "limites": [
            "Verificação estrutural; não mede precisão de classificação.",
            "Origem e descrições foram preservadas, sem validação jurídica.",
            "Avisos de preparação não atribuem publicar, revisar ou fora.",
        ],
    }
    produtos = {
        "questoes_preparadas.jsonl": "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questoes),
        "temas_preparados.json": _json_texto(taxonomia["registros"]),
        "diagnostico.json": _json_texto(diagnostico),
        "arvore_temas.md": exportar_arvore(taxonomia),
    }
    arquivo_csv = io.StringIO(newline="")
    writer = csv.writer(arquivo_csv, lineterminator="\n")
    writer.writerow(["id", "aviso"])
    writer.writerows((q["id"], aviso) for q in questoes for aviso in q["avisos"])
    produtos["avisos_questoes.csv"] = arquivo_csv.getvalue()
    hashes_depois = {p.name: sha256(p) for p in fontes}
    if hashes_antes != hashes_depois:
        raise ValueError("Os materiais de entrada mudaram durante a preparação; descarte esta execução.")
    manifesto = {
        "schema_version": 1,
        "procedimento": "preparacao-v1",
        "fontes_sha256": hashes_antes,
        "produtos_sha256": {nome: hashlib.sha256(produtos[nome].encode("utf-8")).hexdigest()
                            for nome in sorted(produtos)},
        "fontes_preservadas": True,
    }
    produtos["manifesto.json"] = _json_texto(manifesto)
    for nome in produtos:
        destino = saida / nome
        if destino.is_symlink() or (destino.exists() and not destino.is_file()):
            raise ValueError(f"Destino de produto não é um arquivo comum: {nome}.")
        if destino.resolve() in fontes:
            raise ValueError(f"Destino de produto aponta para uma fonte: {nome}.")
    saida.mkdir(parents=True, exist_ok=True)
    # Preparar todos os produtos antes da publicação. O manifesto é o marcador
    # de conclusão e só aparece depois de todas as substituições atômicas.
    with tempfile.TemporaryDirectory(prefix=".preparacao-", dir=saida) as pasta_temporaria:
        temporaria = Path(pasta_temporaria).resolve()
        if not temporaria.is_relative_to(saida):
            raise ValueError("Pasta temporária fora do destino validado.")
        for nome, conteudo in produtos.items():
            _gravar(temporaria / nome, conteudo)
        if hashes_antes != {p.name: sha256(p) for p in fontes}:
            raise ValueError("Os materiais mudaram antes da gravação; nenhuma saída foi publicada.")
        (saida / "manifesto.json").unlink(missing_ok=True)
        for nome in produtos:
            os.replace(temporaria / nome, saida / nome)
    return diagnostico
