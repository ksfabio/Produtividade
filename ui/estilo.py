"""Cores e folha de estilo (QSS) do app, iguais às do protótipo."""

TINTA = "#1F2328"
TINTA_2 = "#3D444D"
MUTED = "#57606A"
BORDA = "#E1E4E8"
BORDA_FORTE = "#C9CED6"
FUNDO = "#FFFFFF"
FUNDO_SUAVE = "#FAFBFC"
FUNDO_CINZA = "#F4F5F7"
ACENTO = "#2457C5"
ACENTO_ESCURO = "#1B3F91"
ACENTO_CLARO = "#E8EEFB"
ACENTO_BORDA = "#D3DEF6"
LARANJA = "#B45309"
LARANJA_TEXTO = "#8A3B05"
LARANJA_CLARO = "#FFF1DE"
# Aguardando (cobranças e itens esperados de outras pessoas): lilás
COBRAR = "#9C4F96"        # selo "COBRAR HOJE" (texto branco)
COBRAR_FUNDO = "#FBF3FA"  # fundo da linha de cobrança
COBRAR_BORDA = "#D9A9D4"  # borda da linha de cobrança
AGUARDA_TEXTO = "#6E2F69" # textos e selos claros de Aguardando
AGUARDA_CLARO = "#F5E1F2"
VERMELHO = "#B42318"
VERMELHO_TEXTO = "#8F1D14"
VERMELHO_CLARO = "#FDECEA"
VERDE = "#1F7A4D"
VERDE_TEXTO = "#145C39"
VERDE_CLARO = "#E6F4EC"

CORES_AUSENCIA = {
    "Férias": ("#0F766E", "#D5F2EE", "#0B4F4A"),
    "Feriado": ("#6B3FA0", "#EBDDF8", "#4B2A7A"),
    "Ausência": ("#B42318", "#FCE3E1", "#8F1D14"),
    "Meio período": ("#B45309", "#FCEBD3", "#7A3A06"),
    "Dia não útil": ("#57606A", "#EEF0F3", "#3D444D"),
}

FONTE = '"Segoe UI", "Segoe UI Variable", system-ui, sans-serif'

QSS = f"""
* {{ font-family: {FONTE}; font-size: 13px; color: {TINTA}; }}
QMainWindow, QWidget#fundo {{ background: {FUNDO}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit {{
    border: 1px solid {BORDA_FORTE}; border-radius: 6px; padding: 6px 10px; background: {FUNDO};
    selection-background-color: {ACENTO};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateEdit:focus {{ border: 2px solid {ACENTO}; padding: 5px 9px; }}
QLineEdit#captura {{ font-size: 14px; padding: 9px 14px; border-radius: 8px; }}
QLineEdit#captura:focus {{ padding: 8px 13px; }}

QPushButton {{
    border: 1px solid {BORDA_FORTE}; border-radius: 6px; background: {FUNDO};
    padding: 6px 12px; min-height: 20px;
}}
QPushButton:hover {{ background: {FUNDO_CINZA}; }}
QPushButton:focus {{ border: 2px solid {ACENTO}; padding: 5px 11px; }}
QPushButton[tipo="primario"] {{ background: {ACENTO}; color: white; border: none; font-weight: 600; padding: 7px 14px; }}
QPushButton[tipo="primario"]:hover {{ background: {ACENTO_ESCURO}; }}
QPushButton[tipo="link"] {{ border: none; background: transparent; color: {ACENTO}; padding: 2px 0; }}
QPushButton[tipo="link"]:hover {{ text-decoration: underline; }}
QPushButton[tipo="aba"] {{ border: none; border-bottom: 2px solid transparent; border-radius: 0;
    background: transparent; color: {TINTA_2}; font-size: 14px; padding: 12px 14px; }}
QPushButton[tipo="aba"]:checked {{ border-bottom: 2px solid {ACENTO}; color: {ACENTO_ESCURO}; font-weight: 600; }}
QPushButton[tipo="chip"] {{ border-radius: 14px; padding: 4px 12px; }}
QPushButton[tipo="chip"]:checked {{ border: 1px solid {ACENTO}; background: {ACENTO_CLARO}; color: {ACENTO_ESCURO}; font-weight: 600; }}
QPushButton[tipo="concluir"] {{ border: 2px solid #8A929C; border-radius: 11px; min-width: 18px; max-width: 18px;
    min-height: 18px; max-height: 18px; padding: 0; background: {FUNDO}; }}
QPushButton[tipo="concluir"]:hover {{ border-color: {VERDE}; background: {VERDE_CLARO}; }}
QPushButton[tipo="cobrar"] {{ background: {COBRAR}; color: white; border: none; font-weight: 600; }}

QFrame#linhaTarefa {{ border: 1px solid {BORDA}; border-radius: 8px; background: {FUNDO}; }}
QFrame#linhaTarefa:hover {{ border-color: {BORDA_FORTE}; background: {FUNDO_SUAVE}; }}
QFrame#linhaTarefa[selecionada="true"] {{ border: 2px solid {ACENTO}; }}
QFrame#linhaCobranca {{ border: 2px solid {COBRAR_BORDA}; border-radius: 8px; background: {COBRAR_FUNDO}; }}
QFrame#cartao {{ border: 1px solid {BORDA}; border-radius: 10px; background: {FUNDO}; }}
QFrame#colunaDia {{ border: 1px solid {BORDA}; border-radius: 10px; background: {FUNDO_SUAVE}; }}
QFrame#colunaHoje {{ border: 2px solid {ACENTO_BORDA}; border-radius: 10px; background: {FUNDO_SUAVE}; }}
QFrame#sugestao {{ border: 1px solid {ACENTO_BORDA}; border-radius: 8px; background: #F3F6FD; }}
QFrame#conflito {{ border: 1px solid #F5C2BC; border-radius: 8px; background: {VERMELHO_CLARO}; }}
QFrame#faltaFazer {{ border: 1px solid {ACENTO_BORDA}; border-radius: 8px; background: #F3F6FD; }}
QFrame#painel {{ border: none; border-left: 1px solid {BORDA}; background: {FUNDO}; }}
QFrame#barraTopo {{ border: none; border-bottom: 1px solid {BORDA}; background: {FUNDO}; }}
QFrame#aviso {{ border-radius: 10px; background: {TINTA}; }}
QFrame#aviso QLabel {{ color: white; font-size: 14px; }}
QFrame#aviso QPushButton {{ color: white; background: transparent; border: 1px solid #8A929C; }}
QFrame#aviso QPushButton:hover {{ background: #2B3137; }}

QLabel[papel="titulo"] {{ font-size: 22px; font-weight: 700; }}
QLabel[papel="subtitulo"] {{ font-size: 13px; color: {MUTED}; }}
QLabel[papel="secao"] {{ font-size: 15px; font-weight: 700; }}
QLabel[papel="meta"] {{ font-size: 12px; color: {MUTED}; }}
QLabel[papel="rotulo"] {{ font-size: 11px; font-weight: 700; color: {MUTED}; }}
QLabel[papel="tituloTarefa"] {{ font-size: 14px; font-weight: 600; }}
QLabel[papel="previa"] {{ font-size: 12px; color: {ACENTO_ESCURO}; }}
"""


def selo(texto: str, cor_texto: str, cor_fundo: str, borda: str | None = None) -> str:
    """CSS de um selo (pílula) para QLabel."""
    b = f"border: 1px solid {borda};" if borda else "border: none;"
    return (f"QLabel {{ color: {cor_texto}; background: {cor_fundo}; {b} border-radius: 9px; "
            f"padding: 2px 8px; font-size: 11px; font-weight: 700; }}")
