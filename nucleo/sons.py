"""Sons dos avisos, gerados na hora (sem arquivos de áudio no app).

Cada som é um WAV curto (mono, 16 bits, 22 050 Hz) montado com senoides e envelope de decaimento.
"""
from __future__ import annotations

import io
import math
import struct
import wave

TAXA = 22_050
SONS = ("Suave", "Sino", "Bipe", "Desligado")

# (frequência Hz, início s, duração s, volume 0–1, harmônicos)
_NOTAS = {
    "Suave": [(659.25, 0.00, 0.55, 0.35, ()), (880.00, 0.22, 0.75, 0.30, ())],
    "Sino": [(1046.5, 0.00, 1.60, 0.40, ((2.76, 0.35), (5.40, 0.15))),
             (1318.5, 0.35, 1.40, 0.25, ((2.76, 0.30),))],
    "Bipe": [(1000.0, 0.00, 0.12, 0.30, ((3.0, 0.20),)), (1000.0, 0.20, 0.12, 0.30, ((3.0, 0.20),))],
}


def amostras(nome: str) -> list[float]:
    """Valores entre -1 e 1. 'Desligado' ou nome desconhecido devolve lista vazia."""
    notas = _NOTAS.get(nome)
    if not notas:
        return []
    total = max(ini + dur for _, ini, dur, _, _ in notas) + 0.05
    sinal = [0.0] * int(total * TAXA)
    for freq, ini, dur, vol, harm in notas:
        i0, n = int(ini * TAXA), int(dur * TAXA)
        ataque = int(0.008 * TAXA)
        for k in range(n):
            t = k / TAXA
            env = min(1.0, k / ataque) * math.exp(-4.0 * t / dur)
            v = math.sin(2 * math.pi * freq * t)
            for mult, peso in harm:
                v += peso * math.sin(2 * math.pi * freq * mult * t)
            sinal[i0 + k] += vol * env * v
    pico = max(1.0, max(abs(x) for x in sinal))
    return [x / pico for x in sinal]


def gerar_wav(nome: str) -> bytes:
    """O som em formato WAV (bytes). 'Desligado' gera um WAV vazio válido."""
    dados = amostras(nome)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32000)) for x in dados))
    return buf.getvalue()
