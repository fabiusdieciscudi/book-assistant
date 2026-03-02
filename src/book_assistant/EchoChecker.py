from collections import deque, defaultdict
import re
from typing import Any

from Commons import red, log
from book_assistant.Commons import yellow

_IGNORED = ["ancora", "degli", "della", "delle", "nella", "alla", "dalla", "sono", "sulla", "Roberto", "Claire", "Goodwill", "Buongiorno", "sono", "siamo", "suoi", "Jacques", "Géraldine"]

def _find_nearby_echoes(file_path: Path, window_size=100):
    word_queue = deque(maxlen=window_size)
    occurrences = []

    sentence_pattern = re.compile(r'[^.!?]+[.!?]+')
    word_pattern = re.compile(r"\b\w+(?:['’-]\w+)?\b")

    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    sentences = sentence_pattern.findall(text)

    for sent_idx, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue

        for match in word_pattern.finditer(sentence):
            word = match.group(0)
            if len(word) < 4:
                continue

            current_tuple = (word, sent_idx, sentence, match.start())

            for prev_word, prev_idx, prev_sentence, prev_pos in word_queue:
                if prev_word == word:
                    prev_tuple = (prev_word, prev_idx, prev_sentence, prev_pos)

                    if current_tuple not in occurrences:
                        occurrences.append(current_tuple)

                    if prev_tuple not in occurrences:
                        occurrences.append(prev_tuple)

            word_queue.append(current_tuple)

    return occurrences


def find_echoes(file_path, window_size=100):
    repeats = _find_nearby_echoes(file_path, window_size)

    if not repeats:
        print("No nearby word repetitions found.")
        return

    prev_sentence = None
    xlist = []

    occurrences = 0

    for word, index, sentence, position in sorted(repeats, key=lambda t: t[1]): # sorted by index
        if prev_sentence != sentence and prev_sentence or index == len(repeats) + 1:
            s, o = _marked(prev_sentence, xlist)
            occurrences = occurrences + o

            if o:
                print(f"[{index: >3}] {s}")

            xlist.clear()

        xlist.append((word, position))  # FIXME: the last one is lost?
        prev_sentence = sentence

    print(f"Occurrences: {occurrences}")


def _marked(s: str, xlist: list[Any]) -> tuple[str, int]:
    occurrences = 0
    for w, p in reversed(sorted(xlist, key=lambda t: t[1])):
        count = 0
        for w1, p1 in xlist:
            if w1 == w:
                count = count + 1

        if count > 1 or w not in _IGNORED:
            color = yellow if count == 1 else red
            s = f"{s[:p]}{color(s[p:p + len(w)])}{s[p + len(w):]}"
            occurrences = occurrences + 1

    return s, occurrences


# Esempio di utilizzo
if __name__ == "__main__":
    file_path = "/Volumes/Aguieloun/Fabius Dieciscudi/Jacques Messadié/1. Jacques Messadié gioca a sciarada/Latex/target/txt/Jacques_Messadié_gioca_a_sciaradach31.txt"
    find_echoes(file_path, window_size=80)