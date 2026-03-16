"""
Morse Code Trainer
Spustit: python morse_trainer.py
Ovladani: píšeš odpověď + Enter, 'r' = přehrát znovu, 'q' = konec, '+'/'-' = více/méně písmen
"""

import sys
import random
import time
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("Chybi knihovna sounddevice. Spust: pip install sounddevice numpy")
    sys.exit(1)

# ── Nastavení ──────────────────────────────────────────────────────────────────

WPM        = 20       # rychlost (Words Per Minute)
FARNSWORTH = 10       # efektivní WPM pro mezery (Farnsworth metoda, < WPM = delší mezery)
FREQ       = 600      # tón v Hz
SAMPLE_RATE = 44100

GROUP_SIZE = 3        # výchozí počet písmen ve skupině

# Písmena LCWO lekcí (první lekce = KM, postupně přibývají)
LESSONS = [
    "KM", "KMR", "KMRS", "KMRSU", "KMRSUA",
    "KMRSUAP", "KMRSUAPT", "KMRSUAPTL",
    "KMRSUAPTLO", "KMRSUAPTLOW",
    "KMRSUAPTLOWI", "KMRSUAPTLOWINE",
    "KMRSUAPTLOWINES", "KMRSUAPTLOWINESD",
    "KMRSUAPTLOWINESD" + "BGF",
    "KMRSUAPTLOWINESD" + "BGFHV",
    "KMRSUAPTLOWINESD" + "BGFHVZ",
    "KMRSUAPTLOWINESD" + "BGFHVZYQ",
    "KMRSUAPTLOWINESD" + "BGFHVZYQCX",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # všechna písmena
]

# ── Morseovka ──────────────────────────────────────────────────────────────────

MORSE = {
    'A': '.-',   'B': '-...', 'C': '-.-.', 'D': '-..',
    'E': '.',    'F': '..-.', 'G': '--.',  'H': '....',
    'I': '..',   'J': '.---', 'K': '-.-',  'L': '.-..',
    'M': '--',   'N': '-.',   'O': '---',  'P': '.--.',
    'Q': '--.-', 'R': '.-.',  'S': '...',  'T': '-',
    'U': '..-',  'V': '...-', 'W': '.--',  'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '0': '-----','1': '.----','2': '..---','3': '...--',
    '4': '....-','5': '.....','6': '-....','7': '--...',
    '8': '---..','9': '----.',
}

def dit_duration(wpm):
    """Délka tečky v sekundách pro dané WPM."""
    return 1.2 / wpm

def tone(duration, freq=FREQ, sr=SAMPLE_RATE, fade_ms=5):
    """Vygeneruje tón jako numpy array."""
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t).astype(np.float32)
    # fade in/out aby se zabránilo cvaknutí
    fade = int(sr * fade_ms / 1000)
    fade = min(fade, samples // 2)
    if fade > 0:
        wave[:fade]  *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
    return wave

def silence(duration, sr=SAMPLE_RATE):
    return np.zeros(int(sr * duration), dtype=np.float32)

def play_morse(text, wpm=WPM, farnsworth=FARNSWORTH, freq=FREQ):
    """Přehraje morseovku pro zadaný text."""
    dit = dit_duration(wpm)
    dah = dit * 3
    # Farnsworth: mezery jsou delší (pomalejší efektivní rychlost)
    fw_dit = dit_duration(farnsworth)
    intra = dit          # mezera mezi tečkami/čárkami uvnitř písmene
    inter = fw_dit * 3   # mezera mezi písmeny
    word  = fw_dit * 7   # mezera mezi slovy (zde mezi skupinami)

    audio_parts = []
    for i, char in enumerate(text.upper()):
        if char == ' ':
            audio_parts.append(silence(word))
            continue
        code = MORSE.get(char)
        if code is None:
            continue
        for j, symbol in enumerate(code):
            if symbol == '.':
                audio_parts.append(tone(dit, freq=freq))
            elif symbol == '-':
                audio_parts.append(tone(dah, freq=freq))
            if j < len(code) - 1:
                audio_parts.append(silence(intra))
        if i < len(text) - 1:
            audio_parts.append(silence(inter))

    if audio_parts:
        audio = np.concatenate(audio_parts)
        sd.play(audio, samplerate=SAMPLE_RATE)
        sd.wait()

# ── Herní logika ───────────────────────────────────────────────────────────────

def random_group(charset, size):
    return ''.join(random.choices(charset, k=size))

def print_stats(correct, total):
    if total == 0:
        return
    pct = 100 * correct / total
    bar_len = 20
    filled = int(bar_len * correct / total)
    bar = '█' * filled + '░' * (bar_len - filled)
    print(f"  [{bar}] {correct}/{total} ({pct:.0f}%)")

def main():
    print()
    print("  morse_trainer.py  |  wpm:{} fw:{} freq:{}Hz".format(WPM, FARNSWORTH, FREQ))
    print("  ─────────────────────────────────────────────")
    print("  Příkazy: 'r' = znovu, '+'/'-' = velikost skupiny, 'l' = lekce, 'q' = konec")
    print()

    # Vyber lekci
    print("  Lekce (1–{}) – zadej číslo lekce [výchozí 1]: ".format(len(LESSONS)), end='', flush=True)
    raw = input().strip()
    lesson_idx = 0
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(LESSONS):
            lesson_idx = n - 1

    charset = LESSONS[lesson_idx]
    group_size = GROUP_SIZE

    correct = 0
    total   = 0
    current_group = random_group(charset, group_size)

    print()
    print("  Lekce {}: [{}]  |  skupina: {} písmen".format(lesson_idx+1, charset, group_size))
    print("  Přehrávám první skupinu…")
    print()

    while True:
        play_morse(current_group)

        print("  > ", end='', flush=True)
        try:
            answer = input().strip().upper()
        except (EOFError, KeyboardInterrupt):
            break

        if answer == 'Q':
            break
        elif answer == 'R':
            print("  ↻ přehrávám znovu")
            continue
        elif answer == '+':
            group_size = min(group_size + 1, 10)
            print("  Skupina: {} písmen".format(group_size))
            current_group = random_group(charset, group_size)
            continue
        elif answer == '-':
            group_size = max(group_size - 1, 1)
            print("  Skupina: {} písmen".format(group_size))
            current_group = random_group(charset, group_size)
            continue
        elif answer == 'L':
            print("  Lekce (1–{}): ".format(len(LESSONS)), end='', flush=True)
            raw = input().strip()
            if raw.isdigit():
                n = int(raw)
                if 1 <= n <= len(LESSONS):
                    lesson_idx = n - 1
                    charset = LESSONS[lesson_idx]
                    print("  Lekce {}: [{}]".format(lesson_idx+1, charset))
            current_group = random_group(charset, group_size)
            continue
        else:
            total += 1
            if answer == current_group:
                correct += 1
                print("  ✓ správně!", end='  ')
            else:
                print("  ✗ bylo: {}".format(current_group), end='  ')
            print_stats(correct, total)
            print()
            current_group = random_group(charset, group_size)

    print()
    print("  ── Konec tréninku ──")
    print_stats(correct, total)
    print()

if __name__ == '__main__':
    main()
