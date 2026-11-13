import difflib

LANG_EN = 0x0409
LANG_RU = 0x0419

# Словарь русского жаргона, сокращений и частых слов
RU_WORDS = {
    "привет", "пока", "спасибо", "спс", "пожалуйста", "пж", "норм", "нормально",
    "кста", "кстати", "сори", "извини", "чел", "чувак", "бро", "го", "изи",
    "кринж", "вайб", "рофл", "имба", "база", "жиза", "пруф", "пруфы", "фича",
    "баг", "лаг", "лаги", "пинг", "фпс", "тима", "катка", "рандом", "скилл",
    "краш", "чилл", "хайп", "треш", "флекс", "агриться", "забей", "пофиг",
    "короче", "крч", "вообще", "сегодня", "завтра", "вчера", "сейчас", "щас",
    "потом", "когда", "почему", "зачем", "сколько", "какой", "хорошо", "плохо",
    "отлично", "супер", "класс", "круто", "жесть", "пипец", "блин", "окей",
    "ок", "ладно", "давай", "смотри", "слушай", "понял", "непонятно",
    "возможно", "наверное", "конечно", "точно", "серьезно", "реально",
    "буквально", "например", "значит", "потому", "чтобы", "который",
    "человек", "время", "работа", "деньги", "проблема", "вопрос"
}

# Словарь английского сленга, IT-терминов и частых слов
EN_WORDS = {
    "hello", "hi", "hey", "bye", "thanks", "thx", "ty", "pls", "please", "bro",
    "dude", "man", "guy", "guys", "lol", "lmao", "rofl", "omg", "wtf", "idk",
    "imo", "imho", "tbh", "brb", "afk", "gg", "wp", "ez", "noob", "pro", "lag",
    "ping", "fps", "bug", "fix", "feature", "code", "git", "push", "pull",
    "commit", "merge", "branch", "deploy", "server", "client", "api", "json",
    "sql", "linux", "windows", "python", "java", "script", "error", "warning",
    "because", "through", "though", "thought", "enough", "people", "should",
    "would", "could", "really", "actually", "probably", "definitely", "usually",
    "always", "never", "something", "anything", "everything", "nothing",
    "understand", "remember", "different", "important", "available", "possible"
}

# Слова-исключения, которые НИКОГДА не нужно переводить или исправлять
IGNORE_WORDS = {
    "git", "npm", "pip", "cd", "ls", "dir", "ssh", "sql", "api", "ok",
    "gg", "ez", "id", "ui", "ux", "exe", "py", "cpp", "cs"
}

# Жесткие замены для частых опечаток (срабатывают мгновенно)
HARD_TYPOS = {
    "приевет": "привет",
    "превет": "привет",
    "сегодян": "сегодня",
    "сигодня": "сегодня",
    "завтро": "завтра",
    "кароче": "короче",
    "вобще": "вообще",
    "вообщем": "в общем",
    "симпотичный": "симпатичный",
    "извените": "извините",
    "пожалуста": "пожалуйста",
    "спсибо": "спасибо",
    "teh": "the",
    "recieve": "receive",
    "seperate": "separate",
    "occured": "occurred",
    "definately": "definitely",
    "becuase": "because",
    "adress": "address",
    "wierd": "weird",
}


def preserve_case(original: str, corrected: str) -> str:
    """Сохраняет исходный регистр слова (Заглавная или КАПС)."""
    if not original:
        return corrected
    if original.isupper():
        return corrected.upper()
    if original[0].isupper():
        return corrected.capitalize()
    return corrected


def is_known_word(word: str, lang: int) -> bool:
    """Проверяет, есть ли слово в словаре указанного языка."""
    w_lower = word.lower()
    if lang == LANG_RU:
        return w_lower in RU_WORDS
    if lang == LANG_EN:
        return w_lower in EN_WORDS
    return False


def is_ignored(word: str) -> bool:
    """Проверяет, находится ли слово в списке исключений."""
    return word.lower() in IGNORE_WORDS


def autocorrect(word: str, lang: int, cutoff: float = 0.82) -> str:
    """
    Исправляет опечатки в слове для заданного языка.
    cutoff — порог схожести (от 0.0 до 1.0). Чем выше, тем строже проверка.
    """
    w_lower = word.lower()

    if w_lower in IGNORE_WORDS:
        return word

    # 1. Проверка по жесткому словарю опечаток
    if w_lower in HARD_TYPOS:
        return preserve_case(word, HARD_TYPOS[w_lower])

    # Короткие слова (< 4 букв) не исправляем нечетким поиском, чтобы не ломать сленг
    if len(w_lower) < 4:
        return word

    dictionary = RU_WORDS if lang == LANG_RU else EN_WORDS

    if w_lower in dictionary:
        return word

    # 2. Нечеткий поиск ближайшего слова
    matches = difflib.get_close_matches(w_lower, dictionary, n=1, cutoff=cutoff)
    if matches:
        return preserve_case(word, matches[0])

    return word