import unittest
from scripts.registrar_tempo_questoes_large_m8 import medir_intervalos


class TempoQuestoesTests(unittest.TestCase):
    def item(self, tempo, tokens=10, janelas=1):
        return {"concluido_mtime_ns": tempo, "tokens": tokens, "janelas": janelas}

    def test_exclui_primeiro_denominador_mantem_intervalos(self):
        resultado = medir_intervalos([self.item(1_000_000_000, 999, 10),
                                     self.item(3_000_000_000, 20, 2),
                                     self.item(6_000_000_000, 30, 3)])
        self.assertEqual(resultado, {"registros_medidos": 2,
                                     "intervalos_ns": [2_000_000_000, 3_000_000_000],
                                     "segundos": 5.0, "janelas_medidas": 5,
                                     "tokens_corpo_medidos": 50})

    def test_recusa_timestamp_repetido_ou_decrescente(self):
        for tempos in ((3, 3), (3, 2)):
            with self.subTest(tempos=tempos), self.assertRaises(ValueError):
                medir_intervalos([self.item(t) for t in tempos])

    def test_recusa_amostra_sem_intervalo(self):
        with self.assertRaises(ValueError):
            medir_intervalos([self.item(1)])

    def test_recusa_timestamp_invalido(self):
        for invalido in (False, 0, -1, 1.5):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                medir_intervalos([self.item(invalido), self.item(5)])
