"""Produtividade: ponto de entrada.

Sem argumentos, abre a interface (instale antes com instalar.bat; veja INSTALACAO.md).

Instalação e manutenção:
    python app.py verificar            confere Python, PySide6, pasta, dados e backup
    python app.py atalho               cria o atalho na Área de Trabalho
    python app.py iniciar-com-windows sim|nao
    python app.py resetar-mini         volta a mini barra para a posição padrão

Linha de comando (útil para testes e sem interface):
    python app.py hoje                 mostra hoje e os próximos dias
    python app.py nova "texto"         captura rápida (mesma sintaxe da mini barra)
    python app.py prever "texto"       mostra o que o app entende, sem salvar
    python app.py feito ID             conclui a tarefa
    python app.py adiar ID [motivo]    adia para o próximo dia com espaço
    python app.py decidir ID OPCAO     fazer_hoje | quebrar | delegar | cancelar
    python app.py horas DIA TEMPO      ex.: horas 29/10 2h  (horas livres do dia)
    python app.py semana               as próximas 4 semanas, dia a dia
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PASTA_APP = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_APP))

from dados.banco import Banco  # noqa: E402
from nucleo.captura import formata_dia, formata_minutos, le_dia, le_duracao  # noqa: E402
from nucleo.planejador import tarefas_do_dia  # noqa: E402
from nucleo.servico import Servico  # noqa: E402

ARQUIVO_DADOS = PASTA_APP / "dados.db"


def _linha(t) -> str:
    extras = [formata_minutos(t.minutos)]
    if t.prazo:
        extras.append(f"até {formata_dia(t.prazo)}")
    if t.data_fixa:
        extras.append("data fixa")
    if t.projeto:
        extras.append(f"#{t.projeto}")
    if t.adiamentos:
        extras.append(f"adiada {t.adiamentos}x")
    if t.conflito:
        extras.append({"nao_cabe": "NÃO CABE ATÉ O PRAZO", "prazo_vencido": "PRAZO VENCIDO",
                       "maior_que_dia": "MAIOR QUE UM DIA"}[t.conflito])
    return f"  [{t.id:>3}] {t.titulo}  ({' · '.join(extras)})"


def mostrar_dias(sv: Servico, quantidade: int):
    cal = sv.calendario()
    tarefas = sv.banco.tarefas("aberta")
    reservas = sv.reservas()
    for d in cal.dias_de_trabalho(sv.hoje(), quantidade):
        do_dia = tarefas_do_dia(tarefas, d)
        usado = sum(t.minutos for t in do_dia) + reservas.get(d, 0)
        nome = sv.nome_dia(d)
        titulo = nome if nome.startswith(formata_dia(d)) else f"{nome} · {formata_dia(d)}"
        print(f"\n{titulo} — {formata_minutos(usado)} de {formata_minutos(cal.capacidade(d))}")
        for a in sv.banco.aguardando("aberto"):
            if max(a.cobrar_em, sv.hoje()) == d:
                print(f"  [COBRAR] {a.pessoa}: {a.o_que} (5min)")
        for t in do_dia:
            print(_linha(t))
        if not do_dia:
            print("  (livre)")
    sem = [t for t in tarefas if t.dia_planejado is None]
    if sem:
        print("\nSem data por enquanto:")
        for t in sem:
            print(_linha(t))


def _manutencao(cmd: str, args: list[str]) -> int:
    import instalacao
    if cmd == "verificar":
        itens = instalacao.verificar(PASTA_APP)
        print(instalacao.texto_verificacao(itens))
        return 0 if all(i.ok for i in itens) else 1
    if cmd == "resetar-mini":
        print(instalacao.resetar_mini_barra(ARQUIVO_DADOS))
        return 0
    if cmd == "atalho":
        ok, msg = instalacao.criar_atalho(PASTA_APP, "Desktop")
    elif args and args[0].lower() in ("sim", "s", "on"):
        ok, msg = instalacao.criar_atalho(PASTA_APP, "Startup")
    elif args and args[0].lower() in ("nao", "não", "n", "off"):
        ok, msg = instalacao.remover_inicializar()
    else:
        print("Inicia com o Windows: " + ("sim" if instalacao.inicia_com_windows() else "não")
              + "\nUse: python app.py iniciar-com-windows sim|nao")
        return 0
    print(msg)
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd in ("verificar", "atalho", "iniciar-com-windows", "resetar-mini"):
        return _manutencao(cmd, argv[2:])
    if cmd == "":
        try:
            from ui.aplicacao import iniciar
        except ImportError as erro:
            print(f"Interface indisponível ({erro}).\nInstale com: pip install -r requirements.txt\n"
                  "Enquanto isso, use a linha de comando: python app.py hoje\n")
            cmd = "hoje"
        else:
            return iniciar(ARQUIVO_DADOS, PASTA_APP)
    banco = Banco(ARQUIVO_DADOS)
    sv = Servico(banco, PASTA_APP)
    if cmd == "hoje":
        r = sv.abrir_o_dia()
        if r:
            print(r.mensagem)
        mostrar_dias(sv, 3)
    elif cmd == "semana":
        sv.abrir_o_dia()
        mostrar_dias(sv, sv.config().horizonte_dias)
    elif cmd == "nova" and len(argv) > 2:
        print(sv.capturar(" ".join(argv[2:])).mensagem)
    elif cmd == "prever" and len(argv) > 2:
        print("Entendi:", sv.prever(" ".join(argv[2:])))
    elif cmd == "feito" and len(argv) > 2:
        print(sv.concluir(int(argv[2])).mensagem)
    elif cmd == "adiar" and len(argv) > 2:
        r = sv.adiar(int(argv[2]), " ".join(argv[3:]) or None)
        print(r.mensagem)
    elif cmd == "decidir" and len(argv) > 3:
        print(sv.decidir(int(argv[2]), argv[3]).mensagem)
    elif cmd == "horas" and len(argv) > 3:
        dia = le_dia(argv[2], date.today())
        minutos = le_duracao(argv[3], aceitar_numero=True)
        if not dia or minutos is None:
            print("Use: python app.py horas 29/10 2h")
            return 1
        print(sv.definir_capacidade(dia, minutos).mensagem)
    else:
        print(__doc__)
        return 1
    banco.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
