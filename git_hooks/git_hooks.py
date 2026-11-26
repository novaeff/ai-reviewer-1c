import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bsl_parser.parser import methods_in_ranges, parse_module
from reviewer.review_method import review_method, unload_ollama_model

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def get_staged_bsl_changes() -> dict[str, list[tuple[int, int]]]:
    """Возвращает словарь: {путь_к_файлу: [(начало_строки, конец_строки)]}."""
    cmd = ["git", "diff", "--cached", "-U0", "--diff-filter=ACM", "--", "*.bsl"]
    res = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if res.returncode != 0:
        print(f"Ошибка вызова git diff: {res.stderr}", file=sys.stderr)
        return {}

    changes: dict[str, list[tuple[int, int]]] = {}
    current_file = None

    for line in res.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            changes.setdefault(current_file, [])
        elif line.startswith("@@ ") and current_file:
            m = _HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                if count > 0:  # count == 0 означает, что строки только удалялись
                    changes[current_file].append((start, start + count - 1))

    # Оставляем только файлы, где реально добавлялись или менялись строки
    return {path: ranges for path, ranges in changes.items() if ranges}


def main() -> int:
    changes = get_staged_bsl_changes()
    if not changes:
        return 0  # Изменений в файлах нет — пропускаем коммит

    print("\n" + "=" * 60)
    print("Запуск локального AI код-ревьюера для изменённых методов...")
    print("=" * 60)

    has_issues = False

    try:
        for rel_path, ranges in changes.items():
            path = Path(rel_path)
            if not path.is_file():
                continue

            module = parse_module(str(path))
            changed_methods = methods_in_ranges(module.methods, ranges)

            # Собираем и сами изменённые методы, и тех, кто их вызывает внутри модуля
            target_methods = []
            seen_names = set()

            for m in changed_methods:
                if m.name.lower() not in seen_names:
                    seen_names.add(m.name.lower())
                    target_methods.append(m)

                for caller in module.callers(m):
                    if caller.name.lower() not in seen_names:
                        seen_names.add(caller.name.lower())
                        target_methods.append(caller)

            if not target_methods:
                continue

            print(f"\nФайл: {rel_path} (затронуто методов: {len(target_methods)})")

            for method in target_methods:
                print(
                    f" -> Проверяю: {method.signature} "
                    f"(строки {method.start_line}–{method.end_line})..."
                )
                try:
                    report = review_method(method, module).strip()
                except Exception as e:
                    print(f"    [!] Ошибка обращения к Ollama: {e}")
                    continue

                print("-" * 40)
                print(report)
                print("-" * 40)

                # Если ответ не начинается с "Замечаний нет", считаем это дефектом
                if not report.lower().startswith("замечаний нет"):
                    has_issues = True

    finally:
        unload_ollama_model()

    if has_issues:
        print("\n[ОТКЛОНЕНО] Найдены замечания в коде. Исправьте их перед коммитом.")
        print("(Для принудительного коммита в обход проверки: git commit --no-verify)")
        return 1

    print("\n[ОК] Замечаний к изменённому коду нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())