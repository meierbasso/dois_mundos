#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 DOIS MUNDOS — gerador de banco de vozes com IA (Azure AI Speech)
===============================================================================
Gera TODOS os arquivos de voz do MVP com vozes neurais e grava em ./audio/,
exatamente na estrutura que o protótipo (dois-mundos-prototipo-v2.html) espera:

    audio/
      pt/  dog.mp3  cat.mp3 ... q_dog.mp3 ... w_animais.mp3  bravo.mp3
      en/  dog.mp3  cat.mp3 ... q_dog.mp3 ... w_animais.mp3  bravo.mp3
      manifest.json

Assim que a pasta existir ao lado do HTML, o app passa a usar os arquivos
gravados e ignora a voz do sistema. Nenhuma mudança de código é necessária.

-------------------------------------------------------------------------------
PRÉ-REQUISITOS
    pip install azure-cognitiveservices-speech
    export AZURE_SPEECH_KEY="sua-chave"
    export AZURE_SPEECH_REGION="brazilsouth"

USO
    python gerar_audio_azure.py                 # gera tudo o que falta
    python gerar_audio_azure.py --forcar        # regrava tudo
    python gerar_audio_azure.py --amostra       # grava só 6 arquivos, p/ testar vozes
    python gerar_audio_azure.py --listar-vozes  # mostra as vozes disponíveis na região

OBSERVAÇÃO DE PRODUTO
    A especificação do MVP pede locução humana em estúdio. Vozes neurais são
    um substituto muito bom para o protótipo e para o beta, mas a decisão de
    usá-las no produto final deve ser consciente: o ponto sensível é o inglês,
    que a criança vai imitar. Grave uma amostra e ouça com fones antes.
===============================================================================
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ------------------------------------------------------------------------------
# 1. VOZES
#    Nomes conforme o catálogo de vozes neurais do Azure AI Speech.
#    Troque livremente: o campo "voz" aceita qualquer nome do catálogo da região.
#    Regra de ouro do produto (OPOL): uma voz por personagem, nunca misturar.
# ------------------------------------------------------------------------------
PERSONAGENS = {
    "pt": {
        "nome": "Tuca",
        "voz": "pt-BR-FranciscaNeural",   # alternativas: pt-BR-GiovannaNeural, pt-BR-LeticiaNeural
        "locale": "pt-BR",
        "rate": "-12%",                   # ~15% mais devagar que a fala adulta (seção 8.2 da spec)
        "pitch": "+6%",
        "estilo": None,                   # algumas vozes aceitam: "cheerful", "friendly"
    },
    "en": {
        "nome": "Robin",
        "voz": "en-US-AndrewNeural",      # alternativas: en-US-EmmaMultilingualNeural
        "locale": "en-US",
        "rate": "-12%",
        "pitch": "+4%",
        "estilo": None,
    },
}

# ------------------------------------------------------------------------------
# 2. CONTEÚDO — espelha o manifesto do protótipo (30 palavras, 3 mundos)
# ------------------------------------------------------------------------------
MUNDOS = [
    {
        "id": "animais",
        "nome": {"pt": "os animais", "en": "the animals"},
        "palavras": [
            {"id": "dog",   "pt": "cachorro",   "en": "dog",   "artigo": "o"},
            {"id": "cat",   "pt": "gato",       "en": "cat",   "artigo": "o"},
            {"id": "cow",   "pt": "vaca",       "en": "cow",   "artigo": "a"},
            {"id": "duck",  "pt": "pato",       "en": "duck",  "artigo": "o"},
            {"id": "horse", "pt": "cavalo",     "en": "horse", "artigo": "o"},
            {"id": "bird",  "pt": "passarinho", "en": "bird",  "artigo": "o"},
            {"id": "fish",  "pt": "peixe",      "en": "fish",  "artigo": "o"},
            {"id": "pig",   "pt": "porco",      "en": "pig",   "artigo": "o"},
            {"id": "sheep", "pt": "ovelha",     "en": "sheep", "artigo": "a"},
            {"id": "hen",   "pt": "galinha",    "en": "hen",   "artigo": "a"},
        ],
    },
    {
        "id": "cores",
        "nome": {"pt": "as cores", "en": "the colors"},
        "palavras": [
            {"id": "red",    "pt": "vermelho", "ptF": "vermelha", "en": "red",    "cor": True},
            {"id": "blue",   "pt": "azul",     "ptF": "azul",     "en": "blue",   "cor": True},
            {"id": "yellow", "pt": "amarelo",  "ptF": "amarela",  "en": "yellow", "cor": True},
            {"id": "green",  "pt": "verde",    "ptF": "verde",    "en": "green",  "cor": True},
            {"id": "orange", "pt": "laranja",  "ptF": "laranja",  "en": "orange", "cor": True},
            {"id": "purple", "pt": "roxo",     "ptF": "roxa",     "en": "purple", "cor": True},
            {"id": "pink",   "pt": "rosa",     "ptF": "rosa",     "en": "pink",   "cor": True},
            {"id": "black",  "pt": "preto",    "ptF": "preta",    "en": "black",  "cor": True},
            {"id": "white",  "pt": "branco",   "ptF": "branca",   "en": "white",  "cor": True},
            {"id": "brown",  "pt": "marrom",   "ptF": "marrom",   "en": "brown",  "cor": True},
        ],
    },
    {
        "id": "comidas",
        "nome": {"pt": "as comidas", "en": "the food"},
        "palavras": [
            {"id": "banana", "pt": "banana", "en": "banana", "artigo": "a"},
            {"id": "apple",  "pt": "maçã",   "en": "apple",  "artigo": "a"},
            {"id": "milk",   "pt": "leite",  "en": "milk",   "artigo": "o"},
            {"id": "water",  "pt": "água",   "en": "water",  "artigo": "a"},
            {"id": "bread",  "pt": "pão",    "en": "bread",  "artigo": "o"},
            {"id": "egg",    "pt": "ovo",    "en": "egg",    "artigo": "o"},
            {"id": "rice",   "pt": "arroz",  "en": "rice",   "artigo": "o"},
            {"id": "grape",  "pt": "uva",    "en": "grape",  "artigo": "a"},
            {"id": "cake",   "pt": "bolo",   "en": "cake",   "artigo": "o"},
            {"id": "juice",  "pt": "suco",   "en": "juice",  "artigo": "o"},
        ],
    },
]

FRASES_FIXAS = {
    "bravo":      {"pt": "Muito bem!",       "en": "Very good!"},
    "ola":        {"pt": "Oi! Eu sou o Tuca.", "en": "Hi! I'm Robin."},
    "vamos_ver":  {"pt": "Vamos ver",        "en": "Let's see"},
    "cantar":     {"pt": "Vamos cantar!",    "en": "Let's sing!"},
    "tchau":      {"pt": "Até amanhã!",      "en": "See you tomorrow!"},
}


def pergunta(p, lang):
    """Monta a frase do bloco 2, com artigo correto em português."""
    if lang == "en":
        if p.get("cor"):
            return f"Where is the {p['en']} one?"
        return f"Where is the {p['en']}?"
    if p.get("cor"):
        # concordância de gênero: "a cor vermelha", não "a cor vermelho"
        return f"Cadê a cor {p.get('ptF', p['pt'])}?"
    return f"Cadê {p.get('artigo', 'o')} {p['pt']}?"


def construir_tarefas(amostra=False):
    """Lista de (lang, id_arquivo, texto, pausa_enfase)."""
    tarefas = []
    for mundo in MUNDOS:
        for lang in ("pt", "en"):
            tarefas.append((lang, f"w_{mundo['id']}", mundo["nome"][lang], False))
        for p in mundo["palavras"]:
            for lang in ("pt", "en"):
                # a palavra isolada leva ênfase: é o item que a criança vai imitar
                tarefas.append((lang, p["id"], p[lang], True))
                tarefas.append((lang, f"q_{p['id']}", pergunta(p, lang), False))
    for chave, txt in FRASES_FIXAS.items():
        for lang in ("pt", "en"):
            tarefas.append((lang, chave, txt[lang], False))
    if amostra:
        tarefas = [t for t in tarefas if t[1] in ("dog", "q_dog", "bravo")]
    return tarefas


def ssml(texto, cfg, enfase=False):
    """
    SSML com prosódia infantil:
      - fala desacelerada, sem distorcer entonação
      - 300 ms de silêncio limpo no início e no fim (exigência da spec)
      - palavra isolada sai um pouco mais devagar e mais alta
    """
    rate = "-20%" if enfase else cfg["rate"]
    volume = "+10%" if enfase else "+0%"
    corpo = (
        f'<prosody rate="{rate}" pitch="{cfg["pitch"]}" volume="{volume}">'
        f"{texto}</prosody>"
    )
    if cfg.get("estilo"):
        corpo = (
            f'<mstts:express-as style="{cfg["estilo"]}" styledegree="1.1">'
            f"{corpo}</mstts:express-as>"
        )
    return (
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" '
        f'xml:lang="{cfg["locale"]}">'
        f'<voice name="{cfg["voz"]}">'
        '<break time="300ms"/>'
        f"{corpo}"
        '<break time="300ms"/>'
        "</voice></speak>"
    )


def listar_vozes(key, region):
    import azure.cognitiveservices.speech as speechsdk
    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    sintetizador = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
    resultado = sintetizador.get_voices_async().get()
    if resultado.reason != speechsdk.ResultReason.VoicesListRetrieved:
        print("Não foi possível listar as vozes:", resultado.error_details)
        return 1
    for v in sorted(resultado.voices, key=lambda x: x.locale):
        if v.locale.startswith(("pt-BR", "en-US")):
            estilos = ", ".join(v.style_list) if v.style_list else "—"
            print(f"{v.locale:<7} {v.short_name:<42} estilos: {estilos}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Gera o banco de vozes do Dois Mundos.")
    ap.add_argument("--saida", default="audio", help="pasta de saída (padrão: audio)")
    ap.add_argument("--forcar", action="store_true", help="regrava arquivos existentes")
    ap.add_argument("--amostra", action="store_true", help="grava poucos arquivos para teste")
    ap.add_argument("--listar-vozes", action="store_true", help="lista vozes da região e sai")
    args = ap.parse_args()

    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        print("ERRO: defina AZURE_SPEECH_KEY e AZURE_SPEECH_REGION no ambiente.")
        return 2

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        print("ERRO: pip install azure-cognitiveservices-speech")
        return 2

    if args.listar_vozes:
        return listar_vozes(key, region)

    raiz = Path(args.saida)
    for lang in ("pt", "en"):
        (raiz / lang).mkdir(parents=True, exist_ok=True)

    tarefas = construir_tarefas(amostra=args.amostra)
    print(f"Vozes: PT={PERSONAGENS['pt']['voz']}  EN={PERSONAGENS['en']['voz']}")
    print(f"{len(tarefas)} arquivos a processar em {raiz.resolve()}\n")

    gerados = pulados = falhas = 0
    manifesto = {"versao": 1, "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "vozes": {l: PERSONAGENS[l]["voz"] for l in ("pt", "en")},
                 "arquivos": {}}

    for i, (lang, nome, texto, enfase) in enumerate(tarefas, 1):
        destino = raiz / lang / f"{nome}.mp3"
        manifesto["arquivos"][f"{lang}/{nome}"] = texto
        if destino.exists() and not args.forcar:
            pulados += 1
            continue

        cfg = PERSONAGENS[lang]
        speech_cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_cfg.speech_synthesis_voice_name = cfg["voz"]
        # 48 kHz / 96 kbps: qualidade folgada para voz, arquivo pequeno
        speech_cfg.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio48Khz96KBitRateMonoMp3
        )
        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=str(destino))
        sintetizador = speechsdk.SpeechSynthesizer(
            speech_config=speech_cfg, audio_config=audio_cfg
        )

        resultado = sintetizador.speak_ssml_async(ssml(texto, cfg, enfase)).get()
        if resultado.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            gerados += 1
            print(f"[{i:3}/{len(tarefas)}] ✓ {lang}/{nome}.mp3  “{texto}”")
        else:
            falhas += 1
            detalhe = ""
            if resultado.reason == speechsdk.ResultReason.Canceled:
                c = resultado.cancellation_details
                detalhe = f"{c.reason} — {c.error_details}"
            print(f"[{i:3}/{len(tarefas)}] ✗ {lang}/{nome}.mp3  {detalhe}")
            if destino.exists():
                destino.unlink()

    (raiz / "manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nGerados: {gerados} | já existiam: {pulados} | falhas: {falhas}")
    print(f"Manifesto: {(raiz / 'manifest.json').resolve()}")
    if gerados:
        print("\nColoque a pasta 'audio/' ao lado do HTML e sirva por HTTP:")
        print("    python -m http.server 8000")
        print("    http://localhost:8000/dois-mundos-prototipo-v2.html")
        print("(abrir o HTML por file:// bloqueia o carregamento dos arquivos)")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
