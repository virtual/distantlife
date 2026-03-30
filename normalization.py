import re
import unicodedata

# Hebrew cantillation and niqqud marks.
HEBREW_NIKKUD_RE = re.compile(r"[\u0591-\u05C7]")
WHITESPACE_RE = re.compile(r"\s+")


def strip_nikkud(text):
    """Return Hebrew text without niqqud/cantillation marks."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFC", str(text))
    return HEBREW_NIKKUD_RE.sub("", normalized)


def has_nikkud(text):
    """Return True if the text contains Hebrew niqqud/cantillation marks."""
    if not text:
        return False
    return HEBREW_NIKKUD_RE.search(str(text)) is not None


def compute_search_key(text, language_code=""):
    """Build a normalized search key for indexed lookups."""
    if text is None:
        return ""

    value = unicodedata.normalize("NFC", str(text)).strip()
    code = (language_code or "").strip().lower()
    if code in {"he", "heb", "hebrew"}:
        value = strip_nikkud(value)

    value = WHITESPACE_RE.sub(" ", value)
    return value.lower()
