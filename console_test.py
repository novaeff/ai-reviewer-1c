from pathlib import Path
from bsl_parser.parser import *;
from reviewer.review_method import *;

def main():
    try:
        while True:
            target = input("\nВведите путь к файлу (или 'q' для выхода): ").strip('"\'')
            if not target or target.lower() == "q":
                break

            path = Path(target)
            if not path.is_file():
                print(f"ERR: Файл не найден: {path}")
                continue

            module = parse_module(str(path))
            if not module.methods:
                print(f"В файле {path.name} не найдено методов.")
                continue

            print(f"\nНайдено методов для проверки: {len(module.methods)}")
            print("=" * 60)

            for idx, method in enumerate(module.methods, start=1):
                print(f"\n[{idx}/{len(module.methods)}] Анализирую: {method.signature} (строки {method.start_line}–{method.end_line})...")
                try:
                    report = review_method(method, module)
                    print("-" * 40)
                    print(f"ВЕРДИКТ: {method.name}")
                    print("-" * 40)
                    print(report)
                except Exception as e:
                    print(f"ERR при вызове модели: {e}")

            print("\n" + "=" * 60)
            print("Проверка файла завершена.")
    finally:
        print("\nОсвобождение памяти...")
        unload_ollama_model()
        print("Сессия завершена.")


if __name__ == "__main__":
    main()