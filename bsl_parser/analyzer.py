from rules import *;
from utils import *;
from entities import *;

def analyze_method(method, name_re, index):
    masked = mask_code(method.body)
    server_flag = is_server(method.directive)

    hints = []
    already_added = set()
    facts = {}
    calls = []

    def add_hint(code, line, message):
        if (code, line) not in already_added:
            already_added.add((code, line))
            hints.append(Hint(code, line, message))

    def add_fact(key, name, line):
        if key not in facts:
            facts[key] = []
        if (name, line) not in facts[key]:
            facts[key].append((name, line))
        facts[key].append((name, line))

    loop_depth = 0
    tx_depth = 0
    nesting = 0
    max_nesting = 0
    max_nesting_line = method.start_line
    max_tx_in_try = []

    for i, line in enumerate(masked.split("\n")):
        curr_line = method.start_line + i

        # Проверка правил из списка RULES
        for rule in RULES:
            match = rule["pattern"].search(line)
            if not match:
                continue
            name = match.group(0).strip(" (.")
            if rule["fact"]:
                add_fact(rule["fact"], name, curr_line)

            active = False
            if rule["when"] == "loop":
                active = loop_depth > 0
            elif rule["when"] == "tx":
                active = tx_depth > 0
            else:
                active = server_flag

            if active == True:
                add_hint(rule["code"], curr_line, rule["msg"])

        # Поиск вызовов других методов этого же модуля
        if name_re is not None:
            for match in name_re.finditer(line):
                before = line[max(0, match.start() - 20) : match.start()]
                if DEFINITION_PREFIX_RE.search(before):
                    continue
                called = index.get(match.group(1).lower())
                if called:
                    calls.append(Call(called.name, curr_line, loop_depth > 0))

        # Подсчет вложенности блоков и транзакций
        for match in KEYWORDS_RE.finditer(line):
            kw = match.group(1).lower()

            # Отсекаем инструкции препроцессора #Если и #КонецЕсли
            if kw in ("если", "конецесли") and match.start() > 0 and line[match.start() - 1] == "#":
                continue

            if kw in ("цикл", "если", "попытка"):
                nesting += 1
                if nesting > max_nesting:
                    max_nesting = nesting
                    max_nesting_line = curr_line
                if kw == "цикл":
                    loop_depth += 1
                    add_fact("loop", "Цикл", curr_line)
                elif kw == "попытка":
                    max_tx_in_try.append(tx_depth)
                    add_fact("try", "Попытка", curr_line)

            elif kw in ("конеццикла", "конецесли", "конецпопытки"):
                nesting = max(0, nesting - 1)
                if kw == "конеццикла":
                    loop_depth = max(0, loop_depth - 1)
                elif kw == "конецпопытки" and len(max_tx_in_try) > 0:
                    max_tx_in_try.pop()

            elif kw == "исключение":
                if len(max_tx_in_try) > 0:
                    tx_depth = max_tx_in_try[-1]

            elif kw == "начатьтранзакцию":
                tx_depth += 1
                add_fact("tx_begin", "НачатьТранзакцию", curr_line)
                if loop_depth > 0:
                    add_hint("TRANSACTION_IN_LOOP", curr_line, "НачатьТранзакцию внутри цикла")

            elif kw == "зафиксироватьтранзакцию":
                tx_depth = max(0, tx_depth - 1)
                add_fact("tx_commit", "ЗафиксироватьТранзакцию", curr_line)

            elif kw == "отменитьтранзакцию":
                tx_depth = max(0, tx_depth - 1)
                add_fact("tx_rollback", "ОтменитьТранзакцию", curr_line)

            for idx in range(len(max_tx_in_try)):
                if tx_depth > max_tx_in_try[idx]:
                    max_tx_in_try[idx] = tx_depth

    if is_client(method.directive):
        for call in calls:
            target = index.get(call.name.lower())
            if call.in_loop and target and is_server(target.directive):
                add_hint(
                    "SERVER_CALL_IN_LOOP",
                    call.line,
                    f"вызов серверного метода {call.name} в цикле клиентского метода",
                )

    tx_starts = facts.get("tx_begin", [])
    if tx_starts and not facts.get("tx_commit"):
        add_hint("TRANSACTION_NO_COMMIT", tx_starts[0][1], "НачатьТранзакцию без ЗафиксироватьТранзакцию")
    if tx_starts and not facts.get("tx_rollback"):
        add_hint("TRANSACTION_NO_ROLLBACK", tx_starts[0][1], "нет ОтменитьТранзакцию в блоке обработки ошибок")

    for match in EMPTY_EXCEPT_RE.finditer(masked):
        curr_line = method.start_line + masked.count("\n", 0, match.start())
        add_hint("EMPTY_EXCEPT", curr_line, "пустой блок Исключение скрывает ошибки")

    if max_nesting >= DEEP_NESTING_LEVEL:
        add_hint(
            "DEEP_NESTING",
            max_nesting_line,
            f"вложенность блоков {max_nesting} уровней, стоит вынести часть логики в отдельный метод",
        )
    if method.line_count > LONG_METHOD_LINES:
        add_hint("LONG_METHOD", method.start_line, f"метод слишком длинный ({method.line_count} строк)")

    method.max_nesting = max_nesting
    method.has_query = bool(facts.get("query") or facts.get("query_exec"))
    method.calls = calls
    method.facts = facts
    method.hints = sorted(hints, key=lambda h: h.line)


def reaches_query(start, index):
    # Обход в глубину по графу вызовов (visited защищает от зацикливания при рекурсии)
    visited = set()
    to_check = [start]
    while len(to_check) > 0:
        method = to_check.pop()
        key = method.name.lower()
        if key in visited:
            continue
        visited.add(key)
        if method.has_query:
            return True
        for call in method.calls:
            target = index.get(call.name.lower())
            if target:
                to_check.append(target)
    return False


def add_transitive_hints(method, index):
    already_added = set()
    for call in method.calls:
        if not call.in_loop or call.name.lower() == method.name.lower():
            continue
        key = (call.line, call.name.lower())
        if key in already_added:
            continue
        target = index.get(call.name.lower())
        if target and reaches_query(target, index):
            already_added.add(key)
            message = f"вызов {call.name} в цикле: внутри этого метода выполняется запрос"
            method.hints.append(Hint("QUERY_IN_CALLEE_IN_LOOP", call.line, message))
    method.hints.sort(key=lambda h: h.line)
