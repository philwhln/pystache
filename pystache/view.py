
from pystache.context import Context
from pystache.template import Template


class ViewError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "ViewError: %s" % self.mesg


class View(object):

    RAISE_ON_MISS = False

    def __init__(self, filename=None, source=None, context=None):
        if filename is None and source is None:
            raise ViewError("No filename or source supplied.")
        if filename and not source:
            self.filename = filename
            with open(self.filename) as handle:
                self.source = handle.read()
        else:
            self.filename = filename or "<string>"
            self.source = source

        self.template = Template(self.filename, self.source)
        self.context = Context(self)
        if context:
            self.context.push(context)

    def render(self):
        return self.template.render(self.context)
