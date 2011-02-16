import cgi
import os
import types

from pystache.parser import Parser
from pystache.translator import Translator


NOT_FOUND = object()


class TemplateError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "TemplateError: %s" % self.mesg

class ContextMiss(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "ContextMiss: Can't find value for: %s" % self.name


class PartialNotFound(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "PartialNotFound: %s" % self.name


class UnableToLoadPartials(Exception):
    def __str__(self):
        return "Partials require lookup or filename to be set."


class Context(object):
    def __init__(self, template, ctx=None):
        self.template = template
        self.stack = []
        if ctx:
            self.stack.append(ctx)

    def push(self, ctx):
        self.stack.append(ctx)

    def pop(self):
        self.stack.pop()

    def partial(self, name):
        if self.template.lookup:
            template = self.template.lookup.get_template(name)
            if not isinstance(template, Template):
                raise TypeError("Partials must be a template.")
        elif self.template.filename is not None:
            dirname = os.path.dirname(self.template.filename)
            fname = os.path.join(dirname, name + self.template.extension)
            if not os.path.exists(fname):
                raise PartialNotFound(name)
            template = Template(filename=fname)
        else:
            raise UnableToLoadPartials()
        return template.render(self)

    def should_raise(self):
        for c in self.stack[::-1]:
            if not hasattr(c, "RAISE_ON_MISS"):
                continue
            return getattr(c, "RAISE_ON_MISS")
        return False    

    def should_call(self, func):
        if isinstance(func, (types.BuiltinFunctionType, types.FunctionType)):
            return func.func_code.co_argcount == 0
        elif isinstance(func, (types.BuiltinMethodType, types.MethodType)):
            return func.func_code.co_argcount - 1 == 0
        else:
            return callable(func)

    def get(self, name):
        parts = name.split(".")
        ret = self.getctx(parts.pop(0))
        while ret is not NOT_FOUND and len(parts):
            curr = parts.pop(0)
            next = NOT_FOUND
            try:
                next = ret[curr]
            except (TypeError, KeyError, IndexError):
                pass
            
            if next is NOT_FOUND:
                next = getattr(ret, curr, NOT_FOUND)
            
            if next is NOT_FOUND:
                ret = next
                break
            
            if self.should_call(next):
                next = next()
        
            ret = next
        
        if ret is NOT_FOUND and self.should_raise():
            raise ContextMiss(name)
        elif ret is NOT_FOUND:
            return ""
        else:
            return ret

    def getstr(self, name):
        ret = self.get(name)
        if not isinstance(ret, basestring):
            return str(ret)
        return ret
    
    def getctx(self, name):
        ret = NOT_FOUND
        for c in self.stack[::-1]:
            try:
                ret = c[name]
                break
            except (TypeError, KeyError, IndexError):
                pass

            if ret is NOT_FOUND:
                ret = getattr(c, name, NOT_FOUND)

            if ret is NOT_FOUND:
                continue

            if self.should_call(ret):
                ret = ret()
            break

        return ret


class Template(object):
    def __init__(self, source=None, filename=None, lookup=None, extension=None):
        if filename is None and source is None:
            raise TemplateError("No filename or source supplied.")
        
        if filename is not None:
            self.filename = filename
            with open(self.filename) as handle:
                self.source = handle.read()
        else:
            self.filename = filename
            self.source = source

        assert self.source is not None

        self.lookup = lookup

        self.extension = extension
        if self.extension is None and filename is not None:
            self.extension = os.path.splitext(filename)[1]
        else:
            self.extension = ".mustache"

        self.glbls = globals()

        ast = Parser(self.source).parse()
        src = Translator(ast).translate()
        code = compile(src, self.filename or '<string>', 'exec')
        exec code in self.glbls
        if "render" not in self.glbls:
            raise TemplateError("Failed to compile template.")
        self._render = self.glbls["render"]

    def render(self, ctx=None):
        if not isinstance(ctx, Context):
            ctx = Context(self, ctx=ctx)
        return self._render(ctx)
