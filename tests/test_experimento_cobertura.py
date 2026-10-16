"""Experimento 5C com fontes sintéticas; nenhum dado real, credencial ou API."""

from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classificacao_topicos import experimento_cobertura as experimento
from classificacao_topicos.execucao import executar_lote
from classificacao_topicos.politica import aplicar_politica
from tests import test_decisoes


BASE = {"ids_ambiguos": [], "confianca_minima": 0.95, "max_extras_publicar": 1}
TEMAS = {i: {"tema_id": i, "parent_id": pai, "nivel": nivel, "status": status}
         for i, pai, nivel, status in (
             ("T000", "", "0", "active"), ("T001", "T000", "1", "active"),
             ("T002", "T000", "1", "active"), ("T003", "T001", "2", "active"),
             ("T004", "T000", "1", "inactive"), ("T005", "T000", "1", "active"))}


def sugestao(identificador="Q0001", **alteracoes):
    return test_decisoes.sugestao(identificador, **alteracoes)


def original(identificador="Q0001", **alteracoes):
    resposta = sugestao(identificador, temas_alternativos=["T002"], **alteracoes)
    decisao = aplicar_politica(resposta, TEMAS, set(), confianca_minima=0.95, max_extras_publicar=2)
    return {"id": identificador, "sugestao": resposta, "decisao": decisao}


def referencia(identificador="Q0001", **alteracoes):
    ref = {"id": identificador, "temas_centrais_aceitaveis": ["T001"], "sem_tema": False,
           "situacao": "provisorio", "justificativa": "Referência sintética para testar o contrato.",
           "limitacoes": "Sem avaliação jurídica.", "tipo_referencia": "IA_sem_especialista",
           "responsavel": "Teste offline"}
    ref.update(alteracoes)
    return ref


def grupo(quantidade):
    propostas = [{"id": f"Q{i:04d}", "propor_publicar": True,
                  "decisao_v1": {"tema_central_id": "T001"}} for i in range(1, quantidade + 1)]
    return propostas, {p["id"]: referencia(p["id"]) for p in propostas}


class DecidirPropostaTests(unittest.TestCase):
    def test_exige_alternativas_como_unico_sinal_original(self):
        for decisao, sinais in (("publicar", []), ("revisar", []),
                               ("revisar", ["temas_alternativos", "confianca_abaixo_limiar"]),
                               ("revisar", ["revisao_solicitada"])):
            item = original()
            item["decisao"].update(decisao=decisao, sinais=sinais)
            with self.subTest(decisao=decisao, sinais=sinais), self.assertRaisesRegex(ValueError, "único bloqueio"):
                experimento.decidir_proposta(item, sugestao(), TEMAS, BASE)

    def test_falha_tecnica_retida_e_segundo_passe_precisa_ser_valido(self):
        resultado = experimento.decidir_proposta(original(), None, TEMAS, BASE)
        self.assertFalse(resultado["propor_publicar"])
        self.assertEqual(resultado["bloqueios"], ["falha_tecnica_segundo_passe"])
        for resposta in (sugestao("Q0002"), sugestao(tema_central_id="T004"),
                         sugestao(confianca_autodeclarada=float("nan")), sugestao(extras_ids=["T001"])):
            with self.subTest(resposta=resposta), self.assertRaises(ValueError):
                experimento.decidir_proposta(original(), resposta, TEMAS, BASE)

    def test_segundo_passe_deve_passar_todas_as_regras_base(self):
        casos = [({"confianca_autodeclarada": 0.949}, "confianca_abaixo_limiar"),
                 ({"requer_revisao": True}, "revisao_solicitada"),
                 ({"temas_alternativos": ["T002"]}, "temas_alternativos"),
                 ({"tema_central_id": "T000"}, "tema_raiz"),
                 ({"extras_ids": ["T002", "T005"]}, "excesso_extras"),
                 ({"sem_tema": True, "tema_central_id": ""}, "sem_tema_sem_confirmacao")]
        for campos, sinal in casos:
            with self.subTest(campos=campos):
                resultado = experimento.decidir_proposta(original(), sugestao(**campos), TEMAS, BASE)
                self.assertFalse(resultado["propor_publicar"])
                self.assertIn(sinal, resultado["bloqueios"])
        resultado = experimento.decidir_proposta(original(), sugestao(), TEMAS, {**BASE, "ids_ambiguos": ["T001"]})
        self.assertFalse(resultado["propor_publicar"])
        self.assertIn("tema_ambiguo", resultado["bloqueios"])

    def test_exige_mesmo_central_e_mesmo_conjunto_de_extras(self):
        for campos, sinal in (({"tema_central_id": "T003"}, "central_divergente_entre_passes"),
                              ({"extras_ids": ["T005"]}, "extras_divergentes_entre_passes")):
            with self.subTest(campos=campos):
                resultado = experimento.decidir_proposta(original(), sugestao(**campos), TEMAS, BASE)
                self.assertFalse(resultado["propor_publicar"])
                self.assertIn(sinal, resultado["bloqueios"])
        item = original(extras_ids=["T003", "T005"])
        resultado = experimento.decidir_proposta(item, sugestao(extras_ids=["T005", "T003"]),
                                                 TEMAS, {**BASE, "max_extras_publicar": 2})
        self.assertTrue(resultado["propor_publicar"])

    def test_concordancia_nao_recalibra_confianca_nem_muta_original(self):
        item = original(confianca_autodeclarada=0.95)
        segunda = sugestao(confianca_autodeclarada=1.0)
        anterior = deepcopy((item, segunda, TEMAS, BASE))
        resultado = experimento.decidir_proposta(item, segunda, TEMAS, BASE)
        self.assertTrue(resultado["propor_publicar"])
        self.assertEqual((item, segunda, TEMAS, BASE), anterior)
        self.assertEqual(item["decisao"]["confianca"], 0.95)


class AvaliarGrupoTests(unittest.TestCase):
    def test_zero_propostas_nao_adota_mesmo_com_referencias_coincidentes(self):
        for quantidade in (0, 2):
            propostas, referencias = grupo(quantidade)
            for proposta in propostas:
                proposta["propor_publicar"] = False
            resumo, comparacoes = experimento.avaliar_grupo(propostas, referencias, TEMAS)
            self.assertFalse(resumo["adotar_lote"])
            self.assertEqual(resumo["propostas"], 0)
            self.assertIsNone(resumo["concordancia_estrita"])
            self.assertEqual(len(comparacoes), quantidade)

    def test_limiar_exato_95_adota_e_valor_abaixo_rejeita(self):
        for n, esperado in ((20, True), (19, False)):
            propostas, referencias = grupo(n)
            referencias["Q0001"] = referencia(situacao="inconclusivo", sem_tema=None, temas_centrais_aceitaveis=[])
            with self.subTest(n=n):
                resumo, _ = experimento.avaliar_grupo(propostas, referencias, TEMAS)
                self.assertEqual(resumo["adotar_lote"], esperado)
                self.assertEqual(resumo["coincidencias_estritas"], n - 1)
                self.assertEqual(resumo["propostas"], n)

    def test_divergencia_explicita_bloqueia_lote_mesmo_com_95_porcento(self):
        propostas, referencias = grupo(20)
        referencias["Q0001"] = referencia(temas_centrais_aceitaveis=["T002"])
        resumo, _ = experimento.avaliar_grupo(propostas, referencias, TEMAS)
        self.assertEqual(resumo["concordancia_estrita"], 0.95)
        self.assertEqual(resumo["divergentes_ids"], ["Q0001"])
        self.assertFalse(resumo["adotar_lote"])
        self.assertEqual(resumo["propostas"], 20)

    def test_inconclusivo_multiplos_e_pai_filho_mantidos_no_denominador_estrito(self):
        propostas, referencias = grupo(4)
        referencias["Q0002"] = referencia("Q0002", situacao="inconclusivo")
        referencias["Q0003"] = referencia("Q0003", temas_centrais_aceitaveis=["T001", "T002"])
        referencias["Q0004"] = referencia("Q0004", temas_centrais_aceitaveis=["T003"])
        anterior = deepcopy((propostas, referencias))
        resumo, _ = experimento.avaliar_grupo(propostas, referencias, TEMAS)
        self.assertEqual(resumo["propostas"], 4)
        self.assertEqual(resumo["concordancia_estrita"], 0.25)
        self.assertEqual(resumo["concordancia_regra_v1"], 0.75)
        self.assertEqual(resumo["comparacoes_regra_v1"],
                         {"exata": 2, "pai_filho_direto": 1, "divergencia": 0, "inconclusivo": 1})
        self.assertEqual(resumo["nao_confirmados_ids"], ["Q0002", "Q0003", "Q0004"])
        self.assertFalse(resumo["adotar_lote"])
        self.assertEqual((propostas, referencias), anterior)

    def test_casos_sem_proposta_nao_entram_no_gate_nem_apagam_denominador(self):
        propostas, referencias = grupo(3)
        propostas[2]["propor_publicar"] = False
        referencias["Q0002"] = referencia("Q0002", temas_centrais_aceitaveis=["T002"])
        referencias["Q0003"] = referencia("Q0003", temas_centrais_aceitaveis=["T002"])
        resumo, comparacoes = experimento.avaliar_grupo(propostas, referencias, TEMAS)
        self.assertEqual(resumo["propostas"], 2)
        self.assertEqual(resumo["concordancia_estrita"], 0.5)
        self.assertEqual(resumo["divergentes_ids"], ["Q0002"])
        self.assertEqual(len(comparacoes), 3)
        self.assertFalse(resumo["adotar_lote"])


class FluxoExperimentoTests(unittest.TestCase):
    def setUp(self):
        f = self.fixture = test_decisoes.DecisoesTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.raiz = f.raiz
        self.pasta = self.raiz / experimento._EXPERIMENTO
        self.pasta.mkdir()
        for alvo in ("urllib.request.urlopen", "classificacao_topicos.execucao.carregar_configuracao",
                     "classificacao_topicos.execucao.gerar_json"):
            bloqueio = patch(alvo, side_effect=AssertionError("Rede e credenciais não autorizadas no teste."))
            bloqueio.start()
            self.addCleanup(bloqueio.stop)
        temas = json.loads((f.preparacao / "temas_preparados.json").read_bytes())
        temas.append({"tema_id": "5554", "parent_id": "T000", "nivel": "1", "status": "active"})
        self.gravar("artefatos/preparacao/temas_preparados.json", temas)
        mp = json.loads((f.preparacao / "manifesto.json").read_bytes())
        mp["produtos_sha256"]["temas_preparados.json"] = experimento._hash_bytes((f.preparacao / "temas_preparados.json").read_bytes())
        self.gravar("artefatos/preparacao/manifesto.json", mp)
        ml = json.loads((f.lote / "manifesto_lote.json").read_bytes())
        ml.update(preparacao_sha256=experimento._hash_bytes((f.preparacao / "manifesto.json").read_bytes()),
                  preparacao_produtos_sha256=mp["produtos_sha256"])
        self.gravar("artefatos/lote/manifesto_lote.json", ml)
        ambiguidades = json.loads(f.ambiguidades.read_bytes())
        ambiguidades["fonte_sha256"] = mp["produtos_sha256"]["temas_preparados.json"]
        self.gravar("config/ambiguidades.json", ambiguidades)
        f.config["ambiguidades_sha256"] = experimento._hash_bytes(f.ambiguidades.read_bytes())
        self.gravar("config/politica_v1.json", f.config)
        f.execucao = self.raiz / "artefatos/recibos-base"
        f.respostas = {"Q0001": sugestao(confianca_autodeclarada=0.95, temas_alternativos=["T002"]),
                       "Q0002": sugestao("Q0002", confianca_autodeclarada=0.96, temas_alternativos=["T002"]),
                       "Q0003": sugestao("Q0003", tema_central_id="5554")}
        f.gravar_recibos()
        f.preparar(saida=self.raiz / experimento._BASE)
        self.base_bytes = {p: p.read_bytes() for p in (self.raiz / experimento._BASE).iterdir()}
        self.gravar("prompts/desambiguacao_v1.txt", "Prompt sintético do segundo passe.\n".encode("utf-8"))
        self.segundo_lote = self.raiz / "artefatos/lote-segundo"
        self.gravar("artefatos/lote-segundo/entradas.jsonl", (f.lote / "entradas.jsonl").read_bytes())
        ml.update(prompt_version="desambiguacao-v1", prompt_sha256=experimento._hash_bytes(
            (self.raiz / "prompts/desambiguacao_v1.txt").read_bytes()))
        self.gravar("artefatos/lote-segundo/manifesto_lote.json", ml)
        self.recibos = self.raiz / "artefatos/segundo-passe"
        with patch("classificacao_topicos.execucao.carregar_configuracao",
                   return_value={"api_key": "ficticia", "model": "gemini-3.5-flash-lite"}), \
                patch("classificacao_topicos.execucao.gerar_json", side_effect=lambda prompt, *a, **k:
                      test_decisoes.retorno(sugestao(prompt.split()[-1], confianca_autodeclarada=1.0))):
            executar_lote(self.segundo_lote, f.preparacao, self.recibos, ids_selecionados=["Q0001", "Q0002"],
                          limite=2, intervalo_segundos=0)
        politica = {"versao": "politica-v2", "procedimento": "desambiguacao-controlada-v1",
                    "selecao": {"quantidade": 2}, "modelo": "gemini-3.5-flash-lite",
                    "prompt": "prompts/desambiguacao_v1.txt", "prompt_version": "desambiguacao-v1",
                    "execucao": {"max_tentativas_por_id": 2, "max_chamadas": 4},
                    "avaliacao": {"limiar_numerador": 95, "limiar_denominador": 100, "max_divergencias_explicitas": 0},
                    "achado_conhecido": {"id": "Q0003", "motivo": "Achado conhecido sintético."}}
        self.gravar("config/politica_v2.json", politica)
        questoes = experimento._linhas((f.preparacao / "questoes_preparadas.jsonl").read_bytes())
        self.gravar((experimento._EXPERIMENTO / "entradas_cegas/bloco_01.jsonl").as_posix(),
                    experimento._jsonl(questoes[:2]))
        self.gravar((experimento._EXPERIMENTO / "ids_selecionados.json").as_posix(), ["Q0001", "Q0002"])
        fontes = [*self.base_bytes, *f.preparacao.iterdir(), f.politica, self.raiz / "config/politica_v2.json",
                  self.raiz / "prompts/desambiguacao_v1.txt", self.pasta / "ids_selecionados.json",
                  self.pasta / "entradas_cegas/bloco_01.jsonl"]
        registro = {"procedimento": "preregistro-desambiguacao-v1", "ids": ["Q0001", "Q0002"],
                    "distribuicao": {"bloco_01": ["Q0001", "Q0002"]}, "registrado_utc": "2026-10-16T00:00:00+00:00",
                    "execucao": {"lote": "artefatos/lote-segundo", "recibos": "artefatos/segundo-passe"},
                    "fontes_sha256": {p.relative_to(self.raiz).as_posix(): experimento._hash_bytes(p.read_bytes()) for p in fontes}}
        self.gravar((experimento._EXPERIMENTO / "preregistro.json").as_posix(), registro)

    def gravar(self, nome, conteudo):
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo if isinstance(conteudo, bytes) else experimento._json_bytes(conteudo))
        return caminho

    def referencias(self, **alteracoes):
        referencias = [referencia("Q0001", **alteracoes), referencia("Q0002")]
        self.gravar((experimento._EXPERIMENTO / "referencias/bloco_01.jsonl").as_posix(), experimento._jsonl(referencias))
        self.gravar((experimento._EXPERIMENTO / "fontes/bloco_01.json").as_posix(), {"origem": "fixture sintética"})

    def preparar_comparacao(self, **alteracoes):
        experimento.propor(self.raiz)
        self.referencias(**alteracoes)
        experimento.congelar_referencias(self.raiz)

    def test_fluxo_completo_reproduz_bytes_hashes_e_preserva_confianca_e_base(self):
        resumo = experimento.propor(self.raiz)
        self.assertFalse((self.pasta / "referencias").exists())
        self.assertFalse(resumo["referencias_consultadas"])
        self.assertEqual(resumo["propostos_ids"], ["Q0001", "Q0002"])
        self.referencias()
        congelamento = experimento.congelar_referencias(self.raiz)
        self.assertEqual(experimento.congelar_referencias(self.raiz), congelamento)
        avaliacao = experimento.concluir(self.raiz)
        self.assertTrue(avaliacao["adotar_lote"])
        self.assertEqual(avaliacao["novos_publicados_ids"], ["Q0001", "Q0002"])
        self.assertEqual(avaliacao["cobertura_base"], 1 / 3)
        self.assertEqual(avaliacao["cobertura_final"], 2 / 3)
        destino = self.raiz / "artefatos/decisoes-v2"
        linhas = list(csv.DictReader(io.StringIO((destino / "publicacao.csv").read_text(encoding="utf-8"))))
        self.assertEqual([l["confianca"] for l in linhas], ["0.95", "0.96", "0.97"])
        self.assertEqual([l["decisao"] for l in linhas], ["publicar", "publicar", "revisar"])
        trilha = experimento._linhas((destino / "trilha_decisoes.jsonl").read_bytes())
        self.assertEqual(trilha[0]["sugestao"]["temas_alternativos"], ["T002"])
        self.assertEqual(trilha[2]["decisao"]["tema_central_id"], "5554")
        manifesto = json.loads((destino / "manifesto_decisoes.json").read_bytes())
        for nome, digest in manifesto["produtos_sha256"].items():
            self.assertEqual(experimento._hash_bytes((destino / nome).read_bytes()), digest)
        experimento._conferir(self.raiz, manifesto["fontes_sha256"])
        self.assertIn("artefatos/segundo-passe/Q0001.json", manifesto["fontes_sha256"])
        copia = self.raiz / "artefatos/reproducao"
        self.assertEqual(experimento.concluir(self.raiz, copia), avaliacao)
        self.assertEqual({p.name: p.read_bytes() for p in copia.iterdir()},
                         {p.name: p.read_bytes() for p in destino.iterdir()})
        self.assertEqual(experimento.concluir(self.raiz), avaliacao)
        self.assertEqual({p: p.read_bytes() for p in self.base_bytes}, self.base_bytes)

    def test_gate_rejeitado_mantem_todas_propostas_no_denominador_e_nao_promove_nenhuma(self):
        self.preparar_comparacao(temas_centrais_aceitaveis=["T002"])
        resumo = experimento.concluir(self.raiz)
        self.assertFalse(resumo["adotar_lote"])
        self.assertEqual(resumo["propostas"], 2)
        self.assertEqual(resumo["concordancia_estrita"], 0.5)
        self.assertEqual(resumo["novos_publicados_ids"], [])
        self.assertEqual(resumo["decisoes_finais"], {"revisar": 3})
        self.assertEqual(resumo["ganho_liquido_questoes"], -1)

    def test_congelamento_rejeita_referencia_de_nivel_zero(self):
        experimento.propor(self.raiz)
        self.referencias(temas_centrais_aceitaveis=["T000"])
        with self.assertRaisesRegex(ValueError, "nível zero"):
            experimento.congelar_referencias(self.raiz)
        self.assertFalse((self.pasta / "manifesto_referencias.json").exists())

    def test_congelamento_nao_le_referencias_com_propostas_ausentes_ou_adulteradas(self):
        experimento.propor(self.raiz)
        for nome in ("manifesto_propostas.json", "propostas.jsonl"):
            caminho = self.pasta / "propostas" / nome
            original_bytes = caminho.read_bytes()
            for ausente in (True, False):
                if ausente:
                    caminho.unlink()
                else:
                    caminho.write_bytes(b'{"incompleto":true}\n')
                try:
                    with self.subTest(nome=nome, ausente=ausente), \
                            patch.object(experimento, "_carregar_revisoes",
                                         side_effect=AssertionError("Referências não podem ser lidas.")) as carregar:
                        with self.assertRaises(ValueError):
                            experimento.congelar_referencias(self.raiz)
                        carregar.assert_not_called()
                    self.assertFalse((self.pasta / "manifesto_referencias.json").exists())
                finally:
                    caminho.write_bytes(original_bytes)

    def test_adulteracao_de_fonte_congelada_bloqueia_sem_escrever_propostas(self):
        caminho = self.raiz / "config/politica_v2.json"
        caminho.write_bytes(caminho.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Hash congelado divergente"):
            experimento.propor(self.raiz)
        self.assertFalse((self.pasta / "propostas").exists())

    def test_recibo_adulterado_ou_arquivo_extra_bloqueiam_propostas(self):
        caminho = self.recibos / "Q0001.json"
        original_bytes = caminho.read_bytes()
        registro = json.loads(original_bytes)
        registro["sugestao"]["confianca_autodeclarada"] = 0.99
        caminho.write_bytes(experimento._json_bytes(registro))
        with self.assertRaisesRegex(ValueError, "Checksum"):
            experimento.propor(self.raiz)
        caminho.write_bytes(original_bytes)
        (self.recibos / "Q0003.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "sem arquivos extras"):
            experimento.propor(self.raiz)
        self.assertFalse((self.pasta / "propostas").exists())

    def test_propostas_e_referencias_congeladas_adulteradas_bloqueiam_conclusao(self):
        self.preparar_comparacao()
        for caminho, mensagem in ((self.pasta / "propostas/propostas.jsonl", "Propostas não coincidem"),
                                  (self.pasta / "referencias/bloco_01.jsonl", "Hash congelado divergente")):
            original_bytes = caminho.read_bytes()
            caminho.write_bytes(original_bytes + b" ")
            try:
                with self.subTest(caminho=caminho), self.assertRaisesRegex(ValueError, mensagem):
                    experimento.concluir(self.raiz)
                self.assertFalse((self.raiz / "artefatos/decisoes-v2").exists())
            finally:
                caminho.write_bytes(original_bytes)

    def test_recibo_alterado_durante_comparacao_e_rechecado_antes_de_gravar(self):
        self.preparar_comparacao()
        avaliar = experimento.avaliar_grupo

        def adulterar(*args):
            resultado = avaliar(*args)
            caminho = self.recibos / "Q0001.json"
            caminho.write_bytes(caminho.read_bytes() + b" ")
            return resultado

        with patch.object(experimento, "avaliar_grupo", side_effect=adulterar):
            with self.assertRaisesRegex(ValueError, "Hash congelado divergente"):
                experimento.concluir(self.raiz)
        self.assertFalse((self.raiz / "artefatos/decisoes-v2").exists())

    def test_saida_divergente_permanece_intacta(self):
        self.preparar_comparacao()
        experimento.concluir(self.raiz)
        destino = self.raiz / "artefatos/decisoes-v2"
        csv_path = destino / "publicacao.csv"
        csv_path.write_bytes(csv_path.read_bytes() + b"adulteracao\n")
        anteriores = {p: p.read_bytes() for p in destino.iterdir()}
        with self.assertRaisesRegex(ValueError, "Saída existente diverge"):
            experimento.concluir(self.raiz)
        self.assertEqual({p: p.read_bytes() for p in anteriores}, anteriores)


class SaidaExperimentoTests(unittest.TestCase):
    def test_arquivo_no_destino_nao_e_sobrescrito(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "existente"
            saida.write_bytes(b"preservar")
            with self.assertRaisesRegex(ValueError, "pasta"):
                experimento._salvar(saida, {"produto.json": b"{}"})
            self.assertEqual(saida.read_bytes(), b"preservar")

    def test_ancestral_link_ou_juncao_e_recusado_antes_de_escrever(self):
        with tempfile.TemporaryDirectory() as pasta:
            ancestral = Path(pasta) / "atalho"
            saida = ancestral / "nova-pasta"
            original_is_symlink = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda p: p == ancestral or original_is_symlink(p)):
                with self.assertRaisesRegex(ValueError, "links ou junções"):
                    experimento._salvar(saida, {"produto.json": b"{}"})
            self.assertFalse(saida.exists())


if __name__ == "__main__":
    unittest.main()
