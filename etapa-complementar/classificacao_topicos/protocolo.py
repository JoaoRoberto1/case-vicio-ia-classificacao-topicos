"""Partições reproduzíveis para avaliação futura, sem treinar modelos."""

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import hashlib
import json
import re
import unicodedata


def _inteiro(valor, nome: str, minimo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro maior ou igual a {minimo}.")
    return valor


def _hash(valor) -> str:
    serializado = json.dumps(
        valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _tokens(texto: str) -> tuple[str, ...]:
    normalizado = unicodedata.normalize("NFKC", texto).casefold()
    return tuple(re.findall(r"[^\W_]+", normalizado, flags=re.UNICODE))


def _validar_ids(registros: Sequence[Mapping], nome: str) -> dict:
    por_id = {}
    for registro in registros:
        identificador = registro.get("id")
        if not isinstance(identificador, str) or not identificador.strip():
            raise ValueError(f"{nome}: registro sem ID válido.")
        if identificador in por_id:
            raise ValueError(f"{nome}: ID duplicado {identificador!r}.")
        por_id[identificador] = registro
    return por_id


def _agrupar(questoes: Mapping, config: Mapping) -> list[dict]:
    """Une textos iguais e pares acima do limiar, incluindo transitividade."""
    limiar = config["limiar_jaccard"]
    if (
        isinstance(limiar, bool)
        or not isinstance(limiar, (int, float))
        or not 0 < limiar <= 1
    ):
        raise ValueError("limiar_jaccard deve estar em (0, 1].")
    tamanho = _inteiro(config["tamanho_shingle"], "tamanho_shingle", 1)
    minimo = _inteiro(config["minimo_tokens"], "minimo_tokens", tamanho)

    ids = sorted(questoes)
    pais = list(range(len(ids)))
    textos = []
    conjuntos = []
    canonicos = {}

    def raiz(indice):
        while pais[indice] != indice:
            pais[indice] = pais[pais[indice]]
            indice = pais[indice]
        return indice

    def unir(a, b):
        raiz_a, raiz_b = raiz(a), raiz(b)
        if raiz_a != raiz_b:
            pais[max(raiz_a, raiz_b)] = min(raiz_a, raiz_b)

    for indice, identificador in enumerate(ids):
        texto = questoes[identificador].get("texto_completo")
        if not isinstance(texto, str):
            raise ValueError(f"{identificador}: texto_completo deve ser texto.")
        tokens = _tokens(texto)
        if not tokens:
            raise ValueError(f"{identificador}: texto_completo está vazio.")
        textos.append(tokens)
        if tokens in canonicos:
            unir(indice, canonicos[tokens])
        else:
            canonicos[tokens] = indice
        conjuntos.append(
            frozenset(
                tokens[inicio : inicio + tamanho]
                for inicio in range(len(tokens) - tamanho + 1)
            )
            if len(tokens) >= minimo
            else frozenset()
        )

    for a, shingles_a in enumerate(conjuntos):
        if not shingles_a:
            continue
        for b in range(a + 1, len(ids)):
            shingles_b = conjuntos[b]
            if not shingles_b or raiz(a) == raiz(b):
                continue
            # O tamanho dos conjuntos limita o Jaccard máximo possível.
            if min(len(shingles_a), len(shingles_b)) / max(
                len(shingles_a), len(shingles_b)
            ) < limiar:
                continue
            intersecao = len(shingles_a.intersection(shingles_b))
            uniao = len(shingles_a) + len(shingles_b) - intersecao
            if intersecao / uniao >= limiar:
                unir(a, b)

    membros = defaultdict(list)
    for indice in range(len(ids)):
        membros[raiz(indice)].append(indice)
    grupos = []
    for indices in membros.values():
        conteudos = sorted(set(textos[indice] for indice in indices))
        grupos.append(
            {
                # O identificador do grupo também deriva somente do conteúdo.
                "id": "g-" + _hash(conteudos)[:20],
                "ids": sorted(ids[indice] for indice in indices),
                "tipo": (
                    "isolado"
                    if len(indices) == 1
                    else "exatas"
                    if len(conteudos) == 1
                    else "quase_duplicatas"
                ),
                "textos_distintos": len(conteudos),
            }
        )
    return sorted(grupos, key=lambda grupo: grupo["id"])


def _estrato(rotulo: Mapping) -> str:
    if rotulo["fora_da_taxonomia"]:
        return "fora"
    disciplina = rotulo.get("disciplina")
    if not isinstance(disciplina, str) or not disciplina.strip():
        raise ValueError(f"{rotulo['id']}: rótulo sem disciplina.")
    return disciplina


def _atribuir_dobras(
    grupos: Sequence[Mapping],
    rotulos: Mapping,
    solicitadas: int,
    semente: int,
    escopo: str,
    avisos: list[str],
) -> list[list[str]]:
    """Balanceia grupos inteiros por tamanho e distribuição dos estratos."""
    quantidade = min(solicitadas, len(grupos))
    if quantidade < 2:
        raise ValueError(f"{escopo}: são necessários ao menos dois grupos.")
    if quantidade < solicitadas:
        avisos.append(
            f"{escopo}: dobras reduzidas de {solicitadas} para {quantidade}; "
            "não há grupos suficientes para a quantidade solicitada."
        )

    contagens = {
        grupo["id"]: Counter(
            _estrato(rotulos[identificador])
            for identificador in grupo["rotulados_ids"]
        )
        for grupo in grupos
    }
    totais = Counter()
    grupos_por_estrato = Counter()
    for contagem in contagens.values():
        totais.update(contagem)
        grupos_por_estrato.update(contagem.keys())
    for estrato, quantidade_grupos in sorted(grupos_por_estrato.items()):
        if quantidade_grupos < quantidade:
            avisos.append(
                f"{escopo}: estrato {estrato!r} presente em "
                f"{quantidade_grupos} grupos para {quantidade} dobras; "
                "não é possível representá-lo em todas."
            )

    ordenados = sorted(
        grupos,
        key=lambda grupo: (
            -len(grupo["rotulados_ids"]),
            -sum(
                valor / totais[estrato]
                for estrato, valor in sorted(contagens[grupo["id"]].items())
            ),
            _hash([semente, escopo, grupo["id"]]),
        ),
    )
    dobras = [[] for _ in range(quantidade)]
    estratos_dobras = [Counter() for _ in range(quantidade)]
    total_rotulos = sum(totais.values())

    for grupo in ordenados:
        contagem = contagens[grupo["id"]]
        tamanho = len(grupo["rotulados_ids"])
        vazias = [indice for indice, dobra in enumerate(dobras) if not dobra]
        candidatas = vazias or list(range(quantidade))

        def custo(indice):
            # Incremento da dispersão quadrática normalizada entre dobras.
            dispersao = sum(
                (
                    2 * estratos_dobras[indice][estrato] * valor
                    + valor * valor
                )
                / (totais[estrato] ** 2)
                for estrato, valor in sorted(contagem.items())
            )
            dispersao += (
                2 * len(dobras[indice]) * tamanho + tamanho * tamanho
            ) / (total_rotulos**2)
            return (
                dispersao,
                len(dobras[indice]),
                _hash([semente, escopo, grupo["id"], indice]),
            )

        escolhida = min(candidatas, key=custo)
        dobras[escolhida].extend(grupo["rotulados_ids"])
        estratos_dobras[escolhida].update(contagem)
    return [sorted(dobra) for dobra in dobras]


def construir_particoes(
    questoes: Sequence[Mapping], rotulos: Sequence[Mapping], config: Mapping
) -> dict:
    """Constrói o manifesto de CV aninhada e separa a avaliação oficial.

    A detecção de duplicatas usa apenas o conteúdo, em todas as questões.
    A alocação das dobras usa somente grupos com rótulos conhecidos. Questões
    sem rótulo nunca integram treino/validação. Grupos que misturam conjuntos
    ficam explicitamente registrados para controles de contaminação futuros.
    """
    semente = _inteiro(config["semente"], "semente", 0)
    externas = _inteiro(config["dobras_externas"], "dobras_externas", 2)
    internas = _inteiro(config["dobras_internas"], "dobras_internas", 2)
    questoes_por_id = _validar_ids(questoes, "questões")
    rotulos_por_id = _validar_ids(rotulos, "rótulos")
    ausentes = sorted(set(rotulos_por_id) - set(questoes_por_id))
    if ausentes:
        raise ValueError(f"Rótulos sem questão correspondente: {ausentes}.")
    for identificador, questao in questoes_por_id.items():
        if questao.get("coorte") not in {"historicas", "recentes"}:
            raise ValueError(f"{identificador}: coorte inválida.")
    for identificador, rotulo in rotulos_por_id.items():
        if not isinstance(rotulo.get("fora_da_taxonomia"), bool):
            raise ValueError(f"{identificador}: fora_da_taxonomia deve ser bool.")

    rotulados_ids = sorted(rotulos_por_id)
    avaliacao_ids = sorted(set(questoes_por_id) - set(rotulos_por_id))
    grupos = _agrupar(questoes_por_id, config["duplicatas"])
    avisos = []
    for grupo in grupos:
        grupo["rotulados_ids"] = sorted(
            identificador
            for identificador in grupo["ids"]
            if identificador in rotulos_por_id
        )
        grupo["avaliacao_ids"] = sorted(
            identificador
            for identificador in grupo["ids"]
            if identificador not in rotulos_por_id
        )
        grupo["coortes"] = sorted(
            {questoes_por_id[identificador]["coorte"] for identificador in grupo["ids"]}
        )
        grupo["misto_rotulados_avaliacao"] = bool(
            grupo["rotulados_ids"] and grupo["avaliacao_ids"]
        )
        if grupo["misto_rotulados_avaliacao"]:
            avisos.append(
                f"Grupo {grupo['id']} mistura rótulos conhecidos e avaliação "
                "oficial; controlar sobreposição em análises e artefatos futuros."
            )

    grupos_rotulados = [grupo for grupo in grupos if grupo["rotulados_ids"]]
    testes_externos = _atribuir_dobras(
        grupos_rotulados, rotulos_por_id, externas, semente, "externas", avisos
    )
    folds = []
    conjunto_rotulados = set(rotulados_ids)
    for indice, teste_ids in enumerate(testes_externos):
        treino = conjunto_rotulados - set(teste_ids)
        grupos_treino = [
            grupo
            for grupo in grupos_rotulados
            if set(grupo["rotulados_ids"]).issubset(treino)
        ]
        validacoes_internas = _atribuir_dobras(
            grupos_treino,
            rotulos_por_id,
            internas,
            semente,
            f"externa_{indice + 1}/internas",
            avisos,
        )
        folds.append(
            {
                "indice": indice + 1,
                "treino_ids": sorted(treino),
                "teste_ids": teste_ids,
                "internas": [
                    {
                        "indice": interno + 1,
                        "treino_ids": sorted(treino - set(validacao_ids)),
                        "validacao_ids": validacao_ids,
                    }
                    for interno, validacao_ids in enumerate(validacoes_internas)
                ],
            }
        )

    coortes = {}
    for coorte in ("historicas", "recentes"):
        ids_coorte = {
            identificador
            for identificador, questao in questoes_por_id.items()
            if questao["coorte"] == coorte
        }
        coortes[coorte] = {
            "ids": sorted(ids_coorte),
            "rotulados_ids": sorted(ids_coorte & conjunto_rotulados),
            "avaliacao_ids": sorted(ids_coorte - conjunto_rotulados),
        }
        if ids_coorte and not ids_coorte & conjunto_rotulados:
            avisos.append(
                f"Coorte {coorte!r} sem rótulos conhecidos; as partições não "
                "medem diretamente seu desempenho nem sua calibração."
            )

    return {
        "versao": 1,
        "metodo": "validacao_cruzada_aninhada_agrupada",
        "estratificacao": "aproximada_por_disciplina_e_fora_da_taxonomia",
        "config": {
            "semente": semente,
            "dobras_externas": externas,
            "dobras_internas": internas,
            "duplicatas": dict(config["duplicatas"]),
        },
        "rotulados_ids": rotulados_ids,
        "avaliacao_ids": avaliacao_ids,
        "coortes": coortes,
        "grupos": grupos,
        "folds": folds,
        "avisos": avisos,
    }
