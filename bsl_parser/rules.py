import re

LONG_METHOD_LINES = 150
DEEP_NESTING_LEVEL = 5

# Регулярки для разбора заголовков и директив
HEADER_RE = re.compile(
    r"^(?:(Асинх)\s+)?(Процедура|Функция)\s+(\w+)\s*\(",
    re.IGNORECASE,
)
END_RE = re.compile(r"^(КонецПроцедуры|КонецФункции)\b", re.IGNORECASE)
EXPORT_RE = re.compile(r"^\s*Экспорт\b", re.IGNORECASE)
PARAM_RE = re.compile(
    r"^(Знач\s+)?(\w+)\s*(?:=\s*(.+))?$",
    re.IGNORECASE | re.DOTALL,
)
REGION_START_RE = re.compile(r"^#Область\s+(.+)$", re.IGNORECASE)
REGION_END_RE = re.compile(r"^#КонецОбласти\b", re.IGNORECASE)
DIRECTIVE_RE = re.compile(r"^(&\w+(?:\([^)]*\))?)\s*(.*)$")

# Ключевые слова для подсчета вложенности и поиска транзакций
KEYWORDS_RE = re.compile(
    r"\b(КонецЦикла|Цикл|Если|КонецЕсли|Попытка|Исключение|КонецПопытки"
    r"|НачатьТранзакцию|ЗафиксироватьТранзакцию|ОтменитьТранзакцию)\b",
    re.IGNORECASE,
)

DEFINITION_PREFIX_RE = re.compile(r"(Процедура|Функция)\s+$", re.IGNORECASE)
EMPTY_EXCEPT_RE = re.compile(r"\bИсключение\b[\s;]*\bКонецПопытки\b", re.IGNORECASE)

INTERACTIVE_RE = re.compile(
    r"(?<![\w.])(?:Предупреждение|ПоказатьПредупреждение|Вопрос|ПоказатьВопрос"
    r"|ОткрытьФорму|ОткрытьФормуМодально|ОткрытьЗначение|ПоказатьЗначение"
    r"|ВвестиЗначение|ВвестиЧисло|ВвестиСтроку|ВвестиДату"
    r"|ПоказатьВводЗначения|ПоказатьВводЧисла|ПоказатьВводСтроки|ПоказатьВводДаты)\s*\(",
    re.IGNORECASE,
)
EXTERNAL_RE = re.compile(
    r"\bНовый\s+(?:HTTPСоединение|WSПрокси|WSОпределения|COMОбъект)\b"
    r"|(?<![\w.])(?:ЗапуститьПриложение|НачатьЗапускПриложения)\s*\(",
    re.IGNORECASE,
)

RULES = [
    {
        "pattern": re.compile(r"\bНовый\s+Запрос\b", re.IGNORECASE),
        "fact": "query",
        "when": "loop",
        "code": "QUERY_IN_LOOP",
        "msg": "создание запроса внутри цикла (запрос на каждую итерацию)",
    },
    {
        "pattern": re.compile(r"\.\s*Выполнить\s*\(", re.IGNORECASE),
        "fact": "query_exec",
        "when": "loop",
        "code": "QUERY_IN_LOOP",
        "msg": "выполнение запроса внутри цикла (обращение к СУБД на каждую итерацию)",
    },
    {
        "pattern": INTERACTIVE_RE,
        "fact": "interactive",
        "when": "tx",
        "code": "INTERACTIVE_IN_TRANSACTION",
        "msg": "интерактивный вызов внутри открытой транзакции (блокировки висят, пока пользователь отвечает)",
    },
    {
        "pattern": INTERACTIVE_RE,
        "fact": "interactive",
        "when": "server",
        "code": "INTERACTIVE_ON_SERVER",
        "msg": "интерактивные функции доступны только на клиенте, на сервере будет ошибка",
    },
    {
        "pattern": EXTERNAL_RE,
        "fact": "external",
        "when": "tx",
        "code": "EXTERNAL_IN_TRANSACTION",
        "msg": "обращение к внешней системе внутри открытой транзакции (долгая операция держит блокировки)",
    },
]