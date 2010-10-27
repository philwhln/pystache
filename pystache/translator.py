
from pystache.parser import (MULTI, STATIC, TAG, SECTION,
                                INV_SECTION, PARTIAL, UTAG, ETAG)


class TranslationError(object):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "TranslationError: %s" % self.mesg


class CodeWriter(object):
    def __init__(self):
        self.buf = []
        self.depth = 0

    def getvalue(self):
        return ''.join(self.buf)

    def write(self, data):
        self.buf.append("%s%s\n" % (("    " * self.depth), data))

    def stmt_(self, code):
        self.write(code)
    
    def func_(self, code):
        self.write("def %s:" % code)
        self.depth += 1

    def return_(self, code):
        self.write("return %s" % code)
        self.depth -= 1

    def cnuf_(self):
        self.depth -= 1

    def if_(self, code):
        self.write("if %s:" % code)
        self.depth += 1

    def elif_(self, code):
        self.depth -= 1
        self.write("elif %s:" % code)
        self.depth += 1
    
    def else_(self):
        self.depth -= 1
        self.write("else:")
        self.depth += 1

    def fi_(self):
        self.depth -= 1

    def for_(self, code):
        self.write("for %s:" % code)
        self.depth += 1

    def rof_(self):
        self.depth -= 1

    def try_(self):
        self.write("try:")
        self.depth += 1

    def except_(self, code=None):
        self.depth -= 1
        if code is None:
            self.write("except:")
        else:
            self.write("except %s:" % code)
        self.depth += 1

    def finally_(self):
        self.depth -= 1
        self.write("finally:")
        self.depth += 1

    def yrt_(self):
        self.depth -= 1


class Translator(object):

    def __init__(self, ast, filename=None):
        self.ast = ast
        self.w = CodeWriter()

    def translate(self):
        self.w.func_("render(ctx)")
        self.w.stmt_("buf = []")
        self.translate_ast(self.ast)
        self.w.return_("''.join(buf)")
        return self.w.getvalue()

    def translate_ast(self, ast):
        if ast[0] == STATIC:
            self.translate_static(ast[1])
        elif ast[0] == MULTI:
            self.translate_multi(ast[1:])
        elif ast[0] == TAG:
            if ast[1] == SECTION:
                self.translate_section(ast[2], ast[3], ast[4:])
            elif ast[1] == INV_SECTION:
                self.translate_inv_section(ast[2], ast[4:])
            elif ast[1] == PARTIAL:
                self.translate_partial(ast[2])
            elif ast[1] == UTAG:
                self.translate_utag(ast[2])
            elif ast[1] == ETAG:
                self.translate_etag(ast[2])
            else:
                raise TranslationError("Invalid tag type: %s" % ast[1])
        else:
            raise TranslationError("Invalid AST node type: %s" % ast[0])

    def translate_multi(self, nodes):
        for node in nodes:
            self.translate_ast(node)

    def translate_section(self, name, content, nodes):
        self.w.stmt_("v = ctx.get(%r)" % name)
        self.w.if_("v")
        self.w.if_("v == True")
        for node in nodes:
            self.translate_ast(node)
        self.w.elif_("callable(v)")
        self.w.stmt_("buf.append(v(%r))" % content)
        self.w.else_()
        self.w.if_('isinstance(v, basestring) or hasattr(v, "items")')
        self.w.stmt_("v = [v]")
        self.w.else_()
        self.w.try_()
        self.w.stmt_("v = iter(v)")
        self.w.except_("TypeError")
        self.w.stmt_("v = [v]")
        self.w.yrt_()
        self.w.fi_()
        self.w.for_("n in v")
        for node in nodes:
            self.w.stmt_("ctx.push(n)")
            self.translate_ast(node)
            self.w.stmt_("ctx.pop()")
        self.w.rof_()
        self.w.fi_()
        self.w.fi_()

    def translate_inv_section(self, name, nodes):
        self.w.stmt_("v = ctx.get(%r)" % name)
        self.w.if_("not v")
        for node in nodes:
            self.translate_ast(node)
        self.w.fi_()

    def translate_partial(self, name):
        self.w.stmt_("buf.append(ctx.partial(%r))" % name)

    def translate_etag(self, name):
        self.w.stmt_("buf.append(cgi.escape(ctx.getstr(%r), True))" % name)

    def translate_utag(self, name):
        self.w.stmt_("buf.append(ctx.getstr(%r))" % name)

    def translate_static(self, data):
        self.w.stmt_("buf.append(%r)" % data)
