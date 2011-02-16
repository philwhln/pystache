import re

class ParseError(Exception):
    
    FMT = "ParseError <Line %d Column %d> %s"
    
    def __init__(self, mesg, pos):
        self.mesg = mesg
        self.line = pos[0]
        self.col = pos[1]
    
    def __str__(self):
        return self.FMT % (self.line, self.col, self.mesg)


class CONST(object):
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return "<%s>" % self.name
    def __repr__(self):
        return self.__str__()


MULTI = CONST("Multi")
STATIC = CONST("Static")
TAG = CONST("Tag")
SECTION = CONST("Section")
INV_SECTION = CONST("Inverted Section")
PARTIAL = CONST("Partial")
UTAG = CONST("Unescaped Tag")
ETAG = CONST("Escaped Tag")


class Scanner(object):
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.compiled = {}
        self.re_match = None
    
    def eos(self):
        return self.pos >= len(self.data)
    
    def match(self, pattern):
        self.re_match = self.pattern(pattern).match(self.data, self.pos)
        if not self.re_match:
            return
        self.pos = self.re_match.end()
        return self.re_match.group(0)
    
    def skip(self, pattern):
        self.re_match = self.pattern(pattern).match(self.data, self.pos)
        if not self.re_match:
            return
        self.pos = self.re_match.end()
        
    def until(self, pattern):
        self.re_match = self.pattern(pattern).search(self.data, self.pos)
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
    
    def pattern(self, pattern):
        ret = self.compiled.get(pattern)
        if ret is None:
            ret = re.compile(pattern)
            self.compiled[pattern] = ret
        return ret


class Parser(object):
    def __init__(self, source, opts=None):
        self.source = source
        self.scanner = Scanner(self.source)
        opts = opts or {}
        self.otag = re.escape(opts.get("otag", "{{"))
        self.ctag = re.escape(opts.get("ctag", "}}"))
        self.tag_content = opts.get("tag_content", r"[\w?!\/\-\.]*")
        self.any_content = opts.get("any_content", ["!", "="])
        self.skip_newline = opts.get("skip_newline", ['#', '^', '/'])

    def parse(self):
        self.sections = []
        self.result = [MULTI]
        
        while not self.scanner.eos():
            if not self.parse_tag() and not self.scanner.eos():
                self.parse_text()

        if len(self.sections):
            raise ParseError("Unclosed section.", self._pos())
            
        return self.result
        
    def parse_tag(self):
        match = self.scanner.match(self.otag)
        if not match:
            return
        otag_match = self.scanner.re_match
        
        # Tags can be switched as we parse the template. So we
        # store the current tag in case its about to be changed.
        curr_ctag = self.ctag
        tagtype = self.scanner.match(r"[#^/=!<>&{]")
        self.scanner.skip(r"\s*")
        
        # Comments and tag switching aren't bound by the rules for
        # tag content. For normal tags, check that the content matches
        # the tag_content pattern.
        content = self.scanner.until(r"\s*(%s)?%s" % (tagtype, curr_ctag))
        if content and tagtype not in self.any_content:
            m = self.scanner.pattern("^%s$" % self.tag_content).match(content)
            if not m:
                pos = self._pos()
                raise ParseError("Invalid tag content: %s" % content, pos)
        if content is None or not len(content) and tagtype != "^":
            raise ParseError("Empty tag.", self._pos())
        
        if tagtype == "#":
            block = [MULTI]
            self.result.append([TAG, SECTION, content, None, block])
            self.sections.append([content, None, self.result])
            self.result = block
        elif tagtype == "^" and content:
            # This is an inverted section (not an else)
            block = [MULTI]
            self.result.append([TAG, INV_SECTION, content, None, block])
            self.sections.append([content, None, self.result])
            self.result = block
        elif tagtype == "^":
            # An else block. Basic implementation is to close previous
            # section and open an inverted section.
            # Close:
            if not len(self.sections):
                raise ParseError("Hanging else section.", self._pos())
            # Append an empty static section for translation
            if self.result == [MULTI]:
                self.result.append([STATIC, ""])
            section, ctag_match, result = self.sections.pop(-1)
            self.result = result
            # Check we're else'ing a normal section
            if self.result[-1][1] != SECTION:
                mesg = "Invalid section for else: %s" % self.result[1]
                raise ParseError(mesg, self._pos())
            # Store content for lambdas.
            start = ctag_match.end()
            end = otag_match.start()
            self.result[-1][3] = self.source[start:end]
            # Open:
            block = [MULTI]
            self.result.append([TAG, INV_SECTION, section, None, block])
            self.sections.append([section, None, self.result])
            self.result = block            
        elif tagtype == "/":
            if not len(self.sections):
                raise ParseError("Closing unopened: %s" % content, self._pos())
            # If the section was empty, include an empty static
            # section so that translating doesn't break.
            if self.result == [MULTI]:
                self.result.append([STATIC, ""])
            section, ctag_match, result = self.sections.pop(-1)
            self.result = result
            # Close tag must match the open tag.
            if section != content:
                raise ParseError("Unclosed section: %s" % section, self._pos())
            # Store contents for passing to a lambda
            start = ctag_match.end() # End of open tag
            end = otag_match.start() # Start of close tag
            self.result[-1][3] = self.source[start:end]
        elif tagtype == "!":
            pass # Ignore comments
        elif tagtype == "=":
            otag, ctag = content.split(' ', 1)
            m = self.scanner.pattern(self.tag_content).match(ctag)
            if len(m.group(0)):
                raise ParseError("Invalid close tag: %s" % ctag, self._pos())
            self.otag, self.ctag = re.escape(otag), re.escape(ctag)
        elif tagtype == ">" or tagtype == "<":
            self.result.append([TAG, PARTIAL, content])
        elif tagtype == "{" or tagtype == "&":
            # Hack for prettiness
            if tagtype == "{":
                tagtype = "}"
            self.result.append([TAG, UTAG, content])
        else:
            self.result.append([TAG, ETAG, content])
        
        self.scanner.skip("\s*")
        self.scanner.skip("(%s)?" % tagtype)
        
        # Check for the close tag.
        if not self.scanner.match(curr_ctag):
            raise ParseError("Unclosed tag.", self._pos())
        
        # Mark end of tag for section content
        if tagtype == "#" or tagtype == "^":
            self.sections[-1][1] = self.scanner.re_match

        if tagtype in self.skip_newline:
            self.scanner.skip("\n")
        
    def parse_text(self):
        text = self.scanner.until(self.otag)
        # No match means rest is static.
        if text is None:
            text = self.scanner.rest()
        # If text is empty, silence the empty
        # static node.
        if text:
            self.result.append([STATIC, text])

    def _pos(self):
        data = self.scanner.data[:self.scanner.pos]
        lines = data.splitlines()
        if not lines:
            lines = [""]
        return (len(lines), len(lines[-1]))
