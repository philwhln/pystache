import cgi
import os
import re
import types

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


TAG_TYPES = ur"#\^/=!<>&{"
DEF_OTAG = u"{{"
DEF_CTAG = u"}}"
ANY_CONTENT = (u"!", u"=")
SKIP_WHITESPACE = (u"#", u"^", u"/", u"<", u">", u"=", u"!")
TAG_CONTENT_RE = ur"[\w?!\/\-]*?([\w?!\/\-]\^*)?(\.[\w?!\/\-]+)*"
NOT_FOUND = object()

# Exceptions


class PyStachError(Exception):
    pass


class ParseError(PyStachError):
    def __init__(self, mesg, pos):
        self.mesg = mesg
        self.line = pos[0]
        self.col = pos[1]

    def __str__(self):
        fmt = u"ParseError <Line %d Column %d> %s"
        return fmt % (self.line, self.col, self.mesg)


class TemplateError(PyStachError):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return u"TemplateError: %s" % self.mesg


class ContextMiss(PyStachError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return u"ContextMiss: Can't find value for: %s" % self.name


class PartialNotFound(PyStachError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return u"PartialNotFound: %s" % self.name


class UnableToLoadPartials(PyStachError):
    def __str__(self):
        return u"Partials require lookup or filename to be set."


class LookupError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg

    def __str__(self):
        return u"LookupError: %s" % self.mesg


class ContextProxy(object):
    def __init__(self, template, ctx, parent, should_raise):
        self.template = template
        self.ctx = ctx
        self.parent = parent
        if hasattr(ctx, u"RAISE_ON_MISS"):
            self.should_raise = ctx.RAISE_ON_MISS or should_raise
        else:
            self.should_raise = should_raise
    
    def render(self, writer, escaped=True):
        if self._should_call(args=0):
            data = self.cached = self.template.decode(self.ctx())
            tmpl = self.template.sub_template(data=data)
            data = tmpl.render(self)
        else:            
            data = self.template.decode(self.ctx)
        if escaped:
            data = cgi.escape(data, quote=True)
        writer.write(data)
    
    def get(self, name):
        parts = name.split(".")
        ret = self
        while len(parts):
            ret = ret._lookup(parts.pop(0))
        return ret

    def falsy(self):
        return not bool(self.ctx)

    def islambda(self):
        return self._should_call(args=1)

    def iterate(self):
        items = []
        if isinstance(self.ctx, basestring) or hasattr(self.ctx, "items"):
            items = [self.ctx]
        else:
            try:
                items = iter(self.ctx)
            except TypeError:
                items = [items]
        for item in items:
            yield ContextProxy(self.template, item, self, self.should_raise)

    def execute(self, content, ctx, writer):
        tmpl = self.template.sub_template(data=self.ctx(content))
        tmpl.render(ctx, writer=writer)

    def _lookup(self, name):
        # Check for accessing up the stack using
        # the name^^ syntax. Each ^ means we want
        # to remove a stack element.
        proxy = self
        while name[-1:] == "^" and ctx.parent is not None:
            proxy = proxy.parent
            name = name[:-1]
        # Remove any trailing markers.
        name = name.rstrip("^")

        ret = NOT_FOUND
        while proxy is not None:
            try:
                ret = proxy.ctx[name]
                break
            except (TypeError, KeyError, IndexError):
                pass
            if ret is NOT_FOUND:
                ret = getattr(proxy.ctx, name, NOT_FOUND)
            if ret is NOT_FOUND:
                proxy = proxy.parent
                continue
            break
        if ret is NOT_FOUND and self.should_raise:
            raise ContextMiss(name)
        return ContextProxy(self.template, ret, self, self.should_raise)

    def _should_call(self, args=0):
        func = self.ctx
        if isinstance(func, (types.BuiltinFunctionType, types.FunctionType)):
            return func.func_code.co_argcount == args
        elif isinstance(func, (types.BuiltinMethodType, types.MethodType)):
            return func.func_code.co_argcount - 1 == args
        else:
            return callable(func)


class Tag(object):
    def __init__(self, tagtype, name, start, end, indent):
        self.tagtype = tagtype
        self.name = name
        self.start = start
        self.end = end
        self.indent = indent


class Tokenizer(object):
    """\
    Consumes a template source and generates a sequence of
    tokens that represent the various syntactical portions
    of the source.
    """
    TAG = object()
    STATIC = object()
    
    def __init__(self, data, opts=None):
        if not isinstance(data, unicode):
            raise TypeError(u"Templates must be unicode not %s" %
                                            data.__class__.__name__)
        self.data = data
        self.opts = opts or {}
        self.compiled = {}
        self.re_match = None
        self.pos = 0
        self.otag = re.escape(self.opts.get(u"otag", DEF_OTAG))
        self.ctag = re.escape(self.opts.get(u"ctag", DEF_CTAG))
        self.any_content = set(self.opts.get(u"any_content", ANY_CONTENT))
        self.skip_ws = set(self.opts.get(u"skip_whitespace", SKIP_WHITESPACE))
        self.tag_content = self.opts.get(u"tag_content", TAG_CONTENT_RE)
    
    def __iter__(self):
        while not self.eos():
            pos = self.pos
            for tag in self.parse_tag():
                yield tag
            if not self.eos():
                static = self.parse_text()
                if static:
                    yield static
            if self.pos <= pos:
                raise self.error("Parser failed to progress.")
    
    def parse_tag(self):
        # Only silence whitespace if this tag is the only non-whitespace
        # content on the line and the tag type is in self.skip_ws
        silence_ws = self.pos == 0 or self.data[self.pos-1] == u"\n"
        
        # Find the start of the next template tag.
        match = self.match(ur"([ \t]+)?%s" % self.otag)
        if not match:
            return []
        otag_match = self.re_match
        ws_padding = otag_match.group(1) or ""
        
        # Detect the tag type if it exists.
        tagtype = self.match(ur"\s*[%s]" % TAG_TYPES)
        self.skip(ur"\s*")

        # Get the content for the current tag by finding the close
        # of the tag.
        content = self.until(ur"\s*(%s)?%s" % (tagtype, self.ctag))
        
        # Check that the tag name is valid if this isn't a comment
        # or tag switch.
        if tagtype not in self.any_content:
            if not content or not content.strip() and tagtype != u"^":
                self.error(u"Empty tag.")
            m = self.pattern(ur"^%s$" % self.tag_content).match(content)
            if not m:
                self.error(u"Invalid tag content: %s" % content)

        # Hack for prettier un-escape tags so that we
        # have {{{foo}}} instead of {{{foo{}}
        if tagtype == u"{":
            tagtype = u"}"

        # Skip space after content and optionally a repeated close
        # tag type.
        self.skip(ur"\s*(%s)?" % tagtype)
        if not self.match(self.ctag):
            self.error(u"Unclosed tag.")
        ctag_match = self.re_match

        # Unhack our un-escaped tag hack
        if tagtype == u"}":
            tagtype = u"{"
        
        # If a tag type in self.skip_ws the tag is the only non-whitespace
        # content on that line, silence that line from the output.
        if silence_ws:
            match = self.pattern(ur"[ \t]*\n").match(self.data, self.pos)
            if tagtype in self.skip_ws and match is not None:
                self.skip(ur"[ \t]*\n")
            else:
                silence_ws = False

        ret = []
        if not silence_ws and len(ws_padding):
            ret.append((self.STATIC, ws_padding))
        
        if tagtype == u"=":
            # Handle a tag update if we have one. This doesn't
            # generate a token for the parse stream.
            otag, ctag = content.split(u" ", 1)
            m = self.pattern(self.tag_content).match(ctag)
            if len(m.group(0)):
                self.error(u"Invalid close tag: %s" % ctag)
            self.otag, self.ctag = re.escape(otag), re.escape(ctag)
        else:
            # Give coordinates where this tag resides in the template
            # data stream.
            start = otag_match.start() + len(ws_padding)
            end = ctag_match.end()
            tag = Tag(tagtype, content, start, end, ws_padding)
            ret.append((self.TAG, tag))
        
        return ret
    
    def parse_text(self):
        text = self.until(u"(^[ \t]+)?%s" % self.otag, re.MULTILINE)
        # No match means rest is static
        if text is None:
            text = self.rest()
        # If text is empty, silence the empty static node
        if text:
            return (self.STATIC, text)
    
    def eos(self):
        return self.pos >= len(self.data)
    
    def match(self, pattern, flags=None):
        self.re_match = self.pattern(pattern, flags).match(self.data, self.pos)
        if not self.re_match:
            return
        self.pos = self.re_match.end()
        return self.re_match.group(0)

    def skip(self, pattern, flags=None):
        self.re_match = self.pattern(pattern, flags).match(self.data, self.pos)
        if not self.re_match:
            return
        self.pos = self.re_match.end()
    
    def until(self, pattern, flags=None):
        self.re_match = self.pattern(pattern, flags).search(self.data, self.pos)
        if not self.re_match:
            return None
        mstart = self.re_match.start()
        ret = self.data[self.pos:mstart]
        self.pos = mstart
        return ret
    
    def rest(self):
        ret = self.data[self.pos:]
        self.pos = len(self.data)
        return ret

    def pattern(self, pattern, flags=None):
        if flags is None:
            flags = 0
        ret = self.compiled.get((pattern, flags))
        if ret is None:
            ret = re.compile(pattern, flags)
            self.compiled[(pattern, flags)] = ret
        return ret

    def error(self, mesg):
        lines = self.data[:self.pos].splitlines()
        if not lines:
            lines = [u""]
        raise ParseError(mesg, (len(lines), len(lines[-1])))


class Renderable(object):
    def __init__(self, template):
        self.template = template

    def render(self, ctx, writer):
        raise NotImplementedError()


class Static(Renderable):
    def __init__(self, template, data):
        super(Static, self).__init__(template)
        self.data = data

    def render(self, ctx, writer):
        writer.write(self.data)


class Partial(Renderable):
    def __init__(self, template, name, indent=None):
        super(Partial, self).__init__(template)
        self.name = name
        self.indent = indent or ""
    
    def render(self, ctx, writer):
        tmpl = self.template.get_partial(self.name, indent=self.indent)
        return tmpl.render(ctx, writer)


class Value(Renderable):
    def __init__(self, template, name, escaped=True):
        super(Value, self).__init__(template)
        self.name = name
        self.escaped = escaped
    
    def render(self, ctx, writer):
        ctx = ctx.get(self.name)
        ctx.render(writer, escaped=self.escaped)


class Multi(Renderable):
    def __init__(self, template, parent):
        super(Multi, self).__init__(template)
        self.parent = parent
        self.sects = []

    def add(self, obj):
        self.sects.append(obj)
        return obj
    
    def render(self, ctx, writer):
        map(lambda s: s.render(ctx, writer), self.sects)


class Section(Multi):
    def __init__(self, template, parent, name, start):
        super(Section, self).__init__(template, parent)
        self.name = name
        self.start = start
        self.end = None
    
    def render(self, ctx, writer):
        ctx = ctx.get(self.name)
        if ctx.falsy():
            return
        elif ctx.islambda():
            content = self.template.subdata(self.start, self.end)
            ctx.execute(content, ctx, writer)
        else:
            for item in ctx.iterate():
                super(Section, self).render(item, writer)


class InvSection(Multi):
    def __init__(self, template, parent, name, start):
        super(InvSection, self).__init__(template, parent)
        self.name = name
        self.start = start
        self.end = None
    
    def render(self, ctx, writer):
        ctx = ctx.get(self.name)
        if ctx.falsy():
            super(InvSection, self).render(ctx, writer)


class Writer(object):
    def __init__(self):
        self.buf = []
    
    def write(self, data):
        assert isinstance(data, unicode)
        self.buf.append(data)
    
    def getvalue(self):
        ret = u"".join(self.buf)
        assert isinstance(ret, unicode)
        return ret


class TemplateOptions(object):
    def __init__(self, opts):
        self.extension = opts.get("extension", None)
        self.lookup = opts.get("lookup", None)
        self.charset = opts.get("charset", "utf-8")
        self.encoding_errors = opts.get("encoding-errors", "replace")

    def get(self, name, default):
        return getattr(self, name, default)

class Template(object):
    def __init__(self, data=None, filename=None, partials=None, opts=None):
        self.data = data
        self.filename = filename
        self.partials = partials or {}

        if isinstance(opts, TemplateOptions):
            self.opts = opts
        else:
            self.opts = TemplateOptions(opts or {})

        if self.data is None and self.filename is None:
            raise RuntimeError(u"Templates require either data or a filename.")

        if self.opts.extension is None and self.filename is not None:
            self.opts.extension = os.path.splitext(self.filename)[-1]

        if self.data is None:
            with open(self.filename) as handle:
                self.data = handle.read()
        
        if isinstance(self.data, str):
            self.data = self.decode(self.data)

        self.root = self.parse(self.data)

    def sub_template(self, data=None, filename=None, **kwargs):
        kwargs.setdefault("data", data)
        kwargs.setdefault("filename", filename)
        kwargs.setdefault("partials", self.partials)
        kwargs.setdefault("opts", self.opts)
        return Template(**kwargs)

    def render(self, context, writer=None):
        if not isinstance(context, ContextProxy):
            context = ContextProxy(self, context, None, False)
        if writer:
            self.root.render(context, writer)
        else:
            writer = Writer()
            self.root.render(context, writer)
            return writer.getvalue()

    def get_partial(self, name, indent=None):
        if name in self.partials:
            tmpl = self.redent(self.partials[name], indent=indent)
            return Template(tmpl, partials=self.partials, opts=self.opts)
        elif self.opts.lookup:
            # I have to fix the indentiation issue for partials because
            # the Ruby version dictates this as part of the spec.
            raise NotImplementedError()
            # template = self.lookup.get_template(name, indent=indent)
            # if not isinstance(template, Template):
            #     raise TypeError(u"Partials must be a template.")
            # return template
        elif self.filename is not None:
            # I have to fix the indentiation issue for partials because
            # the Ruby version dictates this as part of the spec.
            raise NotImplementedError()
            # dirname = os.path.dirname(self.filename)
            # fname = os.path.join(dirname, name + self.extension)
            # if not os.path.exists(fname):
            #     raise PartialNotFound(name)
            # return Template(filename=fname, lookup=self.lookup, opts=self.opts)
        raise UnableToLoadPartials()

    def parse(self, data):
        tokenizer = Tokenizer(data, opts=self.opts)
        root = Multi(self, None)
        curr = root
        for tok in tokenizer:
            if tok[0] == Tokenizer.STATIC:
                curr.add(Static(self, tok[1]))
            elif tok[1].tagtype == u"!":
                # Ignore comments
                pass
            elif tok[1].tagtype == u"#":
                curr = curr.add(Section(self, curr, tok[1].name, tok[1].end))
            elif tok[1].tagtype == u"^" and tok[1].name:
                curr = curr.add(InvSection(self, curr, tok[1].name, tok[1].end))
            elif tok[1].tagtype == u"^":
                if curr.parent is None:
                    tokenizer.error(u"Else tag with no section.")
                curr.parent.end = tok[1].start
                sect = InvSection(self, curr, tok[1].name, tok[1].end)
                curr = curr.parent.add(sect)
            elif tok[1].tagtype == u"/":
                if curr.parent is None:
                    tokenizer.error(u"Stray close tag: %s" % tok[1].name)
                if tok[1].name != curr.name:
                    mesg = u"Mismatched tags: %s, %s"
                    tokenizer.error(mesg % (curr.name, tok[1].name))
                curr.end = tok[1].start
                curr = curr.parent
            elif tok[1].tagtype in (u"<", u">"):
                curr.add(Partial(self, tok[1].name, indent=tok[1].indent))
            elif tok[1].tagtype in (u"{", u"&"):
                curr.add(Value(self, tok[1].name, escaped=False))
            else:
                curr.add(Value(self, tok[1].name))
        if curr is not root:
            tokenizer.error("Unclosed section: %s" % curr.name)
        return root
    
    def subdata(self, start, end):
        return self.data[start:end]
    
    def redent(self, data, indent):
        lines = [u"%s%s" % (indent, l) for l in data.splitlines()]
        if data[-1] == "\n":
            lines.append(u"")
        return self.decode(os.linesep).join(lines)
    
    def decode(self, val):
        if isinstance(val, unicode):
            return val
        elif isinstance(val, str):
            charset = self.opts.get(u"charset", u"utf-8")
            errors = self.opts.get(u"errors", u"replace")
            return val.decode(charset, errors)
        else:
            return unicode(val)


class TemplateInfo(object):
    def __init__(self, fname, template_opts):
        self.fname = fname
        self.mtime = os.stat(fname).st_mtime
        self.template_opts = template_opts
        self.template = Template(filename=self.fname, **self.template_opts)
        self.lock = threading.Lock()

    def recheck_fs(self):
        mtime = os.stat(self.fname).st_mtime
        with self.lock:
            if mtime == self.mtime:
                return
            self.mtime = mtime
            self.template = Template(filename=self.fname, **self.template_opts)


class TemplateLookup(object):
    def __init__(self, directories, extension=None,
                            filesystem_checks=False, template_opts=None):

        self.templates = {}

        if isinstance(directories, basestring):
            directories = [directories]
        self.directories = [self.process_dir(d) for d in directories]

        self.extension = extension or ".mustache"
        if not self.extension.startswith("."):
            self.extension = "." + self.extension

        self.filesystem_checks = filesystem_checks
        self.template_opts = template_opts or {}

        if "extension" not in self.template_opts:
            self.template_opts["extension"] = self.extension

        if "lookup" not in self.template_opts:
            self.template_opts["lookup"] = self

        self.lock = threading.Lock()

    def get_template(self, name):
        tmplinfo = self.templates.get(name, None)
        if not tmplinfo:
            tmplinfo = self.load_template(name)
        if self.filesystem_checks:
            tmplinfo.recheck_fs()
        return tmplinfo.template

    def load_template(self, name):
        with self.lock:
            try:
                return self.templates[name]
            except KeyError:
                pass
            ret = TemplateInfo(self.find_template(name), self.template_opts)
            self.templates[name] = ret
            return ret

    def find_template(self, name):
        for d in self.directories:
            path = self.process_dir(os.path.join(d, name))
            if os.path.commonprefix([d, path]) != d:
                # Only allow template names to reference a subpath
                # of the list of directories.
                continue
            path = os.path.normpath(os.path.join(d, name))
            fname = os.path.join(d, name)
            for fn in [fname, fname + self.extension]:
                if os.path.exists(fn):
                    return fn
        raise LookupError("Failed to find template: %s" % name)

    def process_dir(d):
        return os.path.normpath(os.path.abspath(d))


