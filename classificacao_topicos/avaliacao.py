"""Avaliação offline do tema central, condicional a referências provisórias de IA.

O censo do desenvolvimento e a amostra aleatória restante conservam seus pesos.
A incerteza da referência não é estimada e os resultados não são oficiais.
"""

from __future__ import annotations

from collections import Counter
import csv
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import tempfile

from .estatistica import estimar_precisao
from .execucao import _hash_bytes, _json, _ler, _validar_saida


_CATEGORIAS = ("exata", "pai_filho_direto", "divergencia", "inconclusivo")
_PRODUTOS = {"comparacao_auditoria.csv", "relatorio_avaliacao.json"}
_CAMPOS_REVISAO = {
    "id", "temas_centrais_aceitaveis", "sem_tema", "situacao", "justificativa",
    "limitacoes", "tipo_referencia", "responsavel",
}
_CAMPOS_CSV = (
    "id", "estrato", "decisao", "tema_central_id", "caminho_central",
    "extras_ids", "referencia_temas_centrais_aceitaveis", "referencia_caminhos",
    "referencia_sem_tema", "referencia_situacao", "comparacao_central",
    "detalhe_comparacao", "referencia_ids_correspondentes", "acerto_condicional",
    "justificativa", "limitacoes", "tipo_referencia", "responsavel",
)


def _ancestrais(temas: dict) -> dict[str, list[str]]:
    """Reconstrói relações pelos pais, sem confiar em ancestrais pré-calculados."""
    if not isinstance(temas, dict) or not temas:
        raise ValueError("A taxonomia deve conter temas identificados.")
    for identificador, tema in temas.items():
        if (not isinstance(identificador, str) or not identificador.strip()
                or identificador != identificador.strip() or not isinstance(tema, dict)
                or tema.get("tema_id") != identificador
                or not isinstance(tema.get("parent_id"), str)
                or not isinstance(tema.get("status"), str)
                or tema["status"] not in {"active", "inactive"}):
            raise ValueError("Esquema inválido na taxonomia preparada.")
    resultado = {}
    for identificador in temas:
        cadeia, vistos, atual = [], {identificador}, temas[identificador]["parent_id"]
        while atual:
            if atual not in temas or atual in vistos:
                raise ValueError("A taxonomia contém pai ausente ou ciclo.")
            vistos.add(atual)
            cadeia.append(atual)
            atual = temas[atual]["parent_id"]
        nivel = temas[identificador].get("nivel")
        if type(nivel) not in {str, int} or nivel not in {str(len(cadeia)), len(cadeia)} or len(cadeia) > 2:
            raise ValueError("Nível de tema incompatível com a hierarquia preparada.")
        resultado[identificador] = cadeia
    return resultado


def _carregar_revisoes(caminho: Path, ids: set[str], temas: dict) -> tuple[dict, dict]:
    if caminho.is_symlink():
        raise ValueError("A origem das revisões não pode ser um link simbólico.")
    arquivos = sorted(caminho.glob("*.jsonl")) if caminho.is_dir() else [caminho]
    if not arquivos:
        raise ValueError("Nenhum arquivo JSONL de revisão foi localizado.")
    revisoes, hashes = {}, {}
    for arquivo in arquivos:
        conteudo = _ler(arquivo)
        hashes[arquivo] = _hash_bytes(conteudo)
        try:
            linhas = conteudo.decode("utf-8-sig").split("\n")
        except UnicodeDecodeError:
            raise ValueError("As revisões devem estar codificadas em UTF-8.") from None
        for linha in linhas:
            if not linha.strip():
                continue
            revisao = _json(linha)
            if not isinstance(revisao, dict) or set(revisao) != _CAMPOS_REVISAO:
                raise ValueError("Revisão com campos ausentes ou inesperados.")
            identificador = revisao["id"]
            if not isinstance(identificador, str) or identificador not in ids:
                raise ValueError("Revisão contém ID fora da seleção congelada da auditoria.")
            if identificador in revisoes:
                raise ValueError("Revisão duplicada para uma questão da auditoria.")
            if not isinstance(revisao["situacao"], str) or revisao["situacao"] not in {"provisorio", "inconclusivo"}:
                raise ValueError("Situação da revisão deve ser provisorio ou inconclusivo.")
            sem_tema = revisao["sem_tema"]
            if sem_tema is not None and type(sem_tema) is not bool:
                raise ValueError("sem_tema da revisão deve ser booleano ou null.")
            for campo in ("justificativa", "responsavel"):
                if not isinstance(revisao[campo], str) or not revisao[campo].strip():
                    raise ValueError(f"A revisão exige {campo} textual não vazio.")
            if not isinstance(revisao["limitacoes"], str):
                raise ValueError("Limitações da revisão devem ser texto.")
            if revisao["tipo_referencia"] != "IA_sem_especialista":
                raise ValueError("O tipo de referência deve ser IA_sem_especialista.")
            centrais = revisao["temas_centrais_aceitaveis"]
            if (not isinstance(centrais, list)
                    or any(not isinstance(t, str) or not t.strip() or t != t.strip() for t in centrais)
                    or len(centrais) != len(set(centrais))):
                raise ValueError("Temas centrais aceitáveis devem ser IDs únicos não vazios.")
            if any(t not in temas or temas[t]["status"] != "active" for t in centrais):
                raise ValueError("A revisão contém tema inexistente ou inativo.")
            if sem_tema is True and centrais:
                raise ValueError("Referência sem tema não pode indicar temas centrais aceitáveis.")
            if revisao["situacao"] == "provisorio" and (sem_tema is None or (sem_tema is False and not centrais)):
                raise ValueError("Referência provisória deve afirmar ausência de tema ou indicar temas aceitáveis.")
            revisoes[identificador] = revisao
    if set(revisoes) != ids:
        raise ValueError("As revisões devem cobrir todos e somente os IDs selecionados na auditoria.")
    return revisoes, hashes


def _comparar(central: str, revisao: dict, temas: dict, ancestrais: dict) -> tuple[str, str, list[str]]:
    if revisao["situacao"] == "inconclusivo" or revisao["sem_tema"] is None:
        return "inconclusivo", "referencia_inconclusiva", []
    if revisao["sem_tema"]:
        return "divergencia", "referencia_sem_tema", []
    aceitaveis = revisao["temas_centrais_aceitaveis"]
    if central in aceitaveis:
        return "exata", "mesmo_id", [central]
    diretos = [t for t in aceitaveis
               if temas[central]["parent_id"] == t or temas[t]["parent_id"] == central]
    if diretos:
        return "pai_filho_direto", "relacao_imediata_no_mesmo_ramo", diretos
    distantes = [t for t in aceitaveis if t in ancestrais[central] or central in ancestrais[t]]
    if distantes:
        return "divergencia", "ancestralidade_distante", distantes
    irmaos = [t for t in aceitaveis
              if temas[central]["parent_id"] and temas[t]["parent_id"] == temas[central]["parent_id"]]
    if irmaos:
        return "divergencia", "temas_irmaos", irmaos
    return "divergencia", "ramos_distintos", []


def _caminho(identificador: str, temas: dict) -> str:
    tema = temas[identificador]
    return tema.get("caminho_calculado", tema.get("caminho", identificador))


def _texto_json(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False, allow_nan=False)


def avaliar_auditoria(preparacao: Path, auditoria: Path, decisoes: Path,
                      revisoes: Path, saida: Path) -> dict:
    """Compara referências cegas com a população de publicados já congelada.

    ``revisoes`` aceita um JSONL ou uma pasta de arquivos JSONL independentes.
    Todos os selecionados precisam ter referência; inconclusivos são mantidos.
    O relatório aplica apenas identidade ou parentesco imediato ao tema central.
    Não altera decisões, não avalia extras e não gera a previsão final.
    """
    from .auditoria import _carregar_auditoria

    preparacao, auditoria = Path(preparacao).resolve(), Path(auditoria).resolve()
    decisoes, revisoes = Path(decisoes).absolute(), Path(revisoes).absolute()
    manifesto, temas, questoes, por_decisao, hashes = _carregar_auditoria(preparacao, auditoria, decisoes)
    ancestrais = _ancestrais(temas)
    saida = _validar_saida(Path(saida), piloto=auditoria, preparacao=preparacao,
                           raiz=Path(__file__).resolve().parents[1])
    for entrada in (decisoes, revisoes):
        resolvida = entrada.resolve()
        if (saida == resolvida or saida in resolvida.parents
                or (entrada.is_dir() and resolvida in saida.parents)):
            raise ValueError("A avaliação deve ter saída separada das decisões e revisões.")
    selecionados = manifesto["ids"]
    referencias, hashes_revisoes = _carregar_revisoes(revisoes, set(selecionados), temas)
    hashes = {**hashes, **hashes_revisoes}
    for fonte in hashes:
        if saida == fonte.resolve() or saida in fonte.resolve().parents:
            raise ValueError("A saída não pode conter uma fonte da avaliação.")

    linhas, estratos = [], {}
    for nome in ("desenvolvimento", "restante"):
        estrato = manifesto["estratos"][nome]
        linhas_estrato = []
        for identificador in estrato["selecionados_ids"]:
            decisao, revisao = por_decisao[identificador], referencias[identificador]
            central = decisao["tema_central_id"]
            if decisao["decisao"] != "publicar" or central not in temas or temas[central]["status"] != "active":
                raise ValueError("A auditoria de precisão deve conter somente publicados com tema ativo.")
            categoria, detalhe, correspondentes = _comparar(central, revisao, temas, ancestrais)
            acerto = None if categoria == "inconclusivo" else categoria in {"exata", "pai_filho_direto"}
            linha = {
                "id": identificador, "estrato": nome, "decisao": decisao["decisao"],
                "tema_central_id": central, "caminho_central": _caminho(central, temas),
                "extras_ids": _texto_json(decisao["extras_ids"]),
                "referencia_temas_centrais_aceitaveis": _texto_json(revisao["temas_centrais_aceitaveis"]),
                "referencia_caminhos": _texto_json([_caminho(t, temas) for t in revisao["temas_centrais_aceitaveis"]]),
                "referencia_sem_tema": revisao["sem_tema"], "referencia_situacao": revisao["situacao"],
                "comparacao_central": categoria, "detalhe_comparacao": detalhe,
                "referencia_ids_correspondentes": _texto_json(correspondentes), "acerto_condicional": acerto,
                **{campo: revisao[campo] for campo in ("justificativa", "limitacoes", "tipo_referencia", "responsavel")},
            }
            linhas_estrato.append(linha)
        contagens = Counter(linha["comparacao_central"] for linha in linhas_estrato)
        estratos[nome] = {
            "N": estrato["N"], "n": estrato["n"], "metodo": estrato["metodo"],
            "comparacao_central": {c: contagens[c] for c in _CATEGORIAS},
            "acertos": contagens["exata"] + contagens["pai_filho_direto"],
            "erros": contagens["divergencia"], "inconclusivos": contagens["inconclusivo"],
            "selecionados_ids": estrato["selecionados_ids"],
        }
        linhas.extend(linhas_estrato)
    d, r = estratos["desenvolvimento"], estratos["restante"]
    if d["n"] != d["N"]:
        raise ValueError("O estrato de desenvolvimento deve ser revisado integralmente.")
    if [linha["id"] for linha in linhas] != selecionados:
        raise ValueError("A ordem da seleção diverge dos estratos congelados.")
    precisao = estimar_precisao(d["N"], d["erros"], d["inconclusivos"],
                               r["N"], r["n"], r["erros"], r["inconclusivos"],
                               nivel=manifesto["nivel_intervalo"])
    publicadas = sum(item["decisao"] == "publicar" for item in por_decisao.values())
    if publicadas != d["N"] + r["N"]:
        raise ValueError("Os estratos não cobrem a população de publicados congelada.")
    cobertura = Fraction(publicadas, len(questoes)) if questoes else None
    contagens = Counter(linha["comparacao_central"] for linha in linhas)
    relatorio = {
        "schema_version": 1, "procedimento": "avaliacao-auditoria-v1",
        "tipo_referencia": "IA_sem_especialista", "total_questoes": len(questoes),
        "total_publicadas": publicadas, "total_revisadas": len(linhas),
        "comparacao_central": {c: contagens[c] for c in _CATEGORIAS},
        "ids_por_comparacao": {c: [l["id"] for l in linhas if l["comparacao_central"] == c] for c in _CATEGORIAS},
        "detalhes_comparacao": dict(sorted(Counter(l["detalhe_comparacao"] for l in linhas).items())),
        "estratos": estratos, "precisao_condicional": precisao,
        "cobertura": {
            "publicadas": publicadas, "total_questoes": len(questoes),
            "observada": float(cobertura) if cobertura is not None else None,
            "observada_exata": str(cobertura) if cobertura is not None else None,
            "intervalo": [float(cobertura), float(cobertura)] if cobertura is not None else None,
            "tipo": "contagem_da_populacao_observada", "inferencia_futura": False,
            "explicacao": "A cobertura é uma contagem conhecida desta população congelada; o intervalo degenerado não estima cobertura futura.",
        },
        "fontes_sha256": {str(p): h for p, h in sorted(hashes.items(), key=lambda par: str(par[0]))},
        "limites": [
            "Referência provisória produzida por IA, sem especialista; concordância condicional não é precisão oficial.",
            "São aceitos somente o mesmo ID ou uma relação imediata pai/filho no mesmo ramo; irmãos e ancestrais distantes são divergências.",
            "O indicador considera apenas o tema central; não avalia a qualidade dos extras, decisões revisar ou decisões fora.",
            "Uma referência provisória sem tema conta como erro contra uma decisão publicar.",
            "Referências inconclusivas permanecem inconclusivas mesmo quando coincidem com a decisão; não são descartadas do denominador.",
            "O cenário principal conservador conta inconclusivos como erros; o cenário otimista conta-os como acertos.",
            "Os intervalos incluem somente incerteza amostral, condicionada à referência, à seleção aleatória e à política congelada; não incluem erros da referência.",
            "O desenvolvimento é um censo próprio; sua proporção não é extrapolada para o restante. A avaliação não autoriza alteração da política ou da amostra retroativamente.",
        ],
    }
    arquivo_csv = io.StringIO(newline="")
    gravador = csv.DictWriter(arquivo_csv, fieldnames=_CAMPOS_CSV, lineterminator="\n")
    gravador.writeheader()
    gravador.writerows(linhas)
    csv_bytes = arquivo_csv.getvalue().encode("utf-8-sig")
    relatorio["produtos_sha256"] = {"comparacao_auditoria.csv": _hash_bytes(csv_bytes)}
    produtos = {"comparacao_auditoria.csv": csv_bytes,
                "relatorio_avaliacao.json": (json.dumps(relatorio, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")}
    for fonte, esperado in hashes.items():
        if _hash_bytes(_ler(fonte)) != esperado:
            raise ValueError("Uma fonte mudou durante a avaliação; execute novamente.")
    if saida.exists() and any(p.name not in _PRODUTOS or p.is_symlink() or not p.is_file() for p in saida.iterdir()):
        raise ValueError("A saída da avaliação contém arquivos incompatíveis.")
    saida.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".avaliacao-", dir=saida) as temporaria:
        pasta = Path(temporaria)
        for nome, conteudo in produtos.items():
            (pasta / nome).write_bytes(conteudo)
        (saida / "relatorio_avaliacao.json").unlink(missing_ok=True)
        for nome in produtos:
            os.replace(pasta / nome, saida / nome)
    return relatorio
