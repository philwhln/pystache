class Context(object):
    def __init__(self):
        self.name = "Chris"
        self.value = 10000
        self.in_ca = True

    def taxed_value(self):
        return self.value - int(self.value * 0.4)

    def greeting(self):
        return "Welcome"
    
    def farewell(self):
        return "Fair enough, right?"

ctx = Context()