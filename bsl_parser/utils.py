from rules import *;
from entities import Param

def methods_in_ranges(methods, ranges):
    res = []
    for m in methods:
        for start, end in ranges:
            if m.overlaps(start, end):
                res.append(m)
                break
    return res


def split_lines(text):
    # Не используем splitlines(), потому что он режет по \x0c и сбивает номера строк
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def mask_code(text, keep_strings=False):
    # Заменяем комментарии и строки на пробелы, чтобы не парсить слова внутри них,
    # но сохраняем переносы строк, чтобы не поехала нумерация
    res = []
    in_string = False
    pos = 0
    while pos < len(text):
        char = text[pos]
        next_char = text[pos + 1 : pos + 2]

        if in_string:
            # экранированные кавычки "" внутри строки 1С
            if char == '"' and next_char == '"':
                res.append('""' if keep_strings else "  ")
                pos += 2
                continue
            if char == '"':
                in_string = False
                res.append('"')
            elif char == "\n" or keep_strings:
                res.append(char)
            else:
                res.append(" ")
        elif char == '"':
            in_string = True
            res.append('"')
        elif char == "/" and next_char == "/":
            while pos < len(text) and text[pos] != "\n":
                res.append(" ")
                pos += 1
            continue
        else:
            res.append(char)
        pos += 1
    return "".join(res)

def find_closing_paren(text, open_pos):
    masked = mask_code(text[open_pos:])
    depth = 0
    for i, char in enumerate(masked):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return open_pos + i
    return -1


def split_params(text):
    parts = []
    current = []
    depth = 0
    in_string = False
    for char in text:
        if char == '"':
            in_string = not in_string
        if not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append("".join(current))
                current = []
                continue
        current.append(char)
    parts.append("".join(current))
    return parts


def parse_params(text):
    params = []
    for part in split_params(mask_code(text, keep_strings=True)):
        part = " ".join(part.split())
        if not part:
            continue
        match = PARAM_RE.match(part)
        if match is None:
            continue
        params.append(
            Param(
                name=match.group(2),
                by_val=match.group(1) is not None,
                default=(match.group(3) or "").strip(),
            )
        )
    return params


def is_client(directive):
    d = directive.lower()
    return d.startswith("&наклиенте") and not d.startswith("&наклиентенасервере")


def is_server(directive):
    return directive.lower().startswith("&насервере")


def get_context_name(directive):
    if directive.lower().startswith("&наклиентенасервере"):
        return "клиент и сервер"
    if is_server(directive):
        return "сервер"
    if is_client(directive):
        return "клиент"
    return "контекст неизвестен"