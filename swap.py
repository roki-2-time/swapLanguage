import ctypes
import re
import sys
import time
from ctypes import wintypes

import keyboard

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
user32.PostMessageW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p
]

WM_INPUTLANGCHANGEREQUEST = 0x0050
ERROR_ALREADY_EXISTS = 183

DEBUG = False  # поставьте True, чтобы видеть в консоли, что получает скрипт

# Защита от второго экземпляра (планировщик + IDE одновременно)
_mutex = kernel32.CreateMutexW(None, False, "Local\\swapLanguageAutocorrector")
if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
    print("Скрипт уже запущен, второй экземпляр закрывается.")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Быстрый ввод через SendInput (без буфера обмена и без пауз между клавишами)
# ---------------------------------------------------------------------------
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_BACK = 0x08

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _key_input(vk=0, scan=0, flags=0):
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return inp


def send_inputs(items):
    if not items:
        return
    arr = (INPUT * len(items))(*items)
    user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))


def send_backspaces(count):
    items = []
    for _ in range(count):
        items.append(_key_input(vk=VK_BACK))
        items.append(_key_input(vk=VK_BACK, flags=KEYEVENTF_KEYUP))
    send_inputs(items)


def send_text(text):
    """Печатает текст как Unicode, независимо от текущей раскладки."""
    items = []
    for ch in text:
        code = ord(ch)
        items.append(_key_input(scan=code, flags=KEYEVENTF_UNICODE))
        items.append(_key_input(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    send_inputs(items)


# ---------------------------------------------------------------------------

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
    "кт", "ку", "ня", "оч", "ош", "па", "пу", "ры", "са",
    "св", "сл", "со", "су", "сы", "тв", "те", "чи", "че", "щи",
    "эт", "яв", "ят", "ую", "ют", "ус", "бо", "бы", "ба", "бе",
    "ги", "го", "ди", "дн", "дл", "ог", "ук",
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
    "up", "ay", "ke", "ta", "wo", "rl", "ld", "ab", "ac",
}

# Технические слова, которые никогда не трогаем
IGNORE_WORDS = {
    "git", "npm", "pip", "cd", "ls", "dir", "ssh", "sql", "api",
    "ok", "lol", "gg", "install",
}

# Символы, которые срезаются по краям слова перед проверкой IGNORE_WORDS
# ("(git" -> "git", "git2" -> "git", "git." -> "git")
IGNORE_STRIP_CHARS = "()[]{}\"\\/-_0123456789.,;:!?`'"

# Пауза (сек) между нажатиями, после которой начинается новое слово
WORD_TIMEOUT = 2.0

# Русские слова: набранные по-русски не трогаем,
# набранные латиницей (например ,ele) всегда превращаем в русские.
# Сюда добавляйте слова, с которыми эвристика ошибается.
KNOWN_RU_WORDS = {
    "буду", "будет", "будем", "будешь", "будут", "будто",
    "звучит", "звучать", "звучало",
    "бы", "ещё", "еще", "если", "тогда", "когда", "хорошо", "пишешь",
}
KNOWN_EN_WORDS = {
    "the", "fucking"
}
# Односимвольные слова.
# На английской раскладке: z -> я, b -> и
SINGLE_EN_TO_RU = {"z", "b"}
# На русской раскладке: ш -> i (английское "I")
SINGLE_RU_TO_EN = {"ш"}

LANG_EN = 0x0409
LANG_RU = 0x0419

current_word = []
is_replacing = False
ignore_until = 0.0  # игнорируем собственные нажатия сразу после замены
last_key_time = 0.0  # время последнего нажатия (для сброса буфера по паузе)


def get_current_layout():
    """Получает ID раскладки активного окна напрямую через user32.dll."""
    hwnd = user32.GetForegroundWindow()
    thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    layout_id = user32.GetKeyboardLayout(thread_id)
    return layout_id & 0xFFFF


def force_switch_layout(target_lang):
    """Переключает раскладку; ждёт не дольше 0.15 с."""
    if get_current_layout() == target_lang:
        return

    hwnd = user32.GetForegroundWindow()
    hkl = user32.LoadKeyboardLayoutW(f"{target_lang:08X}", 1)
    user32.PostMessageW(hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl)

    for _ in range(30):
        time.sleep(0.005)
        if get_current_layout() == target_lang:
            return

    # Запасной вариант для окон, которые игнорируют PostMessage (Telegram)
    keyboard.send("alt+shift")


def bigram_ratio(word, bigrams):
    """Доля пар букв слова, которые встречаются в наборе bigrams (0..1)."""
    word = word.lower()
    pairs = [word[i : i + 2] for i in range(len(word) - 1)]
    if not pairs:
        return 0.0
    return sum(p in bigrams for p in pairs) / len(pairs)


def should_switch(word):
    if not word:
        return None

    word_l = word.lower()
    core = word_l.strip(IGNORE_STRIP_CHARS)  # слово без скобок, цифр, знаков

    layout = get_current_layout()

    if DEBUG:
        print(f"word={word!r} core={core!r} layout={hex(layout)}")

    # --- Технические слова: не трогаем ---
    if word_l in IGNORE_WORDS or core in IGNORE_WORDS:
        return None

    # Технические слова, набранные на русской раскладке (git -> пше):
    # возвращаем английский вариант и переключаем раскладку на EN
    if layout == LANG_RU and core:
        core_en = core.translate(RU_TO_EN)
        if core_en in IGNORE_WORDS:
            return LANG_EN, word.translate(RU_TO_EN)

    # --- Односимвольные слова ---
    if len(word) == 1:
        if layout == LANG_EN and word_l in SINGLE_EN_TO_RU:
            return LANG_RU, word.translate(EN_TO_RU)
        if layout == LANG_RU and word_l in SINGLE_RU_TO_EN:
            return LANG_EN, word.translate(RU_TO_EN)
        return None

    # --- Известные русские слова: решаем по списку, без биграмм ---
    if layout == LANG_RU and word_l in KNOWN_RU_WORDS:
        return None  # уже набрано правильно

    if layout == LANG_EN:
        converted_known = word.translate(EN_TO_RU)
        if converted_known.lower() in KNOWN_RU_WORDS:
            return LANG_RU, converted_known  # ,ele -> буду

    # --- Остальные слова: эвристика по биграммам ---
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
    global is_replacing, ignore_until
    is_replacing = True  # Блокируем новые нажатия на время исправления

    try:
        # 1. Стираем ошибочное слово (+1 за уже набранный пробел) одним пакетом
        send_backspaces(word_len + 1)

        # 2. Сразу печатаем исправленное слово и пробел (Unicode, без буфера обмена)
        send_text(converted_word + " ")

        # 3. Только после этого меняем раскладку, чтобы текст появился мгновенно
        force_switch_layout(target_lang)
    finally:
        current_word.clear()
        ignore_until = time.time() + 0.08  # не реагируем на свои же нажатия
        is_replacing = False


def on_key_event(event):
    global current_word, last_key_time

    # Игнорируем события во время замены, сразу после неё и отпускание клавиш
    if is_replacing or time.time() < ignore_until or event.event_type != keyboard.KEY_DOWN:
        return

    # Долгая пауза в наборе: клик мышью, смена окна и т.п. — начинаем слово заново
    now = time.time()
    if now - last_key_time > WORD_TIMEOUT:
        current_word.clear()
    last_key_time = now

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

        # Enter уже отправил сообщение (например, в Telegram), исправлять поздно
        if name == "enter":
            return

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
    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("Остановлено.")