from .utils import *

class BSLMethod:
    def __init__(
        self,
        name,
        kind,
        directive,
        body,
        start_line,
        end_line,
        params=None,
        is_export=False,
        is_async=False,
        comment="",
        region="",
        complete=True,
    ):
        self.name = name
        self.kind = kind
        self.directive = directive
        self.body = body
        self.start_line = start_line
        self.end_line = end_line
        self.params = params if params is not None else []
        self.is_export = is_export
        self.is_async = is_async
        self.comment = comment
        self.region = region
        self.complete = complete

        self.max_nesting = 0
        self.has_query = False
        self.calls = []
        self.facts = {}
        self.hints = []

    @property
    def line_count(self):
        return self.end_line - self.start_line + 1

    @property
    def signature(self):
        param_texts = []
        for p in self.params:
            text = ("Знач " if p.by_val else "") + p.name
            if p.default:
                text += f" = {p.default}"
            param_texts.append(text)
        prefix = "Асинх " if self.is_async else ""
        suffix = " Экспорт" if self.is_export else ""
        return f"{prefix}{self.kind} {self.name}({', '.join(param_texts)}){suffix}"

    def overlaps(self, start, end):
        return self.start_line <= end and start <= self.end_line

    def numbered_body(self):
        text = self.body.replace("\r", "").rstrip("\n")
        res = []
        for i, line in enumerate(text.split("\n")):
            res.append(f"{self.start_line + i:>5}| {line}")
        return "\n".join(res)

    def hints_text(self):
        if len(self.hints) == 0:
            return ""
        lines = []
        for h in self.hints:
            lines.append(f"- строка {h.line}: {h.message}")
        return "Предупреждения статического анализа:\n" + "\n".join(lines)

    def get_context_name(self, directive):
        if directive.lower().startswith("&наклиентенасервере"):
            return "клиент и сервер"
        if is_server(directive):
            return "сервер"
        if is_client(directive):
            return "клиент"
        return "контекст неизвестен"

    def facts_text(self):
        directive = self.directive if self.directive else "директива не указана"
        return f"Контекст выполнения: {directive} ({self.get_context_name(self.directive)})"


class BSLModule:
    def __init__(self, methods, index=None):
        self.methods = methods
        self.index = index if index is not None else {}

    def get(self, name):
        return self.index.get(name.lower())

    def callees(self, method, depth=1):
        res = []
        visited = {method.name.lower()}
        current_level = [method]
        for _ in range(depth):
            next_level = []
            for item in current_level:
                for call in item.calls:
                    key = call.name.lower()
                    if key in visited:
                        continue
                    visited.add(key)
                    called = self.index.get(key)
                    if called:
                        res.append(called)
                        next_level.append(called)
            current_level = next_level
        return res

    def callers(self, method):
        res = []
        for other in self.methods:
            if other is method:
                continue
            for c in other.calls:
                if self.index.get(c.name.lower()) is method:
                    res.append(other)
                    break
        return res

    def related_text(self, method, depth=1, include_bodies=False, max_chars=4000):
        chunks = []
        total = 0
        for called in self.callees(method, depth):
            where = called.directive if called.directive else "без директивы"
            head = f"// {called.signature} [{where}, строки {called.start_line}-{called.end_line}]"
            if called.comment:
                head += "\n// " + called.comment.replace("\n", "\n// ")

            chunk = head
            if include_bodies:
                chunk = head + "\n" + called.body.rstrip()
                if total + len(chunk) > max_chars:
                    chunk = head
            if total + len(chunk) > max_chars:
                break
            chunks.append(chunk)
            total += len(chunk)

        if len(chunks) == 0:
            return ""
        return (
            "Вызываемые методы этого же модуля (для контекста):\n```bsl\n"
            + "\n\n".join(chunks)
            + "\n```"
        )


