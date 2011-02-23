from __future__ import with_statement

import cgi
import hashlib
import os
import re
import threading
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


class PystacheError(Exception):
    pass


class ParseError(PystacheError):
    def __init__(self, mesg, pos):
        self.mesg = mesg
        self.line = pos[0]
        self.col = pos[1]

    def __str__(self):
        fmt = u"ParseError <Line %d Column %d> %s"
        return fmt % (self.line, self.col, self.mesg)


class TemplateError(PystacheError):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return u"TemplateError: %s" % self.mesg


class ContextMiss(PystacheError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return u"ContextMiss: Can't find value for: %s" % self.name


class PartialNotFound(PystacheError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return u"PartialNotFound: %s" % self.name


class UnableToLoadPartials(PystacheError):
    def __str__(self):
        return u"Partials require lookup or filename to be set."


class LookupError(PystacheError):
    def __init__(self, mesg):
        self.mesg = mesg

    def __str__(self):
        return u"LookupError: %s" % self.mesg


class Tag(object):
    """\
    An internal object emitted by the tokenizer and consumed by
    the template parsing to create templates.
    """
    def __init__(self, tagtype, name, start, end):
        self.tagtype = tagtype
        self.name = name
        self.start = start
        self.end = end


class Renderable(object):
    """\
    Root class of a shallow class hiearchy responsible for representing
    a parsed template.
    """
    def __init__(self, template):
        self.template = template

    def render(self, ctx, writer):
        raise NotImplementedError()


class Static(Renderable):
    """\
    Static nodes are used to represent the text not involved with
    dynamic aspects of the template. For instance the template:
    
        Items {{#dots}}.{{/dots}} done.
        
    Has three Static nodes: "Items ", ".", and " done."
    """
    def __init__(self, template, data):
        super(Static, self).__init__(template)
        self.data = data

    def render(self, ctx, writer):
        writer.write(self.data)


class Partial(Renderable):
    """\
    Partials are sub-templates that are evaluated and rendered during
    the render phase of a template (as opposed to parse phase).
    """
    def __init__(self, template, name):
        super(Partial, self).__init__(template)
        self.name = name

    def render(self, ctx, writer):
        tmpl = self.template.get_partial(self.name)
        return tmpl.render(ctx, writer)


class Value(Renderable):
    """\
    Value nodes are a representation of simple variable substitution
    using tags like {{foo}} or {{{foo}}}.
    """
    def __init__(self, template, name, escaped=True):
        super(Value, self).__init__(template)
        self.name = name
        self.escaped = escaped

    def render(self, ctx, writer):
        ctx = ctx.get(self.name)
        ctx.render(writer, escaped=self.escaped)


class Multi(Renderable):
    """\
    Multi nodes can contain multiple sub-nodes that may be rendered
    conditionally. Currently only the internal root node and sections
    have this property.
    """
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
    """\
    A Section represents part of a template that may be conditionally
    rendered, rendered multiple times, or passed to a callable to
    be evaluated.
    """
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
            content = self.template.sub_data(self.start, self.end)
            ctx.execute(content, ctx, writer)
        else:
            for item in ctx.iterate():
                super(Section, self).render(item, writer)


class InvSection(Multi):
    """\
    An InvSection (inverted section) is part of a template that is
    rendered when its tag evalutes as falsy.
    """
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
    """\
    This is the default class used for rendering templates. Users
    can specify a writer kwarg to the render methods that will
    replace the use of this class.
    
    Replacements only need to support the write(data) method. When
    a custom writer is used, nothing is returned from the render
    methods.
    """
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
    """\
    An class that represents the options provided to a template during
    instantiation. Options here are sequestered to an instance to ease
    the instantiation of sub-templates for situations like partials.
    
    `opts` is a dict or instance of TemplateOptions.
    
    Supported options are:
    
        extension   - The filename extension for templates.
        lookup      - An instance of TemplateLookup or any instance that has
                      a `get_template(name)` method.
        charset     - The character set to use when decoding non-unicode
                      data. Default is 'utf-8'. Can be anything that
                      `str.decode` accepts.
        errors      - The action to take for decoding errors. Default is
                      `replace` but can be anything that `str.decode` accepts.
    """
    def __init__(self, opts):
        self.extension = opts.get("extension", ".mustache")
        self.lookup = opts.get("lookup", None)
        self.charset = opts.get("charset", "utf-8")
        self.encoding_errors = opts.get("encoding-errors", "replace")

    def get(self, name, default):
        return getattr(self, name, default)


class TemplateInfo(object):
    """\
    An internal class that represents a template loaded from disk
    for use by the TemplateLoader to keep track of loaded Templates.
    """
    def __init__(self, fname, check_fs, tmpl_opts):
        self.fname = fname
        self.check_fs = check_fs
        self.tmpl_opts = tmpl_opts
        self.lock = threading.Lock()
        self.template = None
        self.mtime = None
        self.load_template()

    def get_template(self):
        with self.lock:
            if not self.check_fs:
                return self.template
        return self.load_template()

    def load_template(self):
        with self.lock:
            self.mtime = os.stat(self.fname).st_mtime
            self.template = Template(filename=self.fname, opts=self.tmpl_opts)
            return self.template


class TemplateLookup(object):
    """\
    The API required for TemplateLookup instances. This is defined so
    that people are aware that `get_template(name)` is used when loading
    partials for templates retreived from a lookup instance. Its not
    a requirement that lookups subclass TemplateLookup.
    """
    def get_template(self, name):
        raise NotImplementedError()


class TemplateFileLookup(TemplateLookup):
    """\
    This class is used to allow for the loading of templates from the
    filesystem using a set of directories as search paths. When a Template
    is instantiated with a lookup it will also be used to locate files for
    partials.
    
    directories - The list of directories to search.
    ext         - When attempting to locate a template, the provided name
                  will be used. If that check fails a second atttempt will
                  use the same name with this filename extension. This
                  allows users to dispense repeating filename extensions
                  when requesting templates (or in partials).
    check_fs    - Whether to recheck the filesystem to see if a template
                  has changed. This check is based on file modification
                  time.
    tmpl_opts   - Passed as the opts keyword arg to the Template constructor.
    """
    def __init__(self, directories, ext=None, check_fs=False, tmpl_opts=None):

        if isinstance(directories, basestring):
            directories = [directories]
        self.directories = [self.process_dir(d) for d in directories]
        
        self.recheck_fs = recheck_fs

        extension = extension or ".mustache"
        if extension[:1] != ".":
            extension = "." + extension
        if tmpl_opts is None:
            tmpl_opts = {}
        tmpl_opts.setdefault("extension", extension)
        tmpl_opts.setdefault("lookup", self)
        self.tmpl_opts = TemplateOptions(tmpl_opts)
        
        self.templates = {}
        self.lock = threading.Lock()

    def get_template(self, name):
        with self.lock:
            tinfo = self.templates.get(name, None)
        if tinfo is not None:
            return tinfo.get_template()
        return self.load_template(name).get_template()

    def load_template(self, name):
        with self.lock:
            try:
                return self.templates[name]
            except KeyError:
                pass
            fname = self.find_template(name)
            tinfo = TemplateInfo(fname, self.check_fs, self.tmpl_opts)
            self.templates[name] = tinfo
            return tinfo

    def find_template(self, name):
        for d in self.directories:
            fname = self.process_dir(os.path.join(d, name))
            if os.path.commonprefix([d, fname]) != d:
                # Only allow template names to reference a subpath
                # of the list of directories.
                continue
            for fn in [fname, fname + self.extension]:
                if os.path.exists(fn):
                    return fn
        raise LookupError("Failed to find template: %s" % name)

    def process_dir(d):
        return os.path.normpath(os.path.abspath(d))


class TemplateDictLookup(TemplateLookup):
    """\
    An implementation of TemplateLookup that retrieves template data
    from a provided dict of templates. This class should not be used
    in production because it does not cache templates and must reparse
    each template everytime it is loaded.
    """
    def __init__(self, partials, tmpl_opts=None):
        self.partials = partials

        tmpl_opts = tmpl_opts or {}
        tmpl_opts.setdefault("lookup", self)
        self.tmpl_opts = TemplateOptions(tmpl_opts)

    def get_template(self, name):
        if name not in self.partials:
            raise LookupError("Failed to find template: %s" % name)
        return Template(data=self.partials[name], opts=self.tmpl_opts)


class ContextProxy(object):
    """\
    This object manages the access to a context variable that is used
    to answer queries for tag names in a template. When a template is
    rendered this class answers requests for attributes or items
    contained in the user supplied data.
    """
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
            tag = Tag(tagtype, content, start, end)
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


class Template(object):
    """\
    A Template object is responsible for parsing the tokenized source
    as well as dispatching render requests to the root renderable
    instance.
    
    data        - Raw template data as a string. If this is not a unicode
                  string an attempt to decode it is made using the encoding
                  options passed in the `opts` paramter.
    filename    - Instead of passing the raw data in the `data` kwarg you
                  can specify a filename for the template. If both `data`
                  and `filename` are passed, the `filename` will be used
                  to find partials and to specify a template filename
                  extension. Files will be decoded according to the
                  encoding options passed in the `opts` paramter.
    opts        - Various configuration settings that control template
                  rendering. See the `TemplateOptions` class for a description
                  of the accepted options.
    """
    def __init__(self, data=None, filename=None, opts=None):
        self.data = data
        self.filename = filename

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

    def render(self, context, writer=None):
        if not isinstance(context, ContextProxy):
            context = ContextProxy(self, context, None, False)
        if writer:
            self.root.render(context, writer)
        else:
            writer = Writer()
            self.root.render(context, writer)
            return writer.getvalue()

    def get_partial(self, name):
        if self.opts.lookup:
            tmpl = self.opts.lookup.get_template(name)
            assert isinstance(tmpl, Template), "Invalid template instance."
            return tmpl
        elif self.filename is not None:
            dirname = os.path.dirname(self.filename)
            fname = os.path.join(dirname, name + self.extension)
            if not os.path.exists(fname):
                raise PartialNotFound(name)
            return self.sub_template(filename=filename)
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
                curr.add(Partial(self, tok[1].name))
            elif tok[1].tagtype in (u"{", u"&"):
                curr.add(Value(self, tok[1].name, escaped=False))
            else:
                curr.add(Value(self, tok[1].name))
        if curr is not root:
            tokenizer.error("Unclosed section: %s" % curr.name)
        return root
    
    def sub_template(self, data=None, filename=None, **kwargs):
        kwargs.setdefault("data", data)
        kwargs.setdefault("filename", filename)
        kwargs.setdefault("opts", self.opts)
        return Template(**kwargs)
    
    def sub_data(self, start, end):
        return self.data[start:end]
    
    def decode(self, val):
        if isinstance(val, unicode):
            return val
        elif isinstance(val, str):
            charset = self.opts.get(u"charset", u"utf-8")
            errors = self.opts.get(u"errors", u"replace")
            return val.decode(charset, errors)
        else:
            return unicode(val)


def render(template, context, **kwargs):
    t = Template(data=template, **kwargs)
    return t.render(context)

