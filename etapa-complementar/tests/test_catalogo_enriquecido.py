"""Contrato do catálogo: descrições preparatórias sem acesso a questões ou rótulos."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from classificacao_catalogo.catalogo import ARQUIVOS, enriquecer


RAIZ = Path(__file__).resolve().parents[1]


def taxonomia_sintetica():
    registros = [
        {
            "tema_id": "raiz",
            "titulo": "Disciplina sintética",
            "descricao": "Descrição original da raiz.",
            "disciplina": "Disciplina sintética",
            "status": "active",
            "nivel": "0",
            "parent_id": "",
            "ancestrais_ids": [],
            "filhos_ids": ["tema-a", "inativo"],
            "caminho": "Disciplina sintética",
            "avisos": [],
            "elegivel": True,
        },
        {
            "tema_id": "tema-a",
            "titulo": "Tema A",
            "descricao": "Descrição original A.",
            "disciplina": "Disciplina sintética",
            "status": "active",
            "nivel": "1",
            "parent_id": "raiz",
            "ancestrais_ids": ["raiz"],
            "filhos_ids": [],
            "caminho": "Disciplina sintética > Tema A",
            "avisos": ["aviso sintético"],
            "elegivel": True,
        },
        {
            "tema_id": "inativo",
            "titulo": "Tema inativo",
            "descricao": "Descrição original inativa.",
            "disciplina": "Disciplina sintética",
            "status": "inactive",
            "nivel": "1",
            "parent_id": "raiz",
            "ancestrais_ids": ["raiz"],
            "filhos_ids": ["tema-b"],
            "caminho": "Disciplina sintética > Tema inativo",
            "avisos": [],
            "elegivel": False,
        },
        {
            "tema_id": "tema-b",
            "titulo": "Tema B",
            "descricao": "Descrição original B.",
            "disciplina": "Disciplina sintética",
            "status": "active",
            "nivel": "2",
            "parent_id": "inativo",
            "ancestrais_ids": ["raiz", "inativo"],
            "filhos_ids": [],
            "caminho": "Disciplina sintética > Tema inativo > Tema B",
            "avisos": ["ancestral inativo"],
            "elegivel": False,
        },
    ]
    return {"registros": registros, "por_id": {r["tema_id"]: r for r in registros}}


def descritor_sintetico(tema_id):
    return {
        "tema_id": tema_id,
        "descricao": "Definição sintética de um conceito do catálogo.",
        "termos": ["expressão alfa", "expressão beta", "expressão gama", "expressão delta", "expressão épsilon"],
        "fontes": ["https://fonte.example/conceitos"],
        "ambiguo": False,
    }


def documento_sintetico(*ids):
    return {
        "schema": "enriquecimento_catalogo_m7_v1",
        "disciplina": "Disciplina sintética",
        "procedimento": "LLM_preparacao_somente_taxonomia",
        "questoes_ou_rotulos_consultados": False,
        "registros": [descritor_sintetico(i) for i in ids],
    }


class CatalogoEnriquecidoSinteticoTest(unittest.TestCase):
    def setUp(self):
        self.taxonomia = taxonomia_sintetica()
        self.documentos = [documento_sintetico("tema-a", "tema-b")]

    def test_altera_somente_descricao_preservando_titulos_status_e_arvore(self):
        anterior = deepcopy(self.taxonomia)
        resultado = enriquecer(self.taxonomia, self.documentos)
        self.assertEqual(list(resultado["por_id"]), list(anterior["por_id"]))
        for original, enriquecido in zip(anterior["registros"], resultado["registros"]):
            with self.subTest(tema=original["tema_id"]):
                self.assertEqual(set(enriquecido), set(original))
                for campo, valor in original.items():
                    if campo != "descricao":
                        self.assertEqual(enriquecido[campo], valor)
                if original["tema_id"] in {"tema-a", "tema-b"}:
                    self.assertNotEqual(enriquecido["descricao"], original["descricao"])
                    self.assertIn("Definição sintética", enriquecido["descricao"])
                    for termo in self.documentos[0]["registros"][0]["termos"]:
                        self.assertIn(termo, enriquecido["descricao"])
                else:
                    self.assertEqual(enriquecido, original)
        self.assertEqual(self.taxonomia, anterior)

    def test_nao_muta_documentos_nem_compartilha_listas_com_original(self):
        taxonomia_anterior = deepcopy(self.taxonomia)
        documentos_anteriores = deepcopy(self.documentos)
        resultado = enriquecer(self.taxonomia, self.documentos)
        self.assertEqual(self.documentos, documentos_anteriores)
        for registro in resultado["registros"]:
            self.assertIs(resultado["por_id"][registro["tema_id"]], registro)
            self.assertIsNot(registro, self.taxonomia["por_id"][registro["tema_id"]])
        resultado["por_id"]["tema-a"]["avisos"].append("mudança somente na saída")
        resultado["por_id"]["raiz"]["filhos_ids"].clear()
        self.assertEqual(self.taxonomia, taxonomia_anterior)
        self.assertEqual(self.documentos, documentos_anteriores)

    def test_campos_extras_do_descritor_nao_sobrescrevem_taxonomia(self):
        r = self.documentos[0]["registros"][0]
        r.update(titulo="Título adulterado", status="inactive", parent_id="outro", filhos_ids=["outro"])
        resultado = enriquecer(self.taxonomia, self.documentos)
        for campo in ("titulo", "status", "parent_id", "filhos_ids"):
            self.assertEqual(resultado["por_id"]["tema-a"][campo], self.taxonomia["por_id"]["tema-a"][campo])

    def test_cobre_candidato_ativo_mesmo_com_ancestral_inativo(self):
        resultado = enriquecer(self.taxonomia, self.documentos)
        self.assertNotEqual(resultado["por_id"]["tema-b"]["descricao"], self.taxonomia["por_id"]["tema-b"]["descricao"])
        self.assertEqual(resultado["por_id"]["tema-b"]["parent_id"], "inativo")
        self.assertFalse(resultado["por_id"]["tema-b"]["elegivel"])

    def test_cobertura_incompleta_recusada(self):
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, [documento_sintetico("tema-a")])

    def test_catalogo_vazio_nao_cobre_candidatos(self):
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, [])

    def test_descritor_duplicado_no_mesmo_documento_recusado(self):
        self.documentos[0]["registros"].append(descritor_sintetico("tema-a"))
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, self.documentos)

    def test_descritor_duplicado_entre_documentos_recusado(self):
        self.documentos.append(documento_sintetico("tema-a"))
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, self.documentos)

    def test_divisao_em_documentos_nao_muda_conteudo(self):
        esperado = enriquecer(self.taxonomia, self.documentos)
        dividido = [documento_sintetico("tema-b"), documento_sintetico("tema-a")]
        self.assertEqual(enriquecer(self.taxonomia, dividido), esperado)

    def test_raiz_inativo_e_id_desconhecido_recusados(self):
        for tema_id in ("raiz", "inativo", "desconhecido"):
            with self.subTest(tema_id=tema_id):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"].append(descritor_sintetico(tema_id))
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_procedimento_deve_ser_preparacao_somente_taxonomia(self):
        for valor in (None, "", "LLM_classificacao", "LLM_preparacao_com_questoes"):
            with self.subTest(procedimento=valor):
                documentos = deepcopy(self.documentos)
                documentos[0]["procedimento"] = valor
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_declaracao_sem_questoes_deve_ser_false_booleano_explicito(self):
        for valor in (True, None, 0, "false", "False", "não"):
            with self.subTest(valor=valor):
                documentos = deepcopy(self.documentos)
                documentos[0]["questoes_ou_rotulos_consultados"] = valor
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)
        del self.documentos[0]["questoes_ou_rotulos_consultados"]
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, self.documentos)

    def test_schema_incompativel_ou_ausente_recusado(self):
        for valor in (None, "", "enriquecimento_catalogo_v0"):
            with self.subTest(schema=valor):
                documentos = deepcopy(self.documentos)
                documentos[0]["schema"] = valor
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)
        del self.documentos[0]["schema"]
        with self.assertRaises(ValueError):
            enriquecer(self.taxonomia, self.documentos)

    def test_descricao_precisa_ser_texto_nao_vazio(self):
        for valor in (None, "", "  \n", 12, []):
            with self.subTest(descricao=valor):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["descricao"] = valor
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_termos_aceitam_limites_cinco_e_doze(self):
        for quantidade in (5, 12):
            with self.subTest(quantidade=quantidade):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["termos"] = [f"termo sintético {i}" for i in range(quantidade)]
                enriquecer(self.taxonomia, documentos)

    def test_termos_fora_do_intervalo_recusados(self):
        for quantidade in (0, 4, 13):
            with self.subTest(quantidade=quantidade):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["termos"] = [f"termo sintético {i}" for i in range(quantidade)]
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_termos_invalidos_ou_repetidos_recusados(self):
        variantes = [
            None,
            "um;dois;três;quatro;cinco",
            ["um", "dois", "três", "quatro", ""],
            ["um", "dois", "três", "quatro", "   "],
            ["um", "dois", "três", "quatro", 5],
            ["um", "dois", "três", "quatro", "um"],
        ]
        for termos in variantes:
            with self.subTest(termos=termos):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["termos"] = termos
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_fontes_exigem_lista_nao_vazia_e_https_com_host(self):
        variantes = [
            [], None, "https://fonte.example",
            ["http://fonte.example"], ["ftp://fonte.example"],
            ["/fonte/local"], ["https:///sem-host"], [""],
            ["https://fonte.example", "http://outra.example"],
        ]
        for fontes in variantes:
            with self.subTest(fontes=fontes):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["fontes"] = fontes
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)

    def test_ambiguidade_precisa_ser_booleano(self):
        for valor in (None, "true", 0, 1):
            with self.subTest(ambiguo=valor):
                documentos = deepcopy(self.documentos)
                documentos[0]["registros"][0]["ambiguo"] = valor
                with self.assertRaises(ValueError):
                    enriquecer(self.taxonomia, documentos)
        self.documentos[0]["registros"][0]["ambiguo"] = True
        enriquecer(self.taxonomia, self.documentos)

    def test_execucoes_repetidas_sao_deterministicas(self):
        primeiro = enriquecer(self.taxonomia, self.documentos)
        segundo = enriquecer(self.taxonomia, self.documentos)
        self.assertEqual(primeiro, segundo)


class CatalogoEnriquecidoRealTest(unittest.TestCase):
    def test_quatro_documentos_cobrem_371_candidatos_sem_alterar_taxonomia(self):
        # Esta integração lê somente temas e descrições; não carrega contexto,
        # questões, referências humanas ou predições de qualquer experimento.
        registros = json.loads((RAIZ / "artefatos/preparacao/temas_preparados.json").read_text(encoding="utf-8"))
        taxonomia = {"registros": registros, "por_id": {r["tema_id"]: r for r in registros}}
        anterior = deepcopy(taxonomia)
        self.assertEqual(len(ARQUIVOS), 4)
        documentos = [json.loads((RAIZ / p).read_text(encoding="utf-8")) for p in ARQUIVOS]
        descritores = [r for doc in documentos for r in doc["registros"]]
        esperados = {r["tema_id"] for r in registros if r["status"] == "active" and int(r["nivel"]) > 0}
        self.assertEqual(len(esperados), 371)
        self.assertEqual(len(descritores), 371)
        self.assertEqual({r["tema_id"] for r in descritores}, esperados)
        resultado = enriquecer(taxonomia, documentos)
        self.assertEqual(taxonomia, anterior)
        self.assertEqual(len(resultado["registros"]), len(registros))
        for original, enriquecido in zip(registros, resultado["registros"]):
            with self.subTest(tema_id=original["tema_id"]):
                restaurado = dict(enriquecido, descricao=original["descricao"])
                self.assertEqual(restaurado, original)
                if original["tema_id"] in esperados:
                    self.assertNotEqual(original["descricao"], enriquecido["descricao"])
                else:
                    self.assertEqual(enriquecido, original)


if __name__ == "__main__":
    unittest.main()
