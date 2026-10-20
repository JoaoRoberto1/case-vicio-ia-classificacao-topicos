"""Testes sintéticos de regras e isolamento; não avaliam questões reais."""

from collections import Counter
from copy import deepcopy
import unittest

from classificacao_topicos.avaliacao import tema_aceito
from classificacao_topicos.protocolo import construir_particoes


def _taxonomia():
    return {
        "por_id": {
            "raiz": {
                "status": "active", "parent_id": "", "ancestrais_ids": []
            },
            "pai": {
                "status": "active", "parent_id": "raiz",
                "ancestrais_ids": ["raiz"],
            },
            "filho": {
                "status": "active", "parent_id": "pai",
                "ancestrais_ids": ["raiz", "pai"],
            },
            "irmao": {
                "status": "active", "parent_id": "pai",
                "ancestrais_ids": ["raiz", "pai"],
            },
            "outra_raiz": {
                "status": "active", "parent_id": "", "ancestrais_ids": [],
            },
            "extra": {
                "status": "active", "parent_id": "outra_raiz",
                "ancestrais_ids": ["outra_raiz"],
            },
            "inativo": {
                "status": "inactive", "parent_id": "pai",
                "ancestrais_ids": ["raiz", "pai"],
            },
        }
    }


def _rotulo(identificador, central="filho", extras=None, fora=False):
    return {
        "id": identificador,
        "tema_central_id": "" if fora else central,
        "extras_ids": extras or [],
        "fora_da_taxonomia": fora,
        "disciplina": "fora" if fora else "Disciplina A",
    }


def _dados():
    questoes = [
        {
            "id": f"Q{indice:04}",
            "texto_completo": f"assunto{indice} conteúdo{indice} contexto{indice}",
            "coorte": "historicas" if indice <= 15 else "recentes",
        }
        for indice in range(1, 19)
    ]
    rotulos = [
        _rotulo(f"Q{indice:04}", fora=indice in (3, 9, 15))
        for indice in range(1, 16)
    ]
    for indice in (2, 5, 8, 11, 14):
        rotulos[indice - 1]["disciplina"] = "Disciplina B"
    config = {
        "semente": 20261020,
        "dobras_externas": 5,
        "dobras_internas": 3,
        "duplicatas": {
            "limiar_jaccard": 0.85,
            "tamanho_shingle": 5,
            "minimo_tokens": 12,
        },
    }
    return questoes, rotulos, config


class RegraDeAcertoTests(unittest.TestCase):
    def test_aceita_central_extra_e_ancestrais_nas_duas_direcoes(self):
        taxonomia = _taxonomia()
        rotulo = _rotulo("Q", extras=["extra"])
        for sugestao in ("filho", "pai", "raiz", "extra", "outra_raiz"):
            with self.subTest(sugestao=sugestao):
                self.assertTrue(tema_aceito(sugestao, rotulo, taxonomia))
        self.assertTrue(
            tema_aceito("filho", _rotulo("Q", central="raiz"), taxonomia)
        )

    def test_nao_confunde_irmaos_com_ancestralidade(self):
        self.assertFalse(tema_aceito("irmao", _rotulo("Q"), _taxonomia()))
        self.assertFalse(tema_aceito("extra", _rotulo("Q"), _taxonomia()))

    def test_modos_de_sensibilidade(self):
        taxonomia = _taxonomia()
        rotulo = _rotulo("Q", extras=["extra"])
        self.assertTrue(tema_aceito("filho", rotulo, taxonomia, "exato"))
        self.assertTrue(tema_aceito("extra", rotulo, taxonomia, "exato"))
        self.assertFalse(tema_aceito("pai", rotulo, taxonomia, "exato"))
        self.assertTrue(tema_aceito("pai", rotulo, taxonomia, "imediato"))
        self.assertFalse(tema_aceito("raiz", rotulo, taxonomia, "imediato"))
        self.assertTrue(
            tema_aceito("filho", _rotulo("Q", central="pai"), taxonomia, "imediato")
        )
        with self.assertRaises(ValueError):
            tema_aceito("filho", rotulo, taxonomia, "inventado")

    def test_rejeita_fora_ids_invalidos_e_inativos(self):
        taxonomia = _taxonomia()
        self.assertFalse(tema_aceito("filho", _rotulo("Q", fora=True), taxonomia))
        self.assertFalse(tema_aceito("inativo", _rotulo("Q"), taxonomia))
        self.assertFalse(tema_aceito("ausente", _rotulo("Q"), taxonomia))
        self.assertFalse(tema_aceito("", _rotulo("Q"), taxonomia))
        for central in ("inativo", "ausente"):
            self.assertFalse(
                tema_aceito("pai", _rotulo("Q", central=central), taxonomia)
            )
        taxonomia["por_id"]["filho"]["status"] = "ativo"
        self.assertFalse(tema_aceito("filho", _rotulo("Q"), taxonomia))


class ParticoesTests(unittest.TestCase):
    def test_cada_rotulo_testado_uma_vez_e_sem_contaminacao_interna(self):
        manifesto = construir_particoes(*_dados())
        conhecidos = set(manifesto["rotulados_ids"])
        oficiais = set(manifesto["avaliacao_ids"])
        testes = []
        self.assertEqual(len(manifesto["folds"]), 5)
        for externa in manifesto["folds"]:
            treino = set(externa["treino_ids"])
            teste = set(externa["teste_ids"])
            self.assertFalse(treino & teste)
            self.assertEqual(treino | teste, conhecidos)
            self.assertFalse((treino | teste) & oficiais)
            testes.extend(teste)
            validacoes = []
            self.assertEqual(len(externa["internas"]), 3)
            for interna in externa["internas"]:
                treino_interno = set(interna["treino_ids"])
                validacao = set(interna["validacao_ids"])
                self.assertFalse(treino_interno & validacao)
                self.assertFalse((treino_interno | validacao) & teste)
                self.assertEqual(treino_interno | validacao, treino)
                validacoes.extend(validacao)
            self.assertEqual(Counter(validacoes), Counter(treino))
        self.assertEqual(Counter(testes), Counter(conhecidos))
        self.assertEqual(
            manifesto["coortes"]["recentes"]["avaliacao_ids"],
            ["Q0016", "Q0017", "Q0018"],
        )
        self.assertTrue(
            any("sem rótulos conhecidos" in aviso for aviso in manifesto["avisos"])
        )

    def test_deterministico_independente_da_ordem_sem_mutar_entradas(self):
        questoes, rotulos, config = _dados()
        copia = deepcopy((questoes, rotulos, config))
        manifesto = construir_particoes(questoes, rotulos, config)
        invertido = construir_particoes(questoes[::-1], rotulos[::-1], config)
        self.assertEqual(manifesto, invertido)
        self.assertEqual((questoes, rotulos, config), copia)

    def test_duplicatas_exatas_e_quase_duplicatas_transitivas(self):
        questoes, rotulos, config = _dados()
        config["duplicatas"] = {
            "limiar_jaccard": 0.6, "tamanho_shingle": 1, "minimo_tokens": 4,
        }
        # A/B e B/C têm Jaccard 4/6; A/C têm somente 3/7.
        questoes[0]["texto_completo"] = "alfa beta gama delta epsilon"
        questoes[1]["texto_completo"] = "alfa beta gama delta zeta"
        questoes[2]["texto_completo"] = "alfa beta gama zeta eta"
        # A duplicata oficial não ganha acesso a nenhum conjunto de treino.
        questoes[15]["texto_completo"] = " ALFA, BETA! GAMA delta EPSILON "
        questoes[15]["disciplina_origem"] = "origem diferente"
        manifesto = construir_particoes(questoes, rotulos, config)
        grupo = next(
            item for item in manifesto["grupos"] if "Q0001" in item["ids"]
        )
        self.assertEqual(grupo["ids"], ["Q0001", "Q0002", "Q0003", "Q0016"])
        self.assertEqual(grupo["tipo"], "quase_duplicatas")
        self.assertTrue(grupo["misto_rotulados_avaliacao"])
        self.assertEqual(grupo["coortes"], ["historicas", "recentes"])
        agrupados = set(grupo["rotulados_ids"])
        for externa in manifesto["folds"]:
            for chave in ("treino_ids", "teste_ids"):
                encontrados = agrupados & set(externa[chave])
                self.assertIn(encontrados, (set(), agrupados))
                self.assertNotIn("Q0016", externa[chave])
            for interna in externa["internas"]:
                for chave in ("treino_ids", "validacao_ids"):
                    encontrados = agrupados & set(interna[chave])
                    self.assertIn(encontrados, (set(), agrupados))
                    self.assertNotIn("Q0016", interna[chave])

    def test_texto_curto_igual_agrupa_mas_similar_nao(self):
        questoes, rotulos, config = _dados()
        questoes[0]["texto_completo"] = "TESTE curto."
        questoes[1]["texto_completo"] = "teste curto"
        questoes[2]["texto_completo"] = "teste curto diferente"
        manifesto = construir_particoes(questoes, rotulos, config)
        grupo = next(
            item for item in manifesto["grupos"] if "Q0001" in item["ids"]
        )
        self.assertEqual(grupo["ids"], ["Q0001", "Q0002"])
        self.assertEqual(grupo["tipo"], "exatas")

    def test_shingles_padrao_e_grupos_independentes_de_id_e_origem(self):
        questoes, rotulos, config = _dados()
        palavras = [f"palavra{indice}" for indice in range(40)]
        questoes[0]["texto_completo"] = " ".join(palavras)
        questoes[1]["texto_completo"] = " ".join(palavras[:-1] + ["alterada"])
        alteradas = palavras[:]
        alteradas[20] = "outra"
        questoes[2]["texto_completo"] = " ".join(alteradas)
        manifesto = construir_particoes(questoes, rotulos, config)
        grupo = next(
            item for item in manifesto["grupos"] if "Q0001" in item["ids"]
        )
        # Mudar só a última palavra supera 0,85; mudar a palavra central não.
        self.assertEqual(grupo["ids"], ["Q0001", "Q0002"])
        for questao in questoes:
            questao["id"] = "renomeado-" + questao["id"]
            questao["disciplina_origem"] = "metadado irrelevante"
        for rotulo in rotulos:
            rotulo["id"] = "renomeado-" + rotulo["id"]
        renomeado = construir_particoes(questoes, rotulos, config)
        outro_grupo = next(
            item for item in renomeado["grupos"]
            if "renomeado-Q0001" in item["ids"]
        )
        self.assertEqual(grupo["id"], outro_grupo["id"])
        self.assertEqual(
            outro_grupo["ids"], ["renomeado-Q0001", "renomeado-Q0002"]
        )

    def test_questao_sem_rotulo_pode_conectar_grupo_mas_nao_entrar_nos_folds(self):
        questoes, rotulos, config = _dados()
        config["duplicatas"] = {
            "limiar_jaccard": 0.6, "tamanho_shingle": 1, "minimo_tokens": 4,
        }
        questoes[0]["texto_completo"] = "alfa beta gama delta epsilon"
        questoes[1]["texto_completo"] = "alfa beta gama zeta eta"
        questoes[15]["texto_completo"] = "alfa beta gama delta zeta"
        manifesto = construir_particoes(questoes, rotulos, config)
        grupo = next(
            item for item in manifesto["grupos"] if "Q0001" in item["ids"]
        )
        self.assertEqual(grupo["rotulados_ids"], ["Q0001", "Q0002"])
        self.assertEqual(grupo["avaliacao_ids"], ["Q0016"])
        for fold in manifesto["folds"]:
            self.assertEqual(
                "Q0001" in fold["teste_ids"], "Q0002" in fold["teste_ids"]
            )
            self.assertNotIn("Q0016", fold["treino_ids"] + fold["teste_ids"])

    def test_equilibrio_de_tamanho_e_disciplina_em_grupos_unitarios(self):
        questoes, rotulos, config = _dados()
        manifesto = construir_particoes(questoes, rotulos, config)
        por_id = {rotulo["id"]: rotulo for rotulo in rotulos}
        tamanhos = [len(fold["teste_ids"]) for fold in manifesto["folds"]]
        self.assertLessEqual(max(tamanhos) - min(tamanhos), 1)
        contagens_b = [
            sum(
                por_id[identificador]["disciplina"] == "Disciplina B"
                for identificador in fold["teste_ids"]
            )
            for fold in manifesto["folds"]
        ]
        self.assertEqual(contagens_b, [1] * 5)
        self.assertTrue(
            any("estrato 'fora'" in aviso for aviso in manifesto["avisos"])
        )

    def test_configuracoes_invalidas_ids_repetidos_e_rotulo_orfao(self):
        for chave, valor in (
            ("semente", True), ("dobras_externas", 1), ("dobras_internas", 1)
        ):
            questoes, rotulos, config = _dados()
            config[chave] = valor
            with self.subTest(chave=chave), self.assertRaises(ValueError):
                construir_particoes(questoes, rotulos, config)
        for limiar in (0, -1, 1.01, float("nan"), True):
            questoes, rotulos, config = _dados()
            config["duplicatas"]["limiar_jaccard"] = limiar
            with self.subTest(limiar=limiar), self.assertRaises(ValueError):
                construir_particoes(questoes, rotulos, config)
        questoes, rotulos, config = _dados()
        with self.assertRaises(ValueError):
            construir_particoes(questoes + [questoes[0]], rotulos, config)
        with self.assertRaises(ValueError):
            construir_particoes(questoes, rotulos + [rotulos[0]], config)
        with self.assertRaises(ValueError):
            construir_particoes(questoes, rotulos + [_rotulo("inexistente")], config)

    def test_menos_grupos_reduz_dobras_com_aviso(self):
        questoes, rotulos, config = _dados()
        config["dobras_externas"] = 20
        config["dobras_internas"] = 20
        manifesto = construir_particoes(questoes, rotulos, config)
        self.assertEqual(len(manifesto["folds"]), 15)
        self.assertTrue(
            any("dobras reduzidas" in aviso for aviso in manifesto["avisos"])
        )

    def test_grupo_unico_impede_validacao(self):
        questoes, rotulos, config = _dados()
        for questao in questoes:
            questao["texto_completo"] = "Mesmo texto para todos os registros."
        with self.assertRaisesRegex(ValueError, "ao menos dois grupos"):
            construir_particoes(questoes, rotulos, config)


if __name__ == "__main__":
    unittest.main()
