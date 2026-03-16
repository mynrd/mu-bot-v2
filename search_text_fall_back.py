import re
import unicodedata
from functools import lru_cache


def _strip_diacritics(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn")


def _canon(s: str, unify_vowels: bool = True) -> str:
    s = _strip_diacritics(s).lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    s = re.sub(r"vv", "w", s)
    if unify_vowels:
        s = re.sub(r"[eiou]", "a", s)
    return s


@lru_cache(maxsize=None)
def _lev_dist(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _lcs_len(a: str, b: str) -> int:
    la, lb = len(a), len(b)
    dp = [0] * (lb + 1)
    for i in range(1, la + 1):
        prev = 0
        for j in range(1, lb + 1):
            tmp = dp[j]
            dp[j] = prev + 1 if a[i - 1] == b[j - 1] else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[-1]


def is_close_match(ign: str, foundText: str, threshold: float = 0.75) -> bool:
    n = len(ign)
    if n <= 4:
        threshold = max(threshold, 0.80)

    a_norm = _canon(ign, unify_vowels=True)
    t_norm = _canon(foundText, unify_vowels=True)
    if not a_norm or not t_norm:
        return False
    n = len(a_norm)

    vowels = set("aeiou")
    a_cons = "".join(ch for ch in _canon(ign, unify_vowels=False) if ch not in vowels)
    t_cons = "".join(ch for ch in _canon(foundText, unify_vowels=False) if ch not in vowels)
    if len(a_cons) >= 2 and _lcs_len(a_cons, t_cons) < len(a_cons):
        return False

    best_agree = 0.0
    best_edit = 0.0
    for i in range(0, max(0, len(t_norm) - n) + 1):
        w = t_norm[i : i + n]
        agree = sum(c1 == c2 for c1, c2 in zip(a_norm, w)) / n
        edit = 1.0 - (_lev_dist(a_norm, w) / n)
        best_agree = max(best_agree, agree)
        best_edit = max(best_edit, edit)
        if agree >= threshold and edit >= (threshold - 0.05):
            return True

    lcs_ratio = _lcs_len(a_norm, t_norm) / n
    if lcs_ratio >= threshold and max(best_agree, best_edit) >= (threshold - 0.05):
        return True

    return False
