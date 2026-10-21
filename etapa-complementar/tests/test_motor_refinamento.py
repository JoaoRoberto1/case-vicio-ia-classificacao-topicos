"""Contratos do refinamento usando apenas questões e taxonomia sintéticas."""

from copy import deepcopy
import math
import unittest

from classificacao_experimentos.entradas import hash_texto
from classificacao_refinamento.motor import Motor, termos_caracteres, validar_receita


def taxonomia():
    itens = [
        {"tema_id": "raiz_a", "status": "active", "nivel": "0", "titulo": "Natureza",
         "caminho": "Natureza", "descricao": "", "disciplina": "Natureza"},
        {"tema_id": "raiz_b", "status": "active", "nivel": "0", "titulo": "Espaço",
         "caminho": "Espaço", "descricao": "", "disciplina": "Espaço"},
        {"tema_id": "alfa", "status": "active", "nivel": "1", "titulo": "Flor jardim",
         "caminho": "Natureza > Flor jardim", "descricao": "Semente pétala",
         "disciplina": "Natureza"},
        {"tema_id": "beta", "status": "active", "nivel": "1", "titulo": "Planeta foguete",
         "caminho": "Espaço > Planeta foguete", "descricao": "Estrela astrônomo",
         "disciplina": "Espaço"},
        {"tema_id": "inativo", "status": "inactive", "nivel": "1", "titulo": "Flor",
         "caminho": "Natureza > Flor", "descricao": "", "disciplina": "Natureza"},
    ]
    return {"por_id": {t["tema_id"]: t for t in itens}}


def questao(identificador, texto="Flor jardim", **outros):
    return {"id": identificador, "enunciado": texto, "comando": "", "alternativas": {}, **outros}


def rotulo(identificador, central="alfa", fora=False, extras=None):
    return {"id": identificador, "tema_central_id": "" if fora else central,
            "fora_da_taxonomia": fora, "extras_ids": extras or []}


def cache(temas, questoes, vetores=None):
    vetores = vetores or {}
    return {
        "schema": "embeddings_e5_v1", "sha256": "a" * 64, "dimensoes": 2,
        "temas": {
            i: {"texto_sha256": hash_texto("tema", t),
                "vetor": vetores.get(i, [1.0, 0.0] if i == "alfa" else [0.0, 1.0])}
            for i, t in temas["por_id"].items() if t["status"] == "active" and t["nivel"] != "0"
        },
        "questoes": {q["id"]: {"texto_sha256": hash_texto("questao", q),
                                "vetor": vetores.get(q["id"], [1.0, 0.0])}
                     for q in questoes},
    }


def receita(**outros):
    return {"modo": "campos", "peso_char": 0.3, "peso_semantico": 0.5,
            "rrf_k": 5, "peso_prior": 0.0, **outros}


class TestMotorRefinamento(unittest.TestCase):
    def montar(self, treino=None, rotulos=None, consulta=None, vetores=None):
        treino = treino or []
        consulta = consulta or questao("nova")
        temas = taxonomia()
        dados = cache(temas, treino + [consulta], vetores)
        return Motor(treino, rotulos or [], temas, dados), consulta

    def test_ranking_e_contrato_sem_probabilidade_de_acerto(self):
        motor, consulta = self.montar()
        resultado = motor.predizer(consulta, receita())
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")
        self.assertEqual({p["tema_id"] for p in resultado["top_candidatos"]}, {"alfa", "beta"})
        self.assertFalse(resultado["sem_evidencia"])
        self.assertNotIn("confianca", resultado)
        self.assertNotIn("decisao", resultado)
        self.assertGreater(resultado["margem"], 0)

    def test_caracteres_recuperam_flexao_sem_palavra_exata(self):
        motor, consulta = self.montar(consulta=questao("nova", "flores jardins"))
        palavra = motor.predizer(consulta, receita(peso_char=0.0, peso_semantico=0.0))
        caractere = motor.predizer(consulta, receita(peso_semantico=0.0))
        self.assertTrue(palavra["sem_evidencia"])
        self.assertFalse(caractere["sem_evidencia"])
        self.assertEqual(caractere["tema_sugerido_id"], "alfa")
        self.assertGreater(caractere["score"], 0)

    def test_char_normaliza_acentos_e_nao_cruza_tokens(self):
        self.assertEqual(termos_caracteres("FLÔR"), termos_caracteres("flor"))
        self.assertEqual(termos_caracteres("a"), [" a "])
        self.assertNotIn("ab cd", termos_caracteres("ab cd"))
        self.assertIn(" ab ", termos_caracteres("ab cd"))

    def test_corpo_prioritario_a_alternativas_longas(self):
        q = questao("nova", "Flor jardim", alternativas={"a": "Planeta foguete " * 100})
        motor, consulta = self.montar(consulta=q)
        resultado = motor.predizer(consulta, receita(peso_semantico=0.0, peso_char=0.0))
        self.assertEqual(resultado["tema_sugerido_id"], "alfa")

    def test_alternativas_recebem_peso_total_sem_corpo_representavel(self):
        a = questao("a", "", alternativas={"x": "Planeta foguete"})
        b = questao("b", "Planeta foguete")
        temas = taxonomia()
        motor = Motor([], [], temas, cache(temas, [a, b]))
        p = motor.predizer(a, receita(peso_semantico=0.0))
        q = motor.predizer(b, receita(peso_semantico=0.0))
        self.assertEqual(p["score"], q["score"])
        self.assertEqual(p["tema_sugerido_id"], "beta")

    def test_metadados_e_ordem_das_alternativas_nao_sao_atributos(self):
        q = questao("nova", alternativas={"a": "Semente", "b": "Pétala"})
        motor, _ = self.montar(consulta=q)
        esperado = motor.predizer(q, receita(peso_prior=0.15))
        alterada = {**q, "disciplina_origem": "Espaço", "assunto_origem": "foguetes",
                    "coorte": "outra", "alternativas": {"z": "Pétala", "x": "Semente"}}
        self.assertEqual(esperado, motor.predizer(alterada, receita(peso_prior=0.15)))

    def test_consultas_no_cache_nao_ajustam_idf_nem_centroides(self):
        treino = questao("treino", "Semente única")
        q1, q2 = questao("nova", "vocabuloinedito"), questao("nova", "outrovocabuloinedito")
        a, _ = self.montar([treino], [rotulo("treino")], q1)
        b, _ = self.montar([treino], [rotulo("treino")], q2)
        self.assertEqual(a._idf_palavras, b._idf_palavras)
        self.assertEqual(a._idf_char, b._idf_char)
        self.assertEqual(a._centroides, b._centroides)
        self.assertNotIn("vocabuloinedito", a._idf_palavras)

    def test_rotulos_so_alteram_prior_e_nao_recuperacao_de_catalogo(self):
        treino = questao("treino", "Texto distinto para aprendizagem")
        a, q = self.montar([treino], [rotulo("treino", "alfa")])
        b, _ = self.montar([treino], [rotulo("treino", "beta")])
        self.assertEqual(a.predizer(q, receita()), b.predizer(q, receita()))
        pa = a.predizer(q, receita(peso_prior=0.15))["probabilidades_disciplinas"]
        pb = b.predizer(q, receita(peso_prior=0.15))["probabilidades_disciplinas"]
        self.assertGreater(pa["Natureza"], pb["Natureza"])
        self.assertAlmostEqual(sum(pa.values()), 1.0)

    def test_prior_fallback_catalogo_sem_humanos_e_fora_nao_vota(self):
        treino = questao("treino", "Registro sem tema")
        a, q = self.montar([treino], [rotulo("treino", fora=True)])
        resultado = a.predizer(q, receita(peso_prior=0.15))
        self.assertEqual(set(resultado["origem_centroides"].values()), {"catalogo_sem_suporte_humano"})
        self.assertGreater(resultado["probabilidades_disciplinas"]["Natureza"], 0.99)
        self.assertEqual(len(resultado["top_candidatos"]), 2)

    def test_cosseno_negativo_no_prior_softmax_e_finito(self):
        motor, q = self.montar(vetores={"nova": [-1.0, 0.0]})
        resultado = motor.predizer(q, receita(peso_prior=0.15))
        prior = resultado["probabilidades_disciplinas"]
        self.assertGreater(prior["Espaço"], prior["Natureza"])
        self.assertTrue(all(math.isfinite(v) for v in prior.values()))

    def test_estado_independe_de_mutacao_das_entradas(self):
        temas = taxonomia()
        treino, q = questao("treino", "Treino flores singular"), questao("nova")
        rotulos = [rotulo("treino")]
        dados = cache(temas, [treino, q])
        motor = Motor([treino], rotulos, temas, dados)
        esperado = motor.predizer(q, receita(peso_prior=0.15))
        dados["questoes"]["nova"]["vetor"][:] = [0.0, 1.0]
        dados["temas"].clear()
        temas["por_id"].clear()
        treino["enunciado"] = "Alterado"
        rotulos[0]["tema_central_id"] = "beta"
        self.assertEqual(esperado, motor.predizer(q, receita(peso_prior=0.15)))
        esperado["top_candidatos"][0]["score"] = -1
        self.assertGreater(motor.predizer(q, receita())["score"], 0)

    def test_ressubstituicao_por_id_e_texto_normalizado(self):
        treino = questao("treino", "Flôr, Jardim!")
        copia = questao("nova", "FLOR jardim")
        motor, _ = self.montar([treino], [rotulo("treino")], copia)
        for q in (treino, copia):
            with self.subTest(id=q["id"]), self.assertRaisesRegex(ValueError, "Ressubstituição"):
                motor.predizer(q, receita())

    def test_texto_consultado_deve_corresponder_ao_cache(self):
        motor, q = self.montar()
        with self.assertRaisesRegex(ValueError, "divergente"):
            motor.predizer({**q, "enunciado": "Texto modificado"}, receita())
        with self.assertRaisesRegex(ValueError, "ausente"):
            motor.predizer({**q, "id": "nao_cacheado"}, receita())

    def test_cache_adulterado_ou_incompleto_recusado(self):
        temas, q = taxonomia(), questao("nova")
        base = cache(temas, [q])
        casos = []
        for vetor in ([math.nan, 0.0], [True, 0.0], [1.0], [0.0, 0.0], [2.0, 0.0]):
            dado = deepcopy(base)
            dado["questoes"]["nova"]["vetor"] = vetor
            casos.append(dado)
        dado = deepcopy(base)
        dado["temas"]["alfa"]["texto_sha256"] = "b" * 64
        casos.append(dado)
        dado = deepcopy(base)
        del dado["temas"]["beta"]
        casos.append(dado)
        dado = deepcopy(base)
        dado["sha256"] = "nao-assinado"
        casos.append(dado)
        for numero, dado in enumerate(casos):
            with self.subTest(numero=numero), self.assertRaises(ValueError):
                Motor([], [], temas, dado)

    def test_treino_com_rotulos_divergentes_recusado(self):
        q = questao("treino", "Texto de treino")
        temas = taxonomia()
        dados = cache(temas, [q])
        casos = [([], [rotulo("treino")]), ([q], []), ([q, q], [rotulo("treino")]),
                 ([q], [rotulo("treino"), rotulo("treino")]),
                 ([q], [rotulo("treino", "inativo")])]
        for qs, rs in casos:
            with self.subTest(q=len(qs), r=len(rs)), self.assertRaises(ValueError):
                Motor(qs, rs, temas, dados)

    def test_configuracao_fora_da_grade_e_top_k_invalidos(self):
        motor, q = self.montar()
        for alteracao in ({"peso_char": True}, {"peso_semantico": math.nan},
                          {"rrf_k": 7}, {"peso_prior": 0.3}, {"modo": "outro"},
                          {"peso_prior": 0.15, "peso_semantico": 0.0}, {"extra": 1}):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                validar_receita(receita(**alteracao))
        for top_k in (True, 0, -1, 2.5):
            with self.subTest(top_k=top_k), self.assertRaises(ValueError):
                motor.predizer(q, receita(), top_k=top_k)

    def test_predicoes_deterministicas_e_sem_dependencia_da_ordem(self):
        temas = taxonomia()
        treino = [questao("t1", "Treino semente"), questao("t2", "Treino estrela")]
        q = questao("nova", "Jardim planeta")
        rotulos = [rotulo("t1"), rotulo("t2", "beta")]
        dados = cache(temas, treino + [q])
        a = Motor(treino, rotulos, temas, dados)
        invertida = {"por_id": dict(reversed(list(temas["por_id"].items())))}
        b = Motor(list(reversed(treino)), list(reversed(rotulos)), invertida, dados)
        for k in (5, 20):
            r = receita(rrf_k=k, peso_prior=0.15)
            self.assertEqual(a.predizer(q, r), b.predizer(q, r))

    def test_top_k_nao_altera_primeiro_score_ou_margem(self):
        motor, q = self.montar()
        p, completo = motor.predizer(q, receita(), 1), motor.predizer(q, receita(), 8)
        self.assertEqual(len(p["top_candidatos"]), 1)
        for campo in ("tema_sugerido_id", "score", "margem"):
            self.assertEqual(p[campo], completo[campo])


if __name__ == "__main__":
    unittest.main()
