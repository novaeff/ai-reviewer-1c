from rules import *;
from entities import *;
from utils import *;
from analyzer import *;

def parse_module_text(text):
    lines = split_lines(text.lstrip("\ufeff"))
    methods = []

    directive = ""
    comment_lines = []
    regions = []
    pos = 0

    while pos < len(lines):
        line = lines[pos].strip()

        directive_match = DIRECTIVE_RE.match(line)
        if directive_match:
            directive = directive_match.group(1)
            line = directive_match.group(2).strip()
            if not line or line.startswith("//"):
                pos += 1
                continue

        header = HEADER_RE.match(line)
        if header is None:
            if not line:
                comment_lines = []
            elif line.startswith("//"):
                comment_lines.append(line[2:].strip())
            elif line.startswith("#"):
                comment_lines = []
                region_start = REGION_START_RE.match(line)
                if region_start:
                    regions.append(region_start.group(1).strip())
                elif REGION_END_RE.match(line) and len(regions) > 0:
                    regions.pop()
            else:
                directive = ""
                comment_lines = []
            pos += 1
            continue

        # Читаем заголовок метода (может переноситься на несколько строк)
        open_pos = header.end() - 1
        header_text = line
        header_size = 1
        close_pos = find_closing_paren(header_text, open_pos)
        while close_pos == -1 and pos + header_size < len(lines):
            header_text += "\n" + lines[pos + header_size].rstrip("\r\n")
            header_size += 1
            close_pos = find_closing_paren(header_text, open_pos)

        if close_pos == -1:
            params, is_export = [], False
        else:
            params = parse_params(header_text[open_pos + 1 : close_pos])
            after_paren = mask_code(header_text[close_pos + 1 :]).split("\n")[0]
            is_export = bool(EXPORT_RE.match(after_paren))

        # Собираем тело метода до КонецПроцедуры / КонецФункции
        body_lines = lines[pos : pos + header_size]
        next_pos = pos + header_size
        complete = False
        while next_pos < len(lines):
            curr_text = lines[next_pos].strip()
            if HEADER_RE.match(curr_text):
                break
            body_lines.append(lines[next_pos])
            next_pos += 1
            if END_RE.match(curr_text):
                complete = True
                break

        methods.append(
            BSLMethod(
                name=header.group(3),
                kind=header.group(2).capitalize(),
                directive=directive,
                body="".join(body_lines),
                start_line=pos + 1,
                end_line=pos + len(body_lines),
                params=params,
                is_export=is_export,
                is_async=header.group(1) is not None,
                comment="\n".join(comment_lines),
                region=" / ".join(regions),
                complete=complete,
            )
        )

        directive = ""
        comment_lines = []
        pos = next_pos

    # Индексируем методы и запускаем анализ
    index = {}
    for method in methods:
        key = method.name.lower()
        if key not in index:
            index[key] = method

    names = sorted(index, key=len, reverse=True)
    name_re = None
    if len(names) > 0:
        pattern = r"(?<![\w.])(" + "|".join(re.escape(n) for n in names) + r")\s*\("
        name_re = re.compile(pattern, re.IGNORECASE)

    for method in methods:
        analyze_method(method, name_re, index)
    for method in methods:
        add_transitive_hints(method, index)

    return BSLModule(methods=methods, index=index)


def parse_module(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    return parse_module_text(text)
