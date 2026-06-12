import json

from app import config

_translations: dict[str, dict] = {}


def load():
    for code in ("en", "fa"):
        path = config.TRANSLATIONS_DIR / f"{code}.json"
        _translations[code] = json.loads(path.read_text(encoding="utf-8"))


def get_locale(request) -> str:
    lang = request.cookies.get("lang", "en")
    return lang if lang in ("en", "fa") else "en"


def translator(lang: str):
    if not _translations:
        load()
    table = _translations.get(lang, {})
    fallback = _translations.get("en", {})

    def t(key: str) -> str:
        return table.get(key) or fallback.get(key, key)

    return t
