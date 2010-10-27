class Item(object):
    def __init__(self, name, current, url):
        self.name = name
        self.current = current
        self.url = url
    
    def link(self):
        return not self.current

class Context(object):
    def __init__(self):
        self.item = [
            Item("red", True, "#Red"),
            Item("green", False, "#Green"),
            Item("blue", False, "#Blue")
        ]
    
    def header(self):
        return "Colors"
    
    def list(self):
        return len(self.item) != 0
    
    def empty(self):
        return len(self.item) == 0

ctx = Context()