import ctypes
import re
import time
import keyboard
import pyperclip

user32 = ctypes.WinDLL("user32", use_last_error=True)

EN_CHARS = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?~"
RU_CHARS = "йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё"

EN_TO_RU = str.maketrans(EN_CHARS, RU_CHARS)
RU_TO_EN = str.maketrans(RU_CHARS, EN_CHARS)

RU_BIGRAMS = {
    "пр", "ст", "но", "то", "на", "ен", "ов", "ни", "ра", "во",
    "ко", "ро", "по", "не", "ал", "ос", "ли", "ка", "ер", "ре",
    "ть", "ся", "ет", "ат", "от", "ел", "ор", "за", "ва", "ак",
    "ом", "он", "ин", "ис", "ем", "им", "ыв", "ый", "ая", "ое",
    "ие", "чт", "гд", "зд", "сп",
    # дополнительные частотные пары
    "бу", "уд", "ду", "да", "де", "до", "ей", "ещ", "ще", "чо",
    "ше", "хо", "ож", "мо", "ма", "ми", "ме", "му", "мы", "мн",
    "ну", "ны", "об", "од", "ту", "ты", "ти", "тр", "пе", "пи",
    "пл", "ле", "лю", "ль", "ла", "ло", "лу", "ды", "же", "жи",
    "зн", "из", "ид", "ий", "ик", "ир", "ит", "ке", "ки", "кн",
    "кт", "ку", "ны", "ня", "оч", "ош", "па", "пу", "ры", "са",
    "св", "сл", "со", "су", "сы", "тв", "те", "чи", "че", "щи",
    "эт", "яв", "ят", "ую", "ют", "ус", "бо", "бы", "ба", "бе",
    "ги", "го", "ди", "дн", "дл", "ид", "ог", "ое", "ту", "ук",
}

EN_BIGRAMS = {
    "th", "he", "in", "er", "an", "re", "on", "at", "en", "nd",
    "ti", "es", "or", "te", "of", "ed", "is", "it", "al", "ar",
    "st", "to", "nt", "ng", "se", "ha", "as", "ou", "io", "le",
    "ve", "co", "me", "de", "hi", "ri", "ro", "ic", "ne", "ea",
    "ra", "ce", "wh", "ll", "ee", "oo", "sh", "ch", "gh",
    # дополнительные частотные пары
    "el", "lo", "ow", "ye", "ur", "ut", "ot", "ho", "wa", "ad",
    "id", "im", "ma", "pl", "pr", "us", "ge", "be", "so", "no",
    "up", "ay", "ke", "ta", "wo", "rl", "ld", "ab", "ac", "ve",
}

IGNORE_WORDS = {
    "git", "npm", "pip", "cd", "ls", "dir", "ssh", "sql", "api",
    "ok", "lol", "gg", "install",
    "буду", "звучит"
}

# Одиночные английские буквы, которые нужно превращать в русские слова.
# При желании можно расширить, но "a" и "i" — настоящие английские слова.
SINGLE_EN_TO_RU = {"z"}

LANG_EN = 0x0409
LANG_RU = 0x0419

current_word = []
is_replacing = False


def get_current_layout():
    """Получает ID раскладки активного окна напрямую через user32.dll."""
    hwnd = user32.GetForegroundWindow()
    thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    layout_id = user32.GetKeyboardLayout(thread_id)
    return layout_id & 0xFFFF


def force_switch_layout(target_lang):
    """Надежно переключает системную раскладку во всех типах окон."""
    hwnd = user32.GetForegroundWindow()
    user32.PostMessageW(hwnd, 0x0050, 0, target_lang)
    time.sleep(0.03)

    if get_current_layout() != target_lang:
        keyboard.send("alt+shift")
        time.sleep(0.04)


def bigram_ratio(word, bigrams):
    """Доля пар букв слова, которые встречаются в наборе bigrams (0..1)."""
    word = word.lower()
    pairs = [word[i : i + 2] for i in range(len(word) - 1)]
    if not pairs:
        return 0.0
    return sum(p in bigrams for p in pairs) / len(pairs)


def should_switch(word):
    word_l = word.lower()
    if not word or word_l in IGNORE_WORDS:
        return None

    layout = get_current_layout()

    # --- Односимвольные слова: только z -> я ---
    if len(word) == 1:
        if layout == LANG_EN and word_l in SINGLE_EN_TO_RU:
            return LANG_RU, word.translate(EN_TO_RU)
        return None

    if layout == LANG_EN:
        # английские сокращения: don't, it's, I'm, we'll ...
        if re.search(r"'(s|t|d|m|ll|re|ve)$", word_l):
            return None

        converted = word.translate(EN_TO_RU)
        orig = bigram_ratio(word, EN_BIGRAMS)
        conv = bigram_ratio(converted, RU_BIGRAMS)
        has_punct = any(c in word[:-1] for c in "[];',.`")

        if conv > orig or (has_punct and conv > 0):
            return LANG_RU, converted

    elif layout == LANG_RU:
        # короткие русские слова (да, ну, еще...) не трогаем
        if len(word) < 4:
            return None

        converted = word.translate(RU_TO_EN)

        # настоящее английское слово состоит только из букв;
        # если в нём есть , . ; [ ] ' ` — это русское слово с б, ю, ж, х, э...
        if not converted.isalpha():
            return None

        orig = bigram_ratio(word, RU_BIGRAMS)
        conv = bigram_ratio(converted, EN_BIGRAMS)

        if conv >= 0.5 and conv > orig:
            return LANG_EN, converted

    return None


def replace_word_globally(word_len, converted_word, end_key, target_lang):
    global is_replacing
    is_replacing = True  # Блокируем новые нажатия на время исправления

    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        old_clipboard = ""
    time.sleep(0.02)

    # Аккуратно стираем ошибочное слово с небольшой задержкой
    for _ in range(word_len + 1):
        keyboard.send("backspace")
        time.sleep(0.005)

    # Меняем язык системы
    force_switch_layout(target_lang)

    # Записываем исправленное слово и вставляем через буфер обмена
    pyperclip.copy(converted_word)
    time.sleep(0.03)
    keyboard.send("ctrl+v")
    time.sleep(0.05)  # Даем системе время обработать вставку
    keyboard.send(end_key)  # Возвращаем пробел или Enter

    # Возвращаем старый буфер обмена
    time.sleep(0.1)
    try:
        pyperclip.copy(old_clipboard)
    except Exception:
        pass

    is_replacing = False


def on_key_event(event):
    global current_word, is_replacing

    # Игнорируем события во время замены или если клавиша отпущена
    if is_replacing or event.event_type != keyboard.KEY_DOWN:
        return

    name = event.name

    if len(name) > 1 and name not in ("space", "enter", "backspace"):
        if name in ("left", "right", "up", "down", "esc", "tab", "delete", "home", "end"):
            current_word.clear()
        return

    if name == "backspace":
        if current_word:
            current_word.pop()
        return

    if name in ("space", "enter"):
        word_str = "".join(current_word)
        current_word.clear()

        result = should_switch(word_str)
        if result:
            target_lang, converted_word = result
            replace_word_globally(len(word_str), converted_word, name, target_lang)
        return

    if len(name) == 1:
        if keyboard.is_pressed("ctrl") or keyboard.is_pressed("alt") or keyboard.is_pressed("win"):
            current_word.clear()
            return
        current_word.append(name)


if __name__ == "__main__":
    print("Автопереключатель запущен...")
    keyboard.hook(on_key_event)
    keyboard.wait()