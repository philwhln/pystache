class Context(object):
    def __init__(self):
        self.name = "Elise"
        self.glytch = True
        self.binary = False
        self.value = None
    
    def numeric(self):
        return float('nan')

ctx = Context()