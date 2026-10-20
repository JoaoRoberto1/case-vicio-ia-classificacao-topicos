"""Ranking local por catálogo, exemplos humanos e citações extraídas por regras.

Nenhuma função chama modelos ou rede. Os escores são medidas de recuperação,
não probabilidades de acerto e não decisões de publicação. Nem a ausência de
evidência nem o apoio de vizinhos ``fora`` determinam ``fora`` automaticamente.

Somente títulos/caminhos/descrições do catálogo e questões de TREINO ajustam
o TF-IDF. Metadados de procedência, coorte e IDs nunca compõem o texto. Os IDs
servem ao bloqueio de ressubstituição e à rastreabilidade de vizinhos.
"""

from __future__ import annotations

import hashlib
import math

from .citacoes import extrair_citacoes
from .lexical import ajustar, similaridade, termos_comuns, transformar


SCHEMA = "classificador_lexical_v1"
CONFIG_PADRAO = {
    "peso_catalogo": 0.7,
    "peso_exemplos": 0.3,
    "peso_leis": 0.0,
    "k_vizinhos": 3,
    "peso_enunciado": 2,
    "peso_comando": 2,
    "peso_alternativas": 1,
    "peso_titulo": 3,
    "peso_caminho": 1,
    "peso_descricao": 1,
}
_PESOS_SCORE = ("peso_catalogo", "peso_exemplos", "peso_leis")
_PESOS_QUESTAO = ("peso_enunciado", "peso_comando", "peso_alternativas")
_PESOS_TEMA = ("peso_titulo", "peso_caminho", "peso_descricao")


def validar_config(config: dict) -> dict:
    """Completa os valores padrão e rejeita parâmetros inesperados/inválidos."""
    if not isinstance(config, dict):
        raise ValueError("A configuração deve ser um objeto.")
    desconhecidos = sorted(set(config) - set(CONFIG_PADRAO))
    if desconhecidos:
        raise ValueError(f"Parâmetros desconhecidos: {desconhecidos}.")
    resultado = {**CONFIG_PADRAO, **config}
    for campo in _PESOS_SCORE:
        valor = resultado[campo]
        if (isinstance(valor, bool) or not isinstance(valor, (int, float))
                or not math.isfinite(valor) or not 0 <= valor <= 1):
            raise ValueError(f"{campo} deve ser um número finito entre zero e um.")
        resultado[campo] = float(valor)
    if not math.isclose(
        math.fsum(resultado[campo] for campo in _PESOS_SCORE),
        1.0, abs_tol=1e-12, rel_tol=0.0,
    ):
        raise ValueError("A soma dos pesos de catálogo, exemplos e leis deve ser um.")
    for campo in (*_PESOS_QUESTAO, *_PESOS_TEMA):
        valor = resultado[campo]
        if type(valor) is not int or not 0 <= valor <= 10:
            raise ValueError(f"{campo} deve ser inteiro entre zero e dez.")
    for grupo in (_PESOS_QUESTAO, _PESOS_TEMA):
        if sum(resultado[campo] for campo in grupo) == 0:
            raise ValueError("Ao menos um peso de texto deve ser positivo por grupo.")
    if type(resultado["k_vizinhos"]) is not int or not 1 <= resultado["k_vizinhos"] <= 100:
        raise ValueError("k_vizinhos deve ser inteiro entre um e cem.")
    return resultado


def _id(registro: dict, campo: str = "id") -> str:
    valor = registro.get(campo) if isinstance(registro, dict) else None
    if not isinstance(valor, str) or not valor or valor != valor.strip():
        raise ValueError(f"{campo} deve ser um texto não vazio e sem espaços nas extremidades.")
    return valor


def _texto_questao(questao: dict, config: dict, ponderado: bool = True) -> str:
    _id(questao)
    for campo in ("enunciado", "comando"):
        if not isinstance(questao.get(campo), str):
            raise ValueError(f"O campo preparado {campo} deve ser texto.")
    alternativas = questao.get("alternativas")
    if not isinstance(alternativas, dict) or any(
        not isinstance(chave, str) or not isinstance(valor, str)
        for chave, valor in alternativas.items()
    ):
        raise ValueError("As alternativas devem mapear rótulos textuais para textos.")
    # A posição/identificador da alternativa não é atributo; só os textos entram.
    campos = [
        ("enunciado", questao["enunciado"]),
        ("comando", questao["comando"]),
        ("alternativas", "\n".join(sorted(alternativas.values()))),
    ]
    return "\n".join(
        texto
        for nome, texto in campos
        for _ in range(config[f"peso_{nome}"] if ponderado else 1)
    )


def _texto_tema(tema: dict, config: dict, ponderado: bool = True) -> str:
    for campo in ("titulo", "caminho", "descricao"):
        if not isinstance(tema.get(campo), str):
            raise ValueError(f"O campo {campo} de um tema deve ser texto.")
    return "\n".join(
        tema[campo]
        for campo in ("titulo", "caminho", "descricao")
        for _ in range(config[f"peso_{campo}"] if ponderado else 1)
    )


def _normalizar_rotulo(rotulo: dict, candidatos: set[str]) -> dict:
    identificador = _id(rotulo)
    central = rotulo.get("tema_central_id")
    extras = rotulo.get("extras_ids")
    fora = rotulo.get("fora_da_taxonomia")
    if not isinstance(central, str) or type(fora) is not bool:
        raise ValueError("Rótulo exige tema_central_id textual e fora_da_taxonomia booleano.")
    if not isinstance(extras, list) or any(not isinstance(extra, str) for extra in extras):
        raise ValueError("extras_ids deve ser uma lista de IDs textuais.")
    if len(set(extras)) != len(extras) or central and central in extras:
        raise ValueError("O rótulo contém temas repetidos.")
    if fora:
        if central or extras:
            raise ValueError("Rótulo fora da taxonomia não pode fornecer temas.")
    elif not central or any(tema not in candidatos for tema in [central, *extras]):
        raise ValueError("O rótulo de treino exige temas ativos de nível maior que zero.")
    return {
        "id": identificador,
        "tema_central_id": central,
        "extras_ids": sorted(extras),
        "fora_da_taxonomia": fora,
    }


def _validar_citacoes(citacoes: dict) -> None:
    if not isinstance(citacoes, dict) or set(citacoes) != {"instrumentos", "artigos", "pares"}:
        raise ValueError("Citações devem conter instrumentos, artigos e pares.")
    for valores in citacoes.values():
        if (not isinstance(valores, list)
                or any(not isinstance(valor, str) or not valor for valor in valores)
                or valores != sorted(set(valores))):
            raise ValueError("As citações devem ser listas ordenadas de textos únicos.")


def evidencia_citacoes(consulta: dict, tema: dict) -> tuple[float, dict]:
    """Jaccard de instrumentos e pares produzidos pelo extrator textual.

    Artigos isolados não participam. Um instrumento compartilhado rende algum
    apoio, mas artigos diferentes aumentam a união e reduzem o escore. O nome do
    instrumento e cada par são unidades distintas, sem inferência de pertinência.
    Pares expressam coocorrência sob a regra conservadora do extrator; não
    comprovam vínculo jurídico entre instrumento e artigo.
    """
    conjuntos = []
    comuns = {}
    for campo in ("instrumentos", "pares"):
        esquerda, direita = set(consulta[campo]), set(tema[campo])
        comuns[campo] = sorted(esquerda & direita)
        conjuntos.append((
            {(campo, valor) for valor in esquerda},
            {(campo, valor) for valor in direita},
        ))
    esquerda = conjuntos[0][0] | conjuntos[1][0]
    direita = conjuntos[0][1] | conjuntos[1][1]
    uniao = esquerda | direita
    return (len(esquerda & direita) / len(uniao) if uniao else 0.0), comuns


def treinar(
    questoes_treino: list[dict], rotulos_treino: list[dict],
    taxonomia: dict, config: dict,
) -> dict:
    """Ajusta um ranking usando somente catálogo e exemplos humanos fornecidos."""
    configuracao = validar_config(config)
    if not isinstance(taxonomia, dict) or not isinstance(taxonomia.get("por_id"), dict):
        raise ValueError("Taxonomia deve fornecer por_id.")
    temas = []
    for tema_id, tema in sorted(taxonomia["por_id"].items()):
        if not isinstance(tema, dict) or _id(tema, "tema_id") != tema_id:
            raise ValueError("Índice por_id inconsistente com os IDs dos temas.")
        if tema.get("status") not in {"active", "inactive"}:
            raise ValueError("Status do tema deve ser active ou inactive.")
        nivel = tema.get("nivel")
        if not isinstance(nivel, str) or not nivel.isdecimal():
            raise ValueError("O nível do tema deve ser uma string inteira não negativa.")
        if tema["status"] == "active" and int(nivel) > 0:
            temas.append(tema)
    if not temas:
        raise ValueError("Nenhum tema ativo de nível maior que zero no catálogo.")
    candidatos = {tema["tema_id"] for tema in temas}
    if not isinstance(questoes_treino, list) or not isinstance(rotulos_treino, list):
        raise ValueError("Questões e rótulos de treino devem ser listas.")
    questoes_por_id = {}
    for questao in questoes_treino:
        identificador = _id(questao)
        if identificador in questoes_por_id:
            raise ValueError("ID de questão repetido no treino.")
        questoes_por_id[identificador] = questao
    rotulos_por_id = {}
    for rotulo in rotulos_treino:
        normalizado = _normalizar_rotulo(rotulo, candidatos)
        if normalizado["id"] in rotulos_por_id:
            raise ValueError("ID de rótulo repetido no treino.")
        rotulos_por_id[normalizado["id"]] = normalizado
    if questoes_por_id.keys() != rotulos_por_id.keys():
        raise ValueError("Questões e rótulos de treino devem ter exatamente os mesmos IDs.")
    ids_treino = sorted(questoes_por_id)
    textos_temas = [_texto_tema(tema, configuracao) for tema in temas]
    textos_treino = [
        _texto_questao(questoes_por_id[identificador], configuracao)
        for identificador in ids_treino
    ]
    idf = ajustar(textos_temas + textos_treino)
    catalogo = [
        {
            "tema_id": tema["tema_id"],
            "vetor": transformar(texto, idf),
            "citacoes": extrair_citacoes(_texto_tema(tema, configuracao, ponderado=False)),
        }
        for tema, texto in zip(temas, textos_temas)
    ]
    treino = [
        {
            **rotulos_por_id[identificador],
            "vetor": transformar(texto, idf),
            "assinatura_texto": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        }
        for identificador, texto in zip(ids_treino, textos_treino)
    ]
    modelo = {
        "schema": SCHEMA,
        "config": configuracao,
        "n_documentos_idf": len(textos_temas) + len(textos_treino),
        "idf": idf,
        "catalogo": catalogo,
        "treino": treino,
    }
    validar_modelo(modelo)
    return modelo


def validar_modelo(modelo: dict) -> None:
    """Verifica o contrato de um modelo carregado de JSON, sem estado implícito."""
    if not isinstance(modelo, dict) or set(modelo) != {
        "schema", "config", "n_documentos_idf", "idf", "catalogo", "treino",
    } or modelo["schema"] != SCHEMA:
        raise ValueError("Esquema de modelo lexical inválido.")
    if not isinstance(modelo["config"], dict) or set(modelo["config"]) != set(CONFIG_PADRAO):
        raise ValueError("A configuração serializada deve estar completa.")
    validar_config(modelo["config"])
    idf = modelo["idf"]
    if not isinstance(idf, dict) or any(
        not isinstance(termo, str) or not termo
        or isinstance(valor, bool) or not isinstance(valor, (int, float))
        or not math.isfinite(valor) or valor < 1
        for termo, valor in idf.items()
    ):
        raise ValueError("IDF inválido.")
    catalogo, treino = modelo["catalogo"], modelo["treino"]
    if not isinstance(catalogo, list) or not catalogo or not isinstance(treino, list):
        raise ValueError("Modelo exige catálogo não vazio e lista de treino.")
    if (type(modelo["n_documentos_idf"]) is not int
            or modelo["n_documentos_idf"] != len(catalogo) + len(treino)):
        raise ValueError("Contagem de documentos de ajuste inconsistente.")
    ids_temas, ids_treino = set(), set()
    for item in catalogo:
        if not isinstance(item, dict) or set(item) != {"tema_id", "vetor", "citacoes"}:
            raise ValueError("Registro de catálogo serializado inválido.")
        tema_id = _id(item, "tema_id")
        if tema_id in ids_temas:
            raise ValueError("Tema repetido no catálogo serializado.")
        ids_temas.add(tema_id)
        _validar_citacoes(item["citacoes"])
    for item in treino:
        if not isinstance(item, dict) or set(item) != {
            "id", "tema_central_id", "extras_ids", "fora_da_taxonomia",
            "vetor", "assinatura_texto",
        }:
            raise ValueError("Registro de treino serializado inválido.")
        _normalizar_rotulo(item, ids_temas)
        if item["id"] in ids_treino:
            raise ValueError("Questão repetida no treino serializado.")
        ids_treino.add(item["id"])
        assinatura = item["assinatura_texto"]
        if (not isinstance(assinatura, str) or len(assinatura) != 64
                or any(caractere not in "0123456789abcdef" for caractere in assinatura)):
            raise ValueError("Assinatura de texto inválida.")
    for item in [*catalogo, *treino]:
        vetor = item["vetor"]
        if not isinstance(vetor, dict) or any(
            termo not in idf or isinstance(valor, bool)
            or not isinstance(valor, (int, float))
            or not math.isfinite(valor) or not 0 < valor <= 1
            for termo, valor in vetor.items()
        ):
            raise ValueError("Vetor lexical inválido.")
        if vetor and not math.isclose(
            math.fsum(valor * valor for valor in vetor.values()), 1.0,
            abs_tol=1e-9, rel_tol=0.0,
        ):
            raise ValueError("O vetor lexical não está normalizado em L2.")


def predizer(modelo: dict, questao: dict, top_k: int = 5) -> dict:
    """Retorna ranking e evidências; não publica, não rejeita nem calibra.

    Sem apoio positivo, o primeiro ID de tema ordenado é apenas um preenchimento
    estável. ``sem_evidencia=True`` deve impedir publicação pelo consumidor.
    """
    validar_modelo(modelo)
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k deve ser inteiro positivo.")
    identificador = _id(questao)
    if identificador in {item["id"] for item in modelo["treino"]}:
        raise ValueError("Ressubstituição recusada: a questão já pertence ao treino.")
    config = modelo["config"]
    texto = _texto_questao(questao, config)
    vetor = transformar(texto, modelo["idf"])
    citacoes = extrair_citacoes(_texto_questao(questao, config, ponderado=False))
    vizinhos = []
    for exemplo in modelo["treino"]:
        sim = similaridade(vetor, exemplo["vetor"])
        if sim > 0:
            vizinhos.append((sim, exemplo))
    # Empates não dependem do ID nem da ordem dos dados; a assinatura do texto e
    # o rótulo são usados apenas quando as similaridades são numericamente iguais.
    vizinhos.sort(key=lambda item: (
        -item[0], item[1]["assinatura_texto"], item[1]["fora_da_taxonomia"],
        item[1]["tema_central_id"], tuple(item[1]["extras_ids"]),
    ))
    vizinhos = vizinhos[:config["k_vizinhos"]]
    denominador = math.fsum(sim * sim for sim, _ in vizinhos)
    apoios: dict[str, float] = {}
    apoio_fora = 0.0
    if denominador:
        contribuicoes: dict[str, list[float]] = {}
        fora = []
        for sim, exemplo in vizinhos:
            peso = sim * sim / denominador
            if exemplo["fora_da_taxonomia"]:
                fora.append(peso)
                continue
            contribuicoes.setdefault(exemplo["tema_central_id"], []).append(peso)
            for extra in exemplo["extras_ids"]:
                contribuicoes.setdefault(extra, []).append(0.5 * peso)
        apoios = {
            tema_id: min(1.0, math.fsum(pesos))
            for tema_id, pesos in contribuicoes.items()
        }
        apoio_fora = min(1.0, math.fsum(fora))
    candidatos = []
    for tema in modelo["catalogo"]:
        sim = similaridade(vetor, tema["vetor"])
        apoio = apoios.get(tema["tema_id"], 0.0)
        leis, comuns = evidencia_citacoes(citacoes, tema["citacoes"])
        score = math.fsum([
            config["peso_catalogo"] * sim,
            config["peso_exemplos"] * apoio,
            config["peso_leis"] * leis,
        ])
        candidatos.append({
            "tema_id": tema["tema_id"],
            "score": min(1.0, max(0.0, score)),
            "similaridade_catalogo": sim,
            "apoio_exemplos": apoio,
            "evidencia_leis": leis,
            "termos_comuns": termos_comuns(vetor, tema["vetor"]),
            "citacoes_comuns": comuns,
        })
    candidatos.sort(key=lambda item: (-item["score"], item["tema_id"]))
    melhor = candidatos[0]
    segundo_score = candidatos[1]["score"] if len(candidatos) > 1 else 0.0
    return {
        "id": identificador,
        "tema_sugerido_id": melhor["tema_id"],
        "score": melhor["score"],
        "margem": melhor["score"] - segundo_score,
        "sem_evidencia": melhor["score"] <= 0.0,
        "apoio_fora": apoio_fora,
        "top_candidatos": candidatos[:top_k],
        "vizinhos": [
            {"id": exemplo["id"], "similaridade": sim}
            for sim, exemplo in vizinhos
        ],
    }
