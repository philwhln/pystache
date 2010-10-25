import cgi

from pystache.parser import Parser
from pystache.translator import Translator


class TemplateError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "TemplateError: %s" % self.mesg


class Template(object):
    def __init__(self, filename, source):
        self.filename = filename
        self.source = source
        self.glbls = globals()

        ast = Parser(self.source).parse()
        src = Translator(ast).translate()
        code = compile(src, self.filename, 'exec')
        exec code in self.glbls
        if "render" not in self.glbls:
            raise TemplateError("Failed to compile template.")
        self.render = self.glbls["render"]

        