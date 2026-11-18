class Param:
    def __init__(self, name, by_val=False, default=""):
        self.name = name
        self.by_val = by_val
        self.default = default


class Call:
    def __init__(self, name, line, in_loop):
        self.name = name
        self.line = line
        self.in_loop = in_loop


class Hint:
    def __init__(self, code, line, message):
        self.code = code
        self.line = line
        self.message = message