"""Generic category matching for product discovery.

Matches user-provided category strings against actual database categories
using linguistic techniques: singularization, suffix/root matching,
synonym expansion, and coverage-based disambiguation.

No hardcoded category→category mappings. Uses two small, generic tables:
  1. IRREGULAR_PLURALS — English irregular plural forms (mouse↔mice, etc.)
  2. PRODUCT_SYNONYMS  — Common product-term synonyms (tv↔television, etc.)

Both tables are language-level, NOT catalog-specific.
"""

import re
from typing import List, Optional, Set, Tuple


# ── English irregular plurals ───────────────────────────────────────────
# Maps singular → plural for words where simple s/es stripping fails.
# Bidirectional: both directions are checked during matching.
IRREGULAR_PLURALS = {
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "child": "children",
    "person": "people",
    "die": "dice",
    "ox": "oxen",
    "man": "men",
    "woman": "women",
    "leaf": "leaves",
    "knife": "knives",
    "life": "lives",
    "shelf": "shelves",
    "self": "selves",
    "calf": "calves",
    "wolf": "wolves",
    "half": "halves",
}

# Build reverse lookup (plural → singular)
_IRREGULAR_PLURAL_REVERSE = {v: k for k, v in IRREGULAR_PLURALS.items()}


# ── Product-term synonyms ──────────────────────────────────────────────
# Maps equivalent product terminology. NOT category names — these are
# generic English words that refer to the same concept.
# Each key maps to a set of alternative forms of the SAME concept.
PRODUCT_SYNONYMS = {
    "tv": {"television", "tele"},
    "television": {"tv", "tele"},
    "tele": {"tv", "television"},
    "notebook": {"laptop"},
    "laptop": {"notebook"},
    "phone": {"smartphone", "cellphone", "mobile"},
    "smartphone": {"phone", "cellphone", "mobile"},
    "cellphone": {"phone", "smartphone", "mobile"},
    "mobile": {"phone", "smartphone", "cellphone"},
    "watch": {"smartwatch", "wristwatch"},
    "smartwatch": {"watch", "wristwatch"},
    "wristwatch": {"watch", "smartwatch"},
    "earphone": {"earpiece", "in-ear"},
    "monitor": {"display", "screen"},
    "display": {"monitor", "screen"},
    "screen": {"monitor", "display"},
    "headset": {"headphone"},
    "headphone": {"headset"},
}


def _singularize(word: str) -> str:
    """Simple English singularization with irregular plural support."""
    word = word.lower().strip()

    # Check irregular plurals first
    if word in _IRREGULAR_PLURAL_REVERSE:
        return _IRREGULAR_PLURAL_REVERSE[word]

    # Regular rules (order matters)
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ves") and len(word) > 4:
        return word[:-3] + "f"
    if word.endswith("ses") and len(word) > 4:
        return word[:-2]
    if word.endswith("ches") or word.endswith("shes") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]

    return word


def _pluralize(word: str) -> str:
    """Simple English pluralization with irregular plural support."""
    word = word.lower().strip()

    # Check irregular plurals
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]

    # Regular rules
    if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith("f"):
        return word[:-1] + "ves"
    if word.endswith("fe"):
        return word[:-2] + "ves"
    if word.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"

    return word + "s"


def _get_word_forms(word: str) -> Set[str]:
    """Get all known forms of a word: original, singular, plural, synonyms."""
    word = word.lower().strip()
    forms = {word}

    singular = _singularize(word)
    plural = _pluralize(word)
    forms.add(singular)
    forms.add(plural)

    # Also get forms of the singular (in case the input was already plural)
    forms.add(_pluralize(singular))

    # Add synonym forms
    for form in list(forms):
        if form in PRODUCT_SYNONYMS:
            for syn in PRODUCT_SYNONYMS[form]:
                forms.add(syn)
                forms.add(_singularize(syn))
                forms.add(_pluralize(syn))

    return forms


def _tokenize(text: str) -> List[str]:
    """Split text into lowercase tokens on whitespace, hyphens, underscores."""
    return [t for t in re.split(r"[\s_\-]+", text.lower().strip()) if t]


def _score_category(
    user_tokens: List[str],
    db_cat: str,
) -> float:
    """Score how well user tokens match a database category.

    Returns a float score. Higher = better match. 0 = no match.

    Scoring tiers:
      2.0  — Exact full-string match (after singularization)
      1.5  — Exact token overlap (singularized forms match)
      0.7–0.95 — Suffix/root match (user token is a suffix of category token)
      0.5–0.69 — Substring/prefix match
      0.0  — No match
    """
    db_tokens = _tokenize(db_cat)

    # Expand all forms for user tokens and DB tokens
    user_forms_per_token = []
    for ut in user_tokens:
        user_forms_per_token.append(_get_word_forms(ut))
    all_user_forms = set()
    for forms in user_forms_per_token:
        all_user_forms |= forms

    db_forms_per_token = []
    for dt in db_tokens:
        db_forms_per_token.append(_get_word_forms(dt))
    all_db_forms = set()
    for forms in db_forms_per_token:
        all_db_forms |= forms

    # ── Tier 1: Exact full-string match ──────────────────────────────
    db_cat_lower = db_cat.lower().strip()
    user_joined = " ".join(user_tokens).lower().strip()
    if user_joined == db_cat_lower:
        return 2.0
    if _singularize(user_joined) == _singularize(db_cat_lower):
        return 2.0
    # Also check hyphenated
    user_joined_hyphen = "-".join(user_tokens).lower().strip()
    if user_joined_hyphen == db_cat_lower:
        return 2.0

    # Check if any user form matches the full db category (e.g. "television" → synonym "tv" matches "tvs")
    db_cat_singular = _singularize(db_cat_lower.replace("-", "").replace("_", "").replace(" ", ""))
    for form in all_user_forms:
        if form == db_cat_lower or form == db_cat_singular:
            return 1.9
        if _singularize(form) == db_cat_singular:
            return 1.9

    # ── Tier 2: Token-level exact overlap ────────────────────────────
    overlap_count = 0
    for uf_set in user_forms_per_token:
        for df_set in db_forms_per_token:
            if uf_set & df_set:
                overlap_count += 1
                break

    if overlap_count > 0:
        # Score based on coverage of both sides
        user_coverage = overlap_count / len(user_tokens)
        db_coverage = overlap_count / len(db_tokens)
        score = 1.0 + min(user_coverage, db_coverage) * 0.5
        return score

    # ── Tier 3: Suffix/substring matching ────────────────────────────
    best_sub_score = 0.0

    for uf_set in user_forms_per_token:
        for df_set in db_forms_per_token:
            for uf in uf_set:
                if len(uf) < 3:
                    continue
                for df in df_set:
                    if len(df) < 3:
                        continue

                    # Suffix match: user form is a suffix of db form
                    # e.g. "phone" is suffix of "smartphone"
                    if df.endswith(uf) and len(df) > len(uf):
                        # Coverage ratio: how much of the db token does the user form cover?
                        coverage = len(uf) / len(df)
                        # Suffix match base score is 0.7, boosted by coverage
                        sub_score = 0.7 + coverage * 0.25
                        if sub_score > best_sub_score:
                            best_sub_score = sub_score

                    # Prefix match: user form is a prefix of db form
                    # e.g. "head" is prefix of "headphone"
                    elif df.startswith(uf) and len(df) > len(uf):
                        coverage = len(uf) / len(df)
                        sub_score = 0.5 + coverage * 0.15
                        if sub_score > best_sub_score:
                            best_sub_score = sub_score

                    # Reverse: db form is a suffix/substring of user form
                    elif uf.endswith(df) and len(uf) > len(df):
                        coverage = len(df) / len(uf)
                        sub_score = 0.6 + coverage * 0.2
                        if sub_score > best_sub_score:
                            best_sub_score = sub_score

    return best_sub_score


def match_category(
    query: str,
    db_categories: List[str],
    threshold: float = 0.4,
) -> Optional[str]:
    """Match a user-provided query string against a list of database categories.

    Args:
        query: The user's category query (e.g. "phone", "wireless headphones",
               "laptop", "television").
        db_categories: List of actual category strings from the database.
        threshold: Minimum score to consider a match.

    Returns:
        The best-matching category string, or None if no match above threshold.
    """
    if not query or not db_categories:
        return None

    query = query.lower().strip()

    # Direct exact match (fast path)
    for db_cat in db_categories:
        if db_cat.lower() == query:
            return db_cat

    # Tokenize the query and remove stop words
    stop_words = {
        "show", "me", "i", "need", "want", "get", "buy", "find",
        "search", "looking", "for", "some", "a", "an", "the",
        "with", "under", "below", "above", "over", "and", "or",
        "that", "have", "has", "is", "are", "please", "can", "you",
        "best", "good", "great", "top", "cheap", "budget",
        "premium", "high", "low", "new", "latest",
    }

    raw_tokens = _tokenize(query)
    user_tokens = [t for t in raw_tokens if t not in stop_words and len(t) > 1]

    if not user_tokens:
        # Fall back to raw tokens if everything was stopped
        user_tokens = [t for t in raw_tokens if len(t) > 1]
    if not user_tokens:
        return None

    best_match = None
    best_score = 0.0

    for db_cat in db_categories:
        score = _score_category(user_tokens, db_cat)
        if score > best_score:
            best_score = score
            best_match = db_cat

    if best_match and best_score >= threshold:
        return best_match

    return None


def match_category_from_message(
    message: str,
    db_categories: List[str],
    threshold: float = 0.4,
) -> Optional[str]:
    """Match a category from a full user message (not just category tokens).

    This tries multiple strategies:
    1. Match the full message (after stop-word removal)
    2. Try individual tokens and bigrams as category candidates
    3. Return the best overall match

    Args:
        message: Full user message (e.g. "show me a phone under 20000")
        db_categories: List of actual category strings from the database.
        threshold: Minimum score to consider a match.

    Returns:
        The best-matching category string, or None if no match.
    """
    if not message or not db_categories:
        return None

    message = message.lower().strip()

    # Direct exact match against any category
    for db_cat in db_categories:
        if db_cat.lower() in message:
            return db_cat

    # Also check singularized forms of categories
    for db_cat in db_categories:
        cat_singular = _singularize(db_cat.lower().replace("-", " "))
        if cat_singular in message:
            return db_cat
        # Check hyphenated version too
        cat_singular_hyphen = _singularize(db_cat.lower())
        if cat_singular_hyphen in message and len(cat_singular_hyphen) > 2:
            return db_cat

    stop_words = {
        "show", "me", "i", "need", "want", "get", "buy", "find",
        "search", "looking", "for", "some", "a", "an", "the",
        "with", "under", "below", "above", "over", "and", "or",
        "that", "have", "has", "had", "is", "are", "was", "were",
        "do", "does", "did", "can", "could", "would", "should",
        "will", "shall", "may", "might", "must", "not", "no",
        "best", "good", "great", "top", "cheap", "budget",
        "premium", "high", "low", "new", "old", "latest",
        "price", "cost", "around", "about", "approximately",
        "please", "you",
    }

    words = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", message)
    content_words = [w for w in words if w not in stop_words and len(w) > 1]

    if not content_words:
        return None

    # Build candidate phrases: individual words + bigrams
    candidates = list(content_words)
    for i in range(len(content_words) - 1):
        candidates.append(f"{content_words[i]} {content_words[i+1]}")
        candidates.append(f"{content_words[i]}-{content_words[i+1]}")

    best_match = None
    best_score = 0.0

    for candidate in candidates:
        candidate_tokens = _tokenize(candidate)
        for db_cat in db_categories:
            score = _score_category(candidate_tokens, db_cat)
            if score > best_score:
                best_score = score
                best_match = db_cat

    if best_match and best_score >= threshold:
        return best_match

    return None
