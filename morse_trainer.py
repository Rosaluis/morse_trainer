"""
Morse Code Trainer
Spustit: python morse_trainer.py
Ovládání: píšeš odpověď + Enter
  r       = přehrát znovu
  +/-     = více/méně písmen ve skupině
  l       = změna lekce
  s       = zobrazit statistiky písmen
  q       = konec a uložit
"""

import sys
import os
import json
import random
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("Chybí knihovna sounddevice. Spusť: pip install sounddevice numpy")
    sys.exit(1)

# ── Nastavení ──────────────────────────────────────────────────────────────────

WPM         = 20      # rychlost signálu (Words Per Minute)
FARNSWORTH  = 10      # efektivní WPM pro mezery (< WPM = delší mezery)
FREQ        = 600     # tón v Hz
SAMPLE_RATE = 44100

GROUP_SIZE  = 3       # výchozí počet písmen ve skupině

# Váha adaptivního tréninku: kolikrát více se objeví písmeno s 0% úspěšností
# oproti písmenu se 100% úspěšností
ADAPTIVE_WEIGHT_MAX = 5.0

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morse_progress.json")

# Písmena LCWO lekcí
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
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
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
    return 1.2 / wpm

def tone(duration, freq=FREQ, sr=SAMPLE_RATE, fade_ms=5):
    samples = int(sr * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t).astype(np.float32)
    fade = int(sr * fade_ms / 1000)
    fade = min(fade, samples // 2)
    if fade > 0:
        wave[:fade]  *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
    return wave

def silence(duration, sr=SAMPLE_RATE):
    return np.zeros(int(sr * duration), dtype=np.float32)

def play_morse(text, wpm=WPM, farnsworth=FARNSWORTH, freq=FREQ):
    dit    = dit_duration(wpm)
    dah    = dit * 3
    fw_dit = dit_duration(farnsworth)
    intra  = dit
    inter  = fw_dit * 3
    word   = fw_dit * 7

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
        audio = np.concatenate([audio, silence(0.2)])
        sd.play(audio, samplerate=SAMPLE_RATE)
        sd.wait()

# ── Persistence ────────────────────────────────────────────────────────────────

def load_progress():
    default = {
        "lesson_idx": 0,
        "group_size": GROUP_SIZE,
        "stats": {}
    }
    if not os.path.exists(SAVE_FILE):
        return default
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in default.items():
            data.setdefault(k, v)
        return data
    except Exception:
        print("  ⚠ Nepodařilo se načíst progress, začínám znovu.")
        return default

def save_progress(lesson_idx, group_size, stats):
    data = {
        "lesson_idx": lesson_idx,
        "group_size": group_size,
        "stats": stats
    }
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ Nepodařilo se uložit progress: {e}")

# ── Statistiky ─────────────────────────────────────────────────────────────────

def update_stats(stats, group, answer):
    """Zaznamená výsledek pro každé písmeno ve skupině zvlášť."""
    for i, letter in enumerate(group):
        if letter not in stats:
            stats[letter] = {"ok": 0, "fail": 0}
        if i < len(answer) and answer[i] == letter:
            stats[letter]["ok"] += 1
        else:
            stats[letter]["fail"] += 1

def letter_accuracy(stats, letter):
    s = stats.get(letter)
    if not s:
        return None
    total = s["ok"] + s["fail"]
    if total == 0:
        return None
    return s["ok"] / total

def print_letter_stats(stats, charset):
    print()
    print("  ── Statistiky písmen ──────────────────────────────")
    for letter in sorted(charset):
        s = stats.get(letter)
        if not s:
            print(f"  {letter}  —  bez záznamu")
            continue
        total = s["ok"] + s["fail"]
        pct   = 100 * s["ok"] / total if total else 0
        filled = int(pct / 5)
        bar   = '█' * filled + '░' * (20 - filled)
        print(f"  {letter}  [{bar}] {pct:5.1f}%  ({s['ok']}/{total})")
    print("  ───────────────────────────────────────────────────")
    print()

# ── Adaptivní výběr ────────────────────────────────────────────────────────────

def adaptive_group(charset, size, stats):
    """
    Vybere písmena s váhami podle chybovosti.
    Nová písmena a ta s nízkou úspěšností se objevují častěji.
    """
    weights = []
    for letter in charset:
        acc = letter_accuracy(stats, letter)
        if acc is None:
            w = (ADAPTIVE_WEIGHT_MAX + 1.0) / 2
        else:
            w = 1.0 + (ADAPTIVE_WEIGHT_MAX - 1.0) * (1.0 - acc)
        weights.append(w)
    return random.choices(charset, weights=weights, k=size)

# ── Hlavní smyčka ──────────────────────────────────────────────────────────────

def print_stats_bar(correct, total):
    if total == 0:
        return
    pct    = 100 * correct / total
    filled = int(20 * correct / total)
    bar    = '█' * filled + '░' * (20 - filled)
    print(f"  [{bar}] {correct}/{total} ({pct:.0f}%)")

def main():
    progress   = load_progress()
    lesson_idx = progress["lesson_idx"]
    group_size = progress["group_size"]
    stats      = progress["stats"]

    print()
    print("  morse_trainer.py  |  wpm:{} fw:{} freq:{}Hz".format(WPM, FARNSWORTH, FREQ))
    print("  ───────────────────────────────────────────────────────")
    print("  Příkazy: r = znovu  +/- = skupina  l = lekce  s = stats  q = konec")
    print()

    if os.path.exists(SAVE_FILE):
        print(f"  ↺ Načten progress: lekce {lesson_idx+1}, skupina {group_size} písmen")
    else:
        print("  Nový trénink — žádný uložený progress.")
    print()

    # Volba lekce při startu
    print("  Lekce (1–{}) [uložená: {}]: ".format(len(LESSONS), lesson_idx+1), end='', flush=True)
    raw = input().strip()
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(LESSONS):
            lesson_idx = n - 1

    charset = list(LESSONS[lesson_idx])

    correct       = 0
    total         = 0
    current_group = ''.join(adaptive_group(charset, group_size, stats))

    print()
    print("  Lekce {}: [{}]  |  skupina: {} písmen  |  adaptivní trénink: ZAP".format(
        lesson_idx+1, LESSONS[lesson_idx], group_size))
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
            current_group = ''.join(adaptive_group(charset, group_size, stats))
            continue

        elif answer == '-':
            group_size = max(group_size - 1, 1)
            print("  Skupina: {} písmen".format(group_size))
            current_group = ''.join(adaptive_group(charset, group_size, stats))
            continue

        elif answer == 'L':
            print("  Lekce (1–{}): ".format(len(LESSONS)), end='', flush=True)
            raw = input().strip()
            if raw.isdigit():
                n = int(raw)
                if 1 <= n <= len(LESSONS):
                    lesson_idx = n - 1
                    charset = list(LESSONS[lesson_idx])
                    print("  Lekce {}: [{}]".format(lesson_idx+1, LESSONS[lesson_idx]))
            current_group = ''.join(adaptive_group(charset, group_size, stats))
            continue

        elif answer == 'S':
            print_letter_stats(stats, charset)
            continue

        else:
            total += 1
            update_stats(stats, current_group, answer)

            if answer == current_group:
                correct += 1
                print("  ✓ správně!", end='  ')
            else:
                print("  ✗ bylo: {}".format(current_group), end='  ')

            print_stats_bar(correct, total)
            print()
            current_group = ''.join(adaptive_group(charset, group_size, stats))

    # Uložit a rozloučit se
    save_progress(lesson_idx, group_size, stats)
    print()
    print("  ── Konec tréninku — progress uložen ──")
    print_stats_bar(correct, total)
    if total > 0:
        print_letter_stats(stats, charset)
    print()

if __name__ == '__main__':
    main()