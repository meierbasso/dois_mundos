#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera os audios do MVP Dois Mundos usando Microsoft Edge TTS, sem chave."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("ERRO: instale a dependencia com: python -m pip install edge-tts")
    sys.exit(2)

PERSONAGENS = {
    "pt": {
        "nome": "Tuca",
        "voz": "pt-BR-FranciscaNeural",
        "rate": "-12%",
        "pitch": "+6Hz",
        "volume": "+0%",
    },
    "en": {
        "nome": "Robin",
        "voz": "en-US-AndrewNeural",
        "rate": "-12%",
        "pitch": "+4Hz",
        "volume": "+0%",
    },
}

MUNDOS = [
    {
        "id": "animais",
        "nome": {"pt": "os animais", "en": "the animals"},
        "palavras": [
            {"id": "dog", "pt": "cachorro", "en": "dog", "artigo": "o"},
            {"id": "cat", "pt": "gato", "en": "cat", "artigo": "o"},
            {"id": "cow", "pt": "vaca", "en": "cow", "artigo": "a"},
            {"id": "duck", "pt": "pato", "en": "duck", "artigo": "o"},
            {"id": "horse", "pt": "cavalo", "en": "horse", "artigo": "o"},
            {"id": "bird", "pt": "passarinho", "en": "bird", "artigo": "o"},
            {"id": "fish", "pt": "peixe", "en": "fish", "artigo": "o"},
            {"id": "pig", "pt": "porco", "en": "pig", "artigo": "o"},
            {"id": "sheep", "pt": "ovelha", "en": "sheep", "artigo": "a"},
            {"id": "hen", "pt": "galinha", "en": "hen", "artigo": "a"},
        ],
    },
    {
        "id": "cores",
        "nome": {"pt": "as cores", "en": "the colors"},
        "palavras": [
            {"id": "red", "pt": "vermelho", "ptF": "vermelha", "en": "red", "cor": True},
            {"id": "blue", "pt": "azul", "ptF": "azul", "en": "blue", "cor": True},
            {"id": "yellow", "pt": "amarelo", "ptF": "amarela", "en": "yellow", "cor": True},
            {"id": "green", "pt": "verde", "ptF": "verde", "en": "green", "cor": True},
            {"id": "orange", "pt": "laranja", "ptF": "laranja", "en": "orange", "cor": True},
            {"id": "purple", "pt": "roxo", "ptF": "roxa", "en": "purple", "cor": True},
            {"id": "pink", "pt": "rosa", "ptF": "rosa", "en": "pink", "cor": True},
            {"id": "black", "pt": "preto", "ptF": "preta", "en": "black", "cor": True},
            {"id": "white", "pt": "branco", "ptF": "branca", "en": "white", "cor": True},
            {"id": "brown", "pt": "marrom", "ptF": "marrom", "en": "brown", "cor": True},
        ],
    },
    {
        "id": "comidas",
        "nome": {"pt": "as comidas", "en": "the food"},
        "palavras": [
            {"id": "banana", "pt": "banana", "en": "banana", "artigo": "a"},
            {"id": "apple", "pt": "maçã", "en": "apple", "artigo": "a"},
            {"id": "milk", "pt": "leite", "en": "milk", "artigo": "o"},
            {"id": "water", "pt": "água", "en": "water", "artigo": "a"},
            {"id": "bread", "pt": "pão", "en": "bread", "artigo": "o"},
            {"id": "egg", "pt": "ovo", "en": "egg", "artigo": "o"},
            {"id": "rice", "pt": "arroz", "en": "rice", "artigo": "o"},
            {"id": "grape", "pt": "uva", "en": "grape", "artigo": "a"},
            {"id": "cake", "pt": "bolo", "en": "cake", "artigo": "o"},
            {"id": "juice", "pt": "suco", "en": "juice", "artigo": "o"},
        ],
    },
]

FRASES_FIXAS = {
    "bravo": {"pt": "Muito bem!", "en": "Very good!"},
    "ola": {"pt": "Oi! Eu sou o Tuca.", "en": "Hi! I'm Robin."},
    "vamos_ver": {"pt": "Vamos ver", "en": "Let's see"},
    "cantar": {"pt": "Vamos cantar!", "en": "Let's sing!"},
    "tchau": {"pt": "Até amanhã!", "en": "See you tomorrow!"},
}


def pergunta(p, lang):
    if lang == "en":
        return f"Where is the {p['en']} one?" if p.get("cor") else f"Where is the {p['en']}?"
    if p.get("cor"):
        return f"Cadê a cor {p.get('ptF', p['pt'])}?"
    return f"Cadê {p.get('artigo', 'o')} {p['pt']}?"


def construir_tarefas(amostra=False):
    tarefas = []
    for mundo in MUNDOS:
        for lang in ("pt", "en"):
            tarefas.append((lang, f"w_{mundo['id']}", mundo["nome"][lang], False))
        for p in mundo["palavras"]:
            for lang in ("pt", "en"):
                tarefas.append((lang, p["id"], p[lang], True))
                tarefas.append((lang, f"q_{p['id']}", pergunta(p, lang), False))
    for chave, textos in FRASES_FIXAS.items():
        for lang in ("pt", "en"):
            tarefas.append((lang, chave, textos[lang], False))
    if amostra:
        tarefas = [t for t in tarefas if t[1] in ("dog", "q_dog", "bravo")]
    return tarefas


async def listar_vozes():
    vozes = await edge_tts.list_voices()
    for v in sorted(vozes, key=lambda x: (x.get("Locale", ""), x.get("ShortName", ""))):
        if v.get("Locale", "").startswith(("pt-BR", "en-US")):
            print(f"{v['Locale']:<7} {v['ShortName']:<42} {v.get('Gender', '')}")


async def gerar_um(texto, cfg, destino, enfase=False):
    rate = "-20%" if enfase else cfg["rate"]
    volume = "+10%" if enfase else cfg["volume"]
    comunicador = edge_tts.Communicate(
        text=texto,
        voice=cfg["voz"],
        rate=rate,
        pitch=cfg["pitch"],
        volume=volume,
    )
    await comunicador.save(str(destino))


async def executar(args):
    if args.listar_vozes:
        await listar_vozes()
        return 0

    raiz = Path(args.saida)
    for lang in ("pt", "en"):
        (raiz / lang).mkdir(parents=True, exist_ok=True)

    tarefas = construir_tarefas(args.amostra)
    manifesto = {
        "versao": 1,
        "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "motor": "edge-tts",
        "vozes": {lang: PERSONAGENS[lang]["voz"] for lang in ("pt", "en")},
        "arquivos": {},
    }

    print(f"Vozes: PT={PERSONAGENS['pt']['voz']}  EN={PERSONAGENS['en']['voz']}")
    print(f"{len(tarefas)} arquivos a processar em {raiz.resolve()}\n")

    gerados = pulados = falhas = 0
    for i, (lang, nome, texto, enfase) in enumerate(tarefas, 1):
        destino = raiz / lang / f"{nome}.mp3"
        manifesto["arquivos"][f"{lang}/{nome}"] = texto
        if destino.exists() and not args.forcar:
            pulados += 1
            print(f"[{i:3}/{len(tarefas)}] - {lang}/{nome}.mp3 já existe")
            continue
        try:
            await gerar_um(texto, PERSONAGENS[lang], destino, enfase)
            gerados += 1
            print(f"[{i:3}/{len(tarefas)}] OK {lang}/{nome}.mp3  '{texto}'")
        except Exception as exc:
            falhas += 1
            destino.unlink(missing_ok=True)
            print(f"[{i:3}/{len(tarefas)}] ERRO {lang}/{nome}.mp3: {exc}")

    (raiz / "manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nGerados: {gerados} | já existiam: {pulados} | falhas: {falhas}")
    print(f"Manifesto: {(raiz / 'manifest.json').resolve()}")
    return 0 if falhas == 0 else 1


def main():
    ap = argparse.ArgumentParser(description="Gera o banco de vozes do Dois Mundos sem chave Azure.")
    ap.add_argument("--saida", default="audio", help="pasta de saída, padrão: audio")
    ap.add_argument("--forcar", action="store_true", help="regrava arquivos existentes")
    ap.add_argument("--amostra", action="store_true", help="gera somente dog, q_dog e bravo")
    ap.add_argument("--listar-vozes", action="store_true", help="lista vozes pt-BR e en-US")
    args = ap.parse_args()
    return asyncio.run(executar(args))


if __name__ == "__main__":
    sys.exit(main())
