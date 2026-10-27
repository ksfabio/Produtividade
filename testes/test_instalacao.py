"""Etapa 6: diagnóstico, atalhos do Windows e utilidades de manutenção."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import instalacao
from dados.banco import Banco


class TestInstalacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verificar_pasta_nova(self):
        itens = instalacao.verificar(self.pasta)
        nomes = {i.nome: i for i in itens}
        self.assertEqual(nomes["Python"].ok, instalacao.sys.version_info >= (3, 11))
        self.assertTrue(nomes["Pasta do app"].ok)
        self.assertIn("ainda não existe", nomes["Dados"].detalhe)
        self.assertTrue(nomes["Backup"].ok)
        texto = instalacao.texto_verificacao(itens)
        self.assertIn("Python:", texto)
        self.assertIn("[OK] Pasta do app", texto)

    def test_verificar_com_dados_nao_altera_nada(self):
        b = Banco(self.pasta / "dados.db")
        cfg = b.config()
        cfg.pasta_backup = str(self.pasta / "onedrive-desligado")
        b.salvar_config(cfg)
        b.fechar()
        antes = (self.pasta / "dados.db").read_bytes()
        conteudo = sorted(p.name for p in self.pasta.iterdir())
        itens = {i.nome: i for i in instalacao.verificar(self.pasta)}
        self.assertIn("0 tarefas", itens["Dados"].detalhe)
        self.assertFalse(itens["Backup"].ok)  # pasta configurada não existe
        self.assertEqual((self.pasta / "dados.db").read_bytes(), antes)
        self.assertEqual(sorted(p.name for p in self.pasta.iterdir()), conteudo)  # nenhum arquivo criado

    def test_script_atalho_escapa_aspas(self):
        s = instalacao.script_atalho("Desktop", Path(r"C:\Py\pythonw.exe"), Path(r"C:\Users\D'Ávila\app.py"),
                                     Path(r"C:\Users\D'Ávila"), None)
        self.assertIn("GetFolderPath('Desktop')", s)
        self.assertIn(r"""$s.Arguments = '"C:\Users\D''Ávila\app.py"'""", s)
        self.assertNotIn("IconLocation", s)
        s2 = instalacao.script_atalho("Startup", Path("x"), Path("y"), Path("z"), Path(r"C:\a\icone.ico"))
        self.assertIn("IconLocation = 'C:\\a\\icone.ico'", s2)

    def test_atalho_fora_do_windows(self):
        with mock.patch.object(instalacao.sys, "platform", "linux"):
            ok, msg = instalacao.criar_atalho(self.pasta)
        self.assertFalse(ok)

    def test_iniciar_com_windows_remover(self):
        with mock.patch.dict(os.environ, {"APPDATA": str(self.pasta)}):
            pasta = instalacao.pasta_inicializar()
            pasta.mkdir(parents=True)
            self.assertFalse(instalacao.inicia_com_windows())
            (pasta / "Produtividade.cmd").write_text("x")
            self.assertTrue(instalacao.inicia_com_windows())
            ok, msg = instalacao.remover_inicializar()
            self.assertTrue(ok)
            self.assertFalse(instalacao.inicia_com_windows())
            self.assertIn("não estava", instalacao.remover_inicializar()[1])

    def test_resetar_mini_barra(self):
        db = self.pasta / "dados.db"
        b = Banco(db)
        cfg = b.config()
        cfg.mini_barra_x, cfg.mini_barra_y, cfg.mini_barra_recolhida = 4000, 3000, True
        b.salvar_config(cfg)
        b.fechar()
        instalacao.resetar_mini_barra(db)
        b = Banco(db)
        c = b.config()
        self.assertEqual((c.mini_barra_x, c.mini_barra_y, c.mini_barra_recolhida), (None, None, False))
        b.fechar()

    def test_scripts_bat_em_ascii_e_crlf(self):
        raiz = Path(__file__).resolve().parent.parent
        for nome in ("instalar.bat", "iniciar.bat", "testar.bat", "baixar_pacotes.bat"):
            dados = (raiz / nome).read_bytes()
            dados.decode("ascii")  # sem acentos: o cmd do Windows lê sem surpresas
            self.assertNotIn(b"\n", dados.replace(b"\r\n", b""), nome)


if __name__ == "__main__":
    unittest.main()
