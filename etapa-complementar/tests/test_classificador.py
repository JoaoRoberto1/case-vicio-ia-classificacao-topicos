"""Casos sintéticos: não julgam nem inspecionam questões do case."""

from copy import deepcopy
import json
import math
import unittest

from classificacao_local.classificador import (
    CONFIG_PADRAO, evidencia_citacoes, predizer, treinar, validar_config,
    validar_modelo,
)
from classificacao_local.lexical import ajustar, similaridade, termos, transformar


def taxonomia():
    registros = [
        {
            "tema_id": "raiz", "parent_id": "", "nivel": "0", "status": "active",
            "titulo": "Catálogo", "caminho": "Catálogo", "descricao": "",
        },
        {
            "tema_id": "alfa", "parent_id": "raiz", "nivel": "1", "status": "active",
            "titulo": "Jardim flores", "caminho": "Catálogo > Jardim flores",
            "descricao": "Cultivo de flores amarelas e sementes.",
        },
        {
            "tema_id": "beta", "parent_id": "raiz", "nivel": "1", "status": "active",
            "titulo": "Viagem astral", "caminho": "Catálogo > Viagem astral",
            "descricao": "Planetas foguetes estrelas.",
        },
        {
            "tema_id": "inativo", "parent_id": "raiz", "nivel": "1", "status": "inactive",
            "titulo": "Jardim flores", "caminho": "Catálogo > Jardim flores",
            "descricao": "Cultivo de flores amarelas e sementes.",
        },
    ]
    return {"registros": registros, "por_id": {tema["tema_id"]: tema for tema in registros}}


def questao(identificador, texto, **extras):
    return {
        "id": identificador, "enunciado": texto, "comando": "",
        "alternativas": {}, **extras,
    }


def rotulo(identificador, tema="alfa", extras=None, fora=False):
    return {
        "id": identificador, "tema_central_id": "" if fora else tema,
        "extras_ids": extras or [], "fora_da_taxonomia": fora,
        "disciplina": "sintética",
    }


class TestLexical(unittest.TestCase):
    def test_normalizacao_preserva_negacao_numeros_e_bigramas(self):
        resultado = termos("Não há FLORES no jardim 2026.")
        self.assertIn("nao", resultado)
        self.assertIn("2026", resultado)
        self.assertIn("flores jardim", resultado)
        self.assertNotIn("no", resultado)

    def test_idf_e_tf_exatos(self):
        idf = ajustar(["flor flor", "flor planeta"])
        self.assertEqual(idf["flor"], 1.0)
        self.assertAlmostEqual(idf["planeta"], math.log(3 / 2) + 1)
        vetor = transformar("flor flor planeta", idf)
        self.assertAlmostEqual(
            vetor["flor"] / vetor["planeta"],
            (1 + math.log(2)) / idf["planeta"],
        )
        self.assertAlmostEqual(sum(valor * valor for valor in vetor.values()), 1.0)
        self.assertAlmostEqual(similaridade(vetor, vetor), 1.0)

    def test_consulta_nao_altera_vocabulario(self):
        idf = ajustar(["flores jardins"])
        antes = deepcopy(idf)
        self.assertEqual(transformar("xilofone inedito", idf), {})
        self.assertEqual(idf, antes)

    def test_documentos_vazios_e_consulta_vazia(self):
        idf = ajustar(["", "a o as os"])
        self.assertEqual(idf, {})
        self.assertEqual(transformar("", idf), {})
        self.assertEqual(similaridade({}, {}), 0)


class TestClassificador(unittest.TestCase):
    def test_catalogo_cobre_tema_sem_exemplo_humano(self):
        modelo = treinar(
            [questao("treino", "flores sementes")], [rotulo("treino")],
            taxonomia(), {},
        )
        resultado = predizer(modelo, questao("nova", "planetas foguetes estrelas"))
        self.assertEqual(resultado["tema_sugerido_id"], "beta")
        self.assertFalse(resultado["sem_evidencia"])
        ids = {item["tema_id"] for item in resultado["top_candidatos"]}
        self.assertEqual(ids, {"alfa", "beta"})
        self.assertNotIn("probabilidade", resultado)
        self.assertNotIn("decisao", resultado)

    def test_peso_legal_altera_score_mas_zero_preserva_evidencia(self):
        temas = taxonomia()
        temas["por_id"]["alfa"]["descricao"] = "art. 7 da Lei nº 12.345/2020."
        temas["por_id"]["beta"]["descricao"] = "art. 9 da Lei nº 12.345/2020."
        consulta = questao("consulta", "art. 7 da Lei nº 12.345/2020.")
        legal = treinar([], [], temas, {
            **CONFIG_PADRAO, "peso_catalogo": 0.0, "peso_exemplos": 0.0,
            "peso_leis": 1.0,
        })
        resultado = predizer(legal, consulta)
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")
        self.assertAlmostEqual(resultado["score"], 1.0)
        self.assertAlmostEqual(resultado["top_candidatos"][1]["score"], 1 / 3)
        self.assertTrue(resultado["top_candidatos"][0]["citacoes_comuns"]["pares"])
        sem_peso = treinar([], [], temas, CONFIG_PADRAO)
        auditoria = predizer(sem_peso, consulta)
        self.assertEqual(auditoria["top_candidatos"][0]["evidencia_leis"], 1.0)
        self.assertAlmostEqual(
            auditoria["score"],
            CONFIG_PADRAO["peso_catalogo"]
            * auditoria["top_candidatos"][0]["similaridade_catalogo"],
        )

    def test_vocabulario_fit_nao_contem_teste_metadados_ou_rotulo_caminho(self):
        treino = questao(
            "identificadorinedito", "flores", origem="metadadooculto",
            disciplina_origem="origemsecreta", coorte="coortesecreta",
        )
        label = rotulo("identificadorinedito")
        label["tema_central_caminho"] = "caminhoinventado"
        modelo = treinar([treino], [label], taxonomia(), {})
        antes = deepcopy(modelo)
        predizer(modelo, questao("teste", "vocabularioteste"))
        for palavra in (
            "identificadorinedito", "metadadooculto", "origemsecreta",
            "coortesecreta", "caminhoinventado", "vocabularioteste",
        ):
            self.assertNotIn(palavra, modelo["idf"])
        self.assertEqual(modelo, antes)

    def test_trocar_metadados_id_e_ordem_alternativas_nao_muda_escores(self):
        modelo = treinar([], [], taxonomia(), {})
        base = questao("um", "flores", alternativas={"a": "planetas", "b": "sementes"})
        alterada = {
            **base, "id": "outro", "disciplina_origem": "Viagem astral",
            "assunto_origem": "Viagem astral", "coorte": "recentes",
            "alternativas": {"x": "sementes", "y": "planetas"},
        }
        antes, depois = predizer(modelo, base), predizer(modelo, alterada)
        antes.pop("id")
        depois.pop("id")
        self.assertEqual(antes, depois)

    def test_trocar_ids_de_treino_nao_muda_escores_em_empate(self):
        config = {**CONFIG_PADRAO, "k_vizinhos": 1}
        primeiro = treinar(
            [questao("a", "texto igual"), questao("z", "texto igual")],
            [rotulo("a", "alfa"), rotulo("z", "beta")], taxonomia(), config,
        )
        segundo = treinar(
            [questao("z", "texto igual"), questao("a", "texto igual")],
            [rotulo("z", "alfa"), rotulo("a", "beta")], taxonomia(), config,
        )
        a = predizer(primeiro, questao("consulta", "texto igual"))
        b = predizer(segundo, questao("consulta", "texto igual"))
        a.pop("vizinhos")
        b.pop("vizinhos")
        self.assertEqual(a, b)

    def test_resubstituicao_recusada_mesmo_com_texto_diferente(self):
        modelo = treinar(
            [questao("treino", "flores")], [rotulo("treino")], taxonomia(), {},
        )
        with self.assertRaisesRegex(ValueError, "Ressubstituição"):
            predizer(modelo, questao("treino", "planetas"))

    def test_apoio_central_extra_e_fora(self):
        config = {
            **CONFIG_PADRAO, "peso_catalogo": 0.0, "peso_exemplos": 1.0,
        }
        modelo = treinar(
            [questao("a", "texto comum"), questao("b", "texto comum")],
            [rotulo("a", "alfa", ["beta"]), rotulo("b", fora=True)],
            taxonomia(), config,
        )
        resultado = predizer(modelo, questao("consulta", "texto comum"))
        por_id = {item["tema_id"]: item for item in resultado["top_candidatos"]}
        self.assertAlmostEqual(por_id["alfa"]["apoio_exemplos"], 0.5)
        self.assertAlmostEqual(por_id["beta"]["apoio_exemplos"], 0.25)
        self.assertAlmostEqual(resultado["apoio_fora"], 0.5)
        self.assertNotIn("decisao", resultado)

    def test_so_vizinho_fora_nao_cria_decisao_fora(self):
        modelo = treinar(
            [questao("a", "texto estranho")], [rotulo("a", fora=True)],
            taxonomia(), {},
        )
        resultado = predizer(modelo, questao("consulta", "texto estranho"))
        self.assertEqual(resultado["apoio_fora"], 1.0)
        self.assertTrue(resultado["sem_evidencia"])
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")
        self.assertNotIn("decisao", resultado)

    def test_zero_evidencia_tem_desempate_estavel(self):
        modelo = treinar([], [], taxonomia(), {})
        modelo["catalogo"].reverse()
        resultado = predizer(modelo, questao("consulta", "xilofone"), top_k=1)
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")
        self.assertEqual(resultado["score"], 0)
        self.assertEqual(resultado["margem"], 0)
        self.assertTrue(resultado["sem_evidencia"])
        self.assertEqual(resultado["top_candidatos"][0]["termos_comuns"], [])

    def test_json_roundtrip_e_ordem_entrada(self):
        original = taxonomia()
        questoes = [questao("z", "flores"), questao("a", "planetas")]
        rotulos = [rotulo("z", "alfa"), rotulo("a", "beta")]
        modelo = treinar(questoes, rotulos, original, {})
        reversa = deepcopy(original)
        reversa["por_id"] = dict(reversed(list(reversa["por_id"].items())))
        self.assertEqual(
            modelo, treinar(list(reversed(questoes)), list(reversed(rotulos)), reversa, {}),
        )
        consulta = questao("nova", "flores e planetas")
        resultado = predizer(modelo, consulta)
        reconstruido = json.loads(json.dumps(modelo, ensure_ascii=False, sort_keys=True))
        self.assertEqual(resultado, predizer(reconstruido, consulta))
        self.assertGreaterEqual(resultado["margem"], 0)
        self.assertTrue(all(
            len(item["termos_comuns"]) <= 8 for item in resultado["top_candidatos"]
        ))

    def test_nao_altera_entradas(self):
        entradas = ([questao("a", "flores")], [rotulo("a")], taxonomia(), {})
        antes = deepcopy(entradas)
        modelo = treinar(*entradas)
        self.assertEqual(entradas, antes)
        consulta = questao("nova", "planetas")
        antes_consulta = deepcopy(consulta)
        antes_modelo = deepcopy(modelo)
        predizer(modelo, consulta)
        self.assertEqual(consulta, antes_consulta)
        self.assertEqual(modelo, antes_modelo)

    def test_sem_tema_ativo_falha(self):
        temas = taxonomia()
        for tema in temas["por_id"].values():
            tema["status"] = "inactive"
        with self.assertRaisesRegex(ValueError, "Nenhum tema"):
            treinar([], [], temas, {})

    def test_treino_exige_correspondencia_um_para_um(self):
        testes = [
            ([questao("a", "flor")], []),
            ([], [rotulo("a")]),
            ([questao("a", "flor"), questao("a", "flor")], [rotulo("a")]),
            ([questao("a", "flor")], [rotulo("a"), rotulo("a")]),
        ]
        for questoes, rotulos in testes:
            with self.subTest(questoes=len(questoes), rotulos=len(rotulos)):
                with self.assertRaises(ValueError):
                    treinar(questoes, rotulos, taxonomia(), {})

    def test_rotulos_invalidos_falham(self):
        invalidos = [
            rotulo("a", "raiz"), rotulo("a", "inativo"), rotulo("a", "ausente"),
            rotulo("a", extras=["alfa"]), rotulo("a", extras=["beta", "beta"]),
            {**rotulo("a"), "fora_da_taxonomia": "0"},
            {**rotulo("a"), "extras_ids": "beta"},
            {**rotulo("a", fora=True), "tema_central_id": "alfa"},
        ]
        for label in invalidos:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    treinar([questao("a", "texto")], [label], taxonomia(), {})

    def test_parametros_invalidos_falham(self):
        invalidos = [
            {"desconhecido": 1}, {"peso_catalogo": -0.1},
            {"peso_catalogo": math.nan}, {"peso_catalogo": math.inf},
            {"peso_catalogo": True}, {"peso_catalogo": 0.9},
            {"k_vizinhos": 0}, {"k_vizinhos": 1.5}, {"k_vizinhos": True},
            {"k_vizinhos": 101}, {"peso_comando": -1}, {"peso_titulo": 11},
            {"peso_comando": 1.5},
            {"peso_enunciado": 0, "peso_comando": 0, "peso_alternativas": 0},
            {"peso_titulo": 0, "peso_caminho": 0, "peso_descricao": 0},
        ]
        for config in invalidos:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    validar_config(config)
        modelo = treinar([], [], taxonomia(), {})
        for top_k in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                predizer(modelo, questao("a", "flores"), top_k=top_k)

    def test_modelo_corrompido_falha(self):
        modelo = treinar([], [], taxonomia(), {})
        for campo, valor in (("schema", "v9"), ("n_documentos_idf", 0), ("idf", {"flor": -1})):
            with self.subTest(campo=campo):
                alterado = deepcopy(modelo)
                alterado[campo] = valor
                with self.assertRaises(ValueError):
                    validar_modelo(alterado)
        alterado = deepcopy(modelo)
        alterado["catalogo"][0]["vetor"] = {"inexistente": 1.0}
        with self.assertRaises(ValueError):
            predizer(alterado, questao("a", "flores"))


class TestEvidenciaCitacoes(unittest.TestCase):
    def test_artigo_isolado_nao_pontua(self):
        isolado = {"instrumentos": [], "artigos": ["123"], "pares": []}
        score, comuns = evidencia_citacoes(isolado, isolado)
        self.assertEqual(score, 0.0)
        self.assertEqual(comuns, {"instrumentos": [], "pares": []})

    def test_mesmo_instrumento_artigos_diferentes_reduzem_score(self):
        esquerda = {"instrumentos": ["instrumento:a"], "artigos": ["123"], "pares": ["a:123"]}
        direita = {"instrumentos": ["instrumento:a"], "artigos": ["456"], "pares": ["a:456"]}
        score, comuns = evidencia_citacoes(esquerda, direita)
        self.assertAlmostEqual(score, 1 / 3)
        self.assertEqual(comuns["instrumentos"], ["instrumento:a"])
        self.assertEqual(comuns["pares"], [])
        self.assertEqual(evidencia_citacoes(esquerda, esquerda)[0], 1.0)

    def test_instrumentos_diferentes_nao_pontuam_artigo_igual(self):
        esquerda = {"instrumentos": ["a"], "artigos": ["123"], "pares": ["a:123"]}
        direita = {"instrumentos": ["b"], "artigos": ["123"], "pares": ["b:123"]}
        self.assertEqual(evidencia_citacoes(esquerda, direita)[0], 0.0)


if __name__ == "__main__":
    unittest.main()
