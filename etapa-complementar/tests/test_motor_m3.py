"""Testes somente sintéticos do ranking M3 e de suas fronteiras de dados."""

from copy import deepcopy
import ast
import inspect
import json
import math
import unittest

from classificacao_experimentos import motor
from classificacao_experimentos.entradas import hash_texto
from classificacao_local import classificador as lexical


def taxonomia():
    registros = [
        {
            "tema_id": "raiz", "parent_id": "", "nivel": "0", "status": "active",
            "titulo": "Catálogo", "caminho": "Catálogo", "descricao": "",
        },
        {
            "tema_id": "alfa", "parent_id": "raiz", "nivel": "1", "status": "active",
            "titulo": "Flores jardim", "caminho": "Catálogo > Flores jardim",
            "descricao": "Sementes e pétalas amarelas.",
        },
        {
            "tema_id": "beta", "parent_id": "raiz", "nivel": "1", "status": "active",
            "titulo": "Planetas foguetes", "caminho": "Catálogo > Planetas foguetes",
            "descricao": "Estrelas e espaço.",
        },
        {
            "tema_id": "gama", "parent_id": "raiz", "nivel": "1", "status": "inactive",
            "titulo": "Flores jardim", "caminho": "Catálogo > Flores jardim",
            "descricao": "Sementes e pétalas amarelas.",
        },
    ]
    return {"registros": registros, "por_id": {t["tema_id"]: t for t in registros}}


def questao(identificador, texto="Flores jardim", **outros):
    return {
        "id": identificador, "enunciado": texto, "comando": "",
        "alternativas": {}, **outros,
    }


def rotulo(identificador, tema="alfa", extras=None, fora=False):
    return {
        "id": identificador, "tema_central_id": "" if fora else tema,
        "extras_ids": extras or [], "fora_da_taxonomia": fora,
    }


def cache_sintetico(temas, questoes, vetores=None):
    vetores = vetores or {}
    return {
        "sha256": "a" * 64,
        "dimensoes": 2,
        "temas": {
            tema_id: {
                "texto_sha256": hash_texto("tema", tema),
                "vetor": vetores.get(tema_id, [1.0, 0.0] if tema_id == "alfa" else [0.0, 1.0]),
            }
            for tema_id, tema in temas["por_id"].items()
            if tema["status"] == "active" and int(tema["nivel"]) > 0
        },
        "questoes": {
            q["id"]: {
                "texto_sha256": hash_texto("questao", q),
                "vetor": vetores.get(q["id"], [1.0, 0.0]),
            }
            for q in questoes
        },
    }


def config(modo="hibrido", **outros):
    return {
        "modo": modo,
        "peso_exemplos": 0.0,
        "peso_leis": 0.0,
        "vizinhos": "lexicais",
        "rrf_k": 20,
        "peso_semantico": 0.5,
        "lexical": lexical.CONFIG_PADRAO.copy(),
        **outros,
    }


class TestMotorM3(unittest.TestCase):
    def test_semantico_puro_usa_somente_cosseno_de_catalogo(self):
        temas, consulta = taxonomia(), questao("nova")
        cache = cache_sintetico(temas, [consulta], {"nova": [0.6, 0.8]})
        modelo = motor.treinar([], [], temas, config("semantico"), cache)
        resultado = motor.predizer(modelo, consulta, cache)
        self.assertEqual(resultado["tema_sugerido_id"], "beta")
        self.assertAlmostEqual(resultado["score"], 0.8)
        self.assertAlmostEqual(resultado["margem"], 0.2)
        self.assertEqual(resultado["vizinhos"], [])
        self.assertEqual(resultado["quantidade_vizinhos"], 0)
        for candidato in resultado["top_candidatos"]:
            self.assertEqual(candidato["score"], candidato["similaridade_semantica"])
            self.assertEqual(candidato["apoio_exemplos"], 0)
        self.assertNotIn("confianca", resultado)
        self.assertNotIn("decisao", resultado)

    def test_rrf_usa_ranks_de_catalogo_e_desempate_estavel(self):
        temas, consulta = taxonomia(), questao("nova")
        cache = cache_sintetico(temas, [consulta], {"nova": [0.0, 1.0]})
        modelo = motor.treinar([], [], temas, config(), cache)
        resultado = motor.predizer(modelo, consulta, cache)
        por_id = {c["tema_id"]: c for c in resultado["top_candidatos"]}
        self.assertEqual(por_id["alfa"]["rank_lexical"], 1)
        self.assertEqual(por_id["beta"]["rank_lexical"], 2)
        self.assertEqual(por_id["alfa"]["rank_semantico"], 2)
        self.assertEqual(por_id["beta"]["rank_semantico"], 1)
        self.assertAlmostEqual(por_id["alfa"]["score"], 0.5 + 0.5 * 21 / 22)
        self.assertEqual(por_id["alfa"]["score"], por_id["beta"]["score"])
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")
        self.assertEqual(resultado["margem"], 0)

    def test_rank_lexical_nao_usa_apoio_dos_exemplos(self):
        temas = taxonomia()
        treino, consulta = questao("treino"), questao("nova")
        cache = cache_sintetico(temas, [treino, consulta])
        receita = config(lexical={
            **lexical.CONFIG_PADRAO, "peso_catalogo": 0.0, "peso_exemplos": 1.0,
        })
        modelo = motor.treinar([treino], [rotulo("treino", "beta")], temas, receita, cache)
        resultado = motor.predizer(modelo, consulta, cache)
        por_id = {c["tema_id"]: c for c in resultado["top_candidatos"]}
        self.assertEqual(por_id["alfa"]["rank_lexical"], 1)
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")

    def test_baseline_lexical_preserva_exatamente_resultado_m2(self):
        temas, consulta = taxonomia(), questao("nova")
        treino = questao("treino")
        cache = cache_sintetico(temas, [treino, consulta])
        receita = config("lexical", peso_exemplos=0.3)
        modelo = motor.treinar([treino], [rotulo("treino")], temas, receita, cache)
        esperado = lexical.predizer(modelo["lexical"], consulta, top_k=1)
        resultado = motor.predizer(modelo, consulta, cache, top_k=1)
        for campo, valor in esperado.items():
            self.assertEqual(resultado[campo], valor)
        self.assertEqual(resultado["quantidade_vizinhos"], 1)
        self.assertEqual(modelo["referencias_cache"], {"temas": {}, "questoes_treino": {}})

    def test_vizinhos_semanticos_ponderam_central_extras_e_fora(self):
        temas = taxonomia()
        treino = [questao("a", "Flores"), questao("b", "Planetas")]
        consulta = questao("nova")
        cache = cache_sintetico(temas, treino + [consulta])
        receita = config(peso_exemplos=0.3, vizinhos="semanticos")
        modelo = motor.treinar(
            treino, [rotulo("a", extras=["beta"]), rotulo("b", fora=True)],
            temas, receita, cache,
        )
        resultado = motor.predizer(modelo, consulta, cache)
        por_id = {c["tema_id"]: c for c in resultado["top_candidatos"]}
        self.assertEqual(por_id["alfa"]["apoio_exemplos"], 0.5)
        self.assertEqual(por_id["beta"]["apoio_exemplos"], 0.25)
        self.assertEqual(resultado["apoio_fora"], 0.5)
        self.assertEqual(resultado["quantidade_vizinhos"], 2)
        self.assertEqual(resultado["similaridade_maxima_vizinho"], 1.0)
        self.assertEqual(resultado["soma_similaridades_quadradas"], 2.0)
        self.assertAlmostEqual(
            por_id["alfa"]["score"], 0.7 * por_id["alfa"]["score_catalogo"] + 0.15,
        )

    def test_apoio_fraco_normalizado_e_exposto_sem_ocultar_magnitude(self):
        temas = taxonomia()
        treino, consulta = questao("treino"), questao("nova")
        cache = cache_sintetico(
            temas, [treino, consulta], {"treino": [0.001, math.sqrt(1 - 0.001 ** 2)]},
        )
        modelo = motor.treinar(
            [treino], [rotulo("treino")], temas,
            config(peso_exemplos=0.3, vizinhos="semanticos"), cache,
        )
        resultado = motor.predizer(modelo, consulta, cache)
        self.assertEqual(resultado["top_candidatos"][0]["apoio_exemplos"], 1)
        self.assertAlmostEqual(resultado["similaridade_maxima_vizinho"], 0.001)
        self.assertAlmostEqual(resultado["soma_similaridades_quadradas"], 0.000001)

    def test_vizinho_negativo_nao_contribui_e_apenas_tres_positivos(self):
        temas = taxonomia()
        treino = [questao(str(i), "texto " + str(i)) for i in range(5)]
        consulta = questao("nova")
        cache = cache_sintetico(temas, treino + [consulta], {"4": [-1.0, 0.0]})
        modelo = motor.treinar(
            treino, [rotulo(str(i)) for i in range(5)], temas,
            config(peso_exemplos=0.3, vizinhos="semanticos"), cache,
        )
        resultado = motor.predizer(modelo, consulta, cache)
        self.assertEqual(resultado["quantidade_vizinhos"], 3)
        self.assertNotIn("4", [v["id"] for v in resultado["vizinhos"]])

    def test_ablacao_sem_exemplos_nao_muda_score_com_rotulo(self):
        temas, treino, consulta = taxonomia(), questao("treino"), questao("nova")
        cache = cache_sintetico(temas, [treino, consulta])
        resultados = []
        for label in ("alfa", "beta"):
            modelo = motor.treinar(
                [treino], [rotulo("treino", label)], temas,
                config(vizinhos="semanticos"), cache,
            )
            resultado = motor.predizer(modelo, consulta, cache)
            resultados.append([(c["tema_id"], c["score"]) for c in resultado["top_candidatos"]])
        self.assertEqual(*resultados)

    def test_peso_legal_usa_exatamente_jaccard_do_m2(self):
        temas, consulta = taxonomia(), questao("nova", "art. 7 da Lei 12.345/2020")
        temas["por_id"]["alfa"]["descricao"] = "art. 7 da Lei 12.345/2020"
        temas["por_id"]["beta"]["descricao"] = "art. 9 da Lei 12.345/2020"
        cache = cache_sintetico(temas, [consulta])
        modelo = motor.treinar([], [], temas, config(peso_leis=0.1), cache)
        resultado = motor.predizer(modelo, consulta, cache)
        por_id = {c["tema_id"]: c for c in resultado["top_candidatos"]}
        self.assertEqual(por_id["alfa"]["evidencia_leis"], 1.0)
        self.assertAlmostEqual(por_id["beta"]["evidencia_leis"], 1 / 3)
        for candidato in resultado["top_candidatos"]:
            self.assertAlmostEqual(
                candidato["score"],
                0.9 * candidato["score_catalogo"] + 0.1 * candidato["evidencia_leis"],
            )

    def test_cache_pode_conter_reserva_mas_modelo_vincula_apenas_treino(self):
        temas = taxonomia()
        treino, reserva, consulta = questao("treino"), questao("reserva"), questao("nova")
        cache = cache_sintetico(temas, [treino, reserva, consulta])
        modelo = motor.treinar([treino], [rotulo("treino")], temas, config(), cache)
        self.assertEqual(set(modelo["referencias_cache"]["questoes_treino"]), {"treino"})
        self.assertEqual([q["id"] for q in modelo["lexical"]["treino"]], ["treino"])
        # A ausência de uma entrada que o modelo não usa não interfere no ranking.
        antes = motor.predizer(modelo, consulta, cache)
        del cache["questoes"]["reserva"]
        self.assertEqual(antes, motor.predizer(modelo, consulta, cache))
        with self.assertRaisesRegex(ValueError, "Ressubstituição"):
            motor.predizer(modelo, treino, cache)

    def test_cache_hash_ausente_trocado_e_dimensao_divergente_falham(self):
        temas, consulta = taxonomia(), questao("nova")
        cache = cache_sintetico(temas, [consulta])
        modelo = motor.treinar([], [], temas, config(), cache)
        for campo, valor in (("sha256", ""), ("sha256", "b" * 64), ("dimensoes", 3)):
            alterado = deepcopy(cache)
            alterado[campo] = valor
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                motor.predizer(modelo, consulta, alterado)
        sem_hash = deepcopy(cache)
        del sem_hash["sha256"]
        with self.assertRaises(ValueError):
            motor.treinar([], [], temas, config(), sem_hash)

    def test_cache_recusa_texto_incorreto_e_vetor_alterado_ou_invalido(self):
        temas, treino, consulta = taxonomia(), questao("treino"), questao("nova")
        cache = cache_sintetico(temas, [treino, consulta])
        modelo = motor.treinar([treino], [rotulo("treino")], temas, config(), cache)
        for grupo, identificador in (("questoes", "treino"), ("temas", "alfa")):
            alterado = deepcopy(cache)
            alterado[grupo][identificador]["vetor"] = [0.0, 1.0]
            with self.subTest(grupo=grupo), self.assertRaisesRegex(ValueError, "divergente"):
                motor.predizer(modelo, consulta, alterado)
        for valor in ([0.0, 0.0], [1.0], [math.nan, 0.0], [True, 0.0], ["1", 0]):
            alterado = deepcopy(cache)
            alterado["questoes"]["nova"]["vetor"] = valor
            with self.subTest(vetor=valor), self.assertRaises(ValueError):
                motor.predizer(modelo, consulta, alterado)
        for alvo in ("nova", "treino"):
            alterado = deepcopy(cache)
            alterado["questoes"][alvo]["texto_sha256"] = "b" * 64
            with self.subTest(alvo=alvo), self.assertRaisesRegex(ValueError, "Texto"):
                motor.predizer(modelo, consulta, alterado)
        with self.assertRaisesRegex(ValueError, "Texto"):
            motor.predizer(modelo, questao("nova", "Texto diferente"), cache)
        del cache["questoes"]["nova"]
        with self.assertRaisesRegex(ValueError, "Texto"):
            motor.predizer(modelo, consulta, cache)

    def test_cossenos_negativos_sao_zero_e_rrf_nao_inventa_evidencia(self):
        temas, consulta = taxonomia(), questao("nova", "xilofone desconhecido")
        cache = cache_sintetico(temas, [consulta], {"nova": [-0.6, -0.8]})
        for modo in ("semantico", "hibrido"):
            modelo = motor.treinar([], [], temas, config(modo), cache)
            resultado = motor.predizer(modelo, consulta, cache)
            with self.subTest(modo=modo):
                self.assertTrue(resultado["sem_evidencia"])
                self.assertEqual(resultado["tema_sugerido_id"], "alfa")
                self.assertTrue(all(
                    c["similaridade_semantica"] == 0 for c in resultado["top_candidatos"]
                ))

    def test_roundtrip_ordem_de_entrada_e_metadados_nao_mudam_resultado(self):
        temas = taxonomia()
        treino = [questao("a", "Flores"), questao("b", "Planetas")]
        labels = [rotulo("a"), rotulo("b", "beta")]
        consulta = questao("nova")
        cache = cache_sintetico(temas, treino + [consulta])
        receita = config(peso_exemplos=0.3, vizinhos="semanticos")
        modelo = motor.treinar(treino, labels, temas, receita, cache)
        antes = deepcopy((modelo, cache, treino, labels, temas))
        reversa = deepcopy(temas)
        reversa["por_id"] = dict(reversed(list(reversa["por_id"].items())))
        self.assertEqual(
            modelo, motor.treinar(treino[::-1], labels[::-1], reversa, receita, cache),
        )
        resultado = motor.predizer(modelo, consulta, cache)
        roundtrip = json.loads(json.dumps(modelo, sort_keys=True, ensure_ascii=False))
        self.assertEqual(resultado, motor.predizer(roundtrip, consulta, cache))
        outra = {
            **consulta, "id": "outro", "disciplina_origem": "metadadoinventado",
            "assunto_origem": "Planetas", "coorte": "reservada",
        }
        outro_cache = deepcopy(cache)
        outro_cache["questoes"]["outro"] = deepcopy(cache["questoes"]["nova"])
        alterado = motor.predizer(modelo, outra, outro_cache)
        alterado["id"] = resultado["id"]
        self.assertEqual(resultado, alterado)
        self.assertEqual((modelo, cache, treino, labels, temas), antes)

    def test_empate_dos_vizinhos_independe_do_id_de_treino(self):
        temas, consulta = taxonomia(), questao("nova", "texto igual")
        scores = []
        for ids in (["a", "b", "c", "d"], ["d", "c", "b", "a"]):
            treino = [questao(i, "texto igual") for i in ids]
            labels = [rotulo(i, "alfa" if n < 2 else "beta") for n, i in enumerate(ids)]
            cache = cache_sintetico(temas, treino + [consulta])
            modelo = motor.treinar(
                treino, labels, temas,
                config(peso_exemplos=0.3, vizinhos="semanticos"), cache,
            )
            resultado = motor.predizer(modelo, consulta, cache)
            resultado.pop("vizinhos")
            scores.append(resultado)
        self.assertEqual(*scores)

    def test_modelo_corrompido_e_config_invalida_falham(self):
        temas, consulta = taxonomia(), questao("nova")
        cache = cache_sintetico(temas, [consulta])
        for receita in (
            config(modo="inexistente"), config(peso_exemplos=True),
            config(peso_exemplos=math.nan), config(peso_semantico=2),
            config(peso_leis=0.8, peso_exemplos=0.3), config(rrf_k=0),
            config("semantico", peso_exemplos=0.3),
            config("lexical", peso_exemplos=0.0),
            config("lexical", peso_exemplos=0.3, vizinhos="semanticos"),
            config(vizinhos="todos"), config(desconhecido=True),
        ):
            with self.subTest(config=receita), self.assertRaises(ValueError):
                motor.treinar([], [], temas, receita, cache)
        modelo = motor.treinar([], [], temas, config(), cache)
        for campo, valor in (("schema", "v0"), ("cache_sha256", "x"), ("dimensoes", False)):
            alterado = deepcopy(modelo)
            alterado[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                motor.predizer(alterado, consulta, cache)
        alterado = deepcopy(modelo)
        del alterado["referencias_cache"]["temas"]["alfa"]
        with self.assertRaises(ValueError):
            motor.predizer(alterado, consulta, cache)
        # A predição continua recusando corrupção profunda do M2 mesmo ao
        # delegar essa validação exclusivamente ao motor lexical.
        alterado = deepcopy(modelo)
        alterado["lexical"]["idf"]["termo_invalido"] = -1
        with self.assertRaisesRegex(ValueError, "IDF"):
            motor.predizer(alterado, consulta, cache)
        alterado = deepcopy(modelo)
        alterado["lexical"]["catalogo"] = [None]
        with self.assertRaises(ValueError):
            motor.predizer(alterado, consulta, cache)
        for top_k in (0, True, 1.5):
            with self.assertRaises(ValueError):
                motor.predizer(modelo, consulta, cache, top_k)

    def test_motor_importa_apenas_stdlib_e_modulos_locais(self):
        arvore = ast.parse(inspect.getsource(motor))
        imports = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in no.names)
            elif isinstance(no, ast.ImportFrom) and no.level == 0:
                imports.add(no.module.split(".")[0])
        self.assertLessEqual(
            imports, {"__future__", "hashlib", "json", "math", "classificacao_local"},
        )


if __name__ == "__main__":
    unittest.main()
