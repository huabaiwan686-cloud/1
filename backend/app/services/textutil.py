"""文本工具：通配符匹配（P1-16 采集通配符替换）。"""
import re


def wildcard_to_regex(pattern: str) -> str:
    """把 *（任意序列）/?（单个字符）通配符转成正则。"""
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def wildcard_match(text: str, pattern: str) -> bool:
    """全文任意位置匹配（类似 fnmatch 但跨行）。无通配符时退化为子串判断。"""
    if not pattern:
        return False
    text = text or ""
    if "*" not in pattern and "?" not in pattern:
        return pattern in text
    return re.search(wildcard_to_regex(pattern), text, re.DOTALL) is not None


def wildcard_replace(text: str, pattern: str, repl: str) -> str:
    """通配符替换：pattern 含 * / ? 时按正则替换，否则普通子串替换。"""
    if not pattern:
        return text
    if "*" not in pattern and "?" not in pattern:
        return (text or "").replace(pattern, repl)
    return re.sub(wildcard_to_regex(pattern), repl, text or "", flags=re.DOTALL)
