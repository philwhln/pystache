from pystache import render

class Context(object):
    def __init__(self):
        self.name = "Tater"
        self.helper = "To tinker?"
    
    def bolder(self, text):
        return "<b>" + render(text, self) + "</b> " + self.helper

ctx = Context()