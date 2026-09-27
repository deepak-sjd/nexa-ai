import re


# Pure heuristics, no API calls — so this can never be the thing
# that breaks chat (unlike embeddings). Default is to retrieve
# (True) whenever unsure, so behavior only gets safer, never
# silently worse, than always-retrieve.

_GREETING_RE = re.compile(
    r"^(hi|hello|hey|yo|sup|thanks|thank you|thx|ok|okay|cool|"
    r"bye|goodbye|good morning|good night|who are you|what are you|"
    r"what can you do|how are you)[\s!.?]*$",
    re.IGNORECASE,
)

_DOCUMENT_HINT_RE = re.compile(
    r"\b(document|pdf|file|upload|attach|page \d|chapter|"
    r"according to|summarize|summarise|in (the|this|my) (doc|pdf|"
    r"file|report|resume|paper)|this (doc|pdf|file)|the (doc|pdf|"
    r"file) (says|states|mentions))\b",
    re.IGNORECASE,
)


def should_retrieve(query: str) -> bool:
    """
    Decide whether a message needs document retrieval at all.

    False only for the clear-cut cases (empty, pure greeting/
    smalltalk) so chit-chat never pays for a search or an
    embeddings call. Everything else defaults to True, same as
    today's always-retrieve behavior.
    """

    text = (query or "").strip()

    if not text:
        return False

    if _GREETING_RE.match(text):
        return False

    if _DOCUMENT_HINT_RE.search(text):
        return True

    # Short, generic questions with no document signal and no
    # question mark are more often smalltalk than a real query.
    if len(text) <= 12 and "?" not in text:
        return False

    return True
