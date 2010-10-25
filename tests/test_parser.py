import t

import pystache.parser as p

def test_empty():
    r = p.Parser("")
    r.parse()
    t.eq(r.result, [p.MULTI])

def test_basic():
    r = p.Parser("foo")
    r.parse()
    t.eq(r.result, [p.MULTI, [p.STATIC, "foo"]])

def test_tag():
    tests = [
        "{{foo}}",
        "{{ foo}}",
        "{{foo }}",
        "{{ foo }}",
        "{{\tfoo\t}}"
    ]
    def run_tag_test(data):
        r = p.Parser(data)
        r.parse()
        t.eq(r.result, [p.MULTI, [p.TAG, p.ETAG, "foo"]])
    for case in tests:
        yield run_tag_test, case

def test_unescaped_tag():
    tests = [
        "{{{foo}}}",
        "{{{ foo}}}",
        "{{{foo }}}",
        "{{{ foo }}}",
        "{{&foo}}",
        "{{&foo&}}",
        "{{& foo&}}",
        "{{&foo &}}",
        "{{& foo &}}"
    ]
    def run_unescaped_tag_test(data):
        r = p.Parser(data)
        r.parse()
        t.eq(r.result, [p.MULTI, [p.TAG, p.UTAG, "foo"]])
    for case in tests:
        yield run_unescaped_tag_test, case
    t.raises(p.ParseError, p.Parser("{{{foo}}").parse)

def test_comments_ignored():
    tests = [
        "{{! some stuff here.... }}",
        "{{!       \t\r\nand yeah buddy}}",
        "{{!adfasdf \r\t\n}}"
    ]
    def run_comment_test(data):
        r = p.Parser(data)
        r.parse()
        t.eq(r.result, [p.MULTI])
    for case in tests:
        yield run_comment_test, case
    t.raises(p.ParseError, p.Parser("{{!}}").parse)

def test_alternate_tags():
    tests = [
        ("{{=<{ }>}}", [p.MULTI]),
        ("{{=<{ }>=}}", [p.MULTI]),
        ("{{=<{ }>}}<{foo}>", [p.MULTI, [p.TAG, p.ETAG, "foo"]]),
        ("{{=<{ }>}}{{foo}}", [p.MULTI, [p.STATIC, "{{foo}}"]]),
        ("{{=<{ }>}}<{foo}><{={{ }}}>{{bar}}",
            [p.MULTI, [p.TAG, p.ETAG, "foo"], [p.TAG, p.ETAG, "bar"]])
    ]
    def run_alternate_tag_test(data):
        r = p.Parser(data[0])
        r.parse()
        t.eq(r.result, data[1])
    for case in tests:
        yield run_alternate_tag_test, case
    t.raises(p.ParseError, p.Parser("{{=5 5}}").parse)

def _sect_tests(tagtype, const):
    tests = [
        ("{{%sfoo}}{{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", [p.MULTI]]]
        ),
        ("{{%sfoo}}{{bar}}{{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", [
                p.MULTI, [p.TAG, p.ETAG, "bar"]
            ]]]
        ),
        ("{{%sfoo}}{{%sbar}}{{/bar}}{{/foo}}" % (tagtype, tagtype),
            [p.MULTI, [p.TAG, const, "foo", [
                p.MULTI, [p.TAG, const, "bar", [p.MULTI]]
            ]]]
        ),
        ("{{%sfoo}}{{/foo}}{{%sbar}}{{/bar}}" % (tagtype, tagtype),
            [p.MULTI,
                [p.TAG, const, "foo", [p.MULTI]],
                [p.TAG, const, "bar", [p.MULTI]]
            ]
        )
    ]
    def run_section_test(data):
        r = p.Parser(data[0])
        r.parse()
        t.eq(r.result, data[1])
    for case in tests:
        yield run_section_test, case

    tests = [
        "{{%sfoo}}" % tagtype,
        "{{%sfoo}}{{%sbar}}" % (tagtype, tagtype),
        "{{/foo}}",
        "{{/foo}}{{/bar}}",
        "{{%sfoo}}{{%sbar}}{{/foo}}{{/bar}}" % (tagtype, tagtype),
        "{{%sfoo}}{{/bar}}{{/foo}}" % tagtype,
        "{{%sfoo}}{{/foo}}{{/bar}}" % tagtype
    ]
    def run_section_error_test(data):
        t.raises(p.ParseError, p.Parser(data).parse)
    for case in tests:
        yield run_section_error_test, case

def test_section():
    for t in _sect_tests("#", p.SECTION):
        yield t
    for t in _sect_tests("^", p.INV_SECTION):
        yield t

def test_partials():
    tests = [
        "{{<name}}",
        "{{<name<}}",
        "{{>name}}",
        "{{>name>}}",
        "{{> name}}",
        "{{> name }}",
        "{{<name }}",
        "{{< name <}}",
        "{{< name<}}",
        "{{<\tname\t<}}",
    ]
    def run_partials_test(case):
        r = p.Parser(case)
        r.parse()
        t.eq(r.result, [p.MULTI, [p.TAG, p.PARTIAL, "name"]])
    for case in tests:
        yield run_partials_test, case
    
    tests = [
        "{{<}}",
        "{{>}}",
        "{{<foo>}}",
        "{{>bar<}}"
    ]
    def run_partials_error_test(case):
        t.raises(p.ParseError, p.Parser(case).parse)
    for case in tests:
        yield run_partials_error_test, case


def test_error():
    try:
        p.Parser("{{").parse()
    except p.ParseError, inst:
        t.eq(inst.mesg, "Empty tag.")
        t.eq(inst.line, 1)
        t.eq(inst.col, 2)
        str(inst) # Doesn't raise
    else:
        t.eq(1, 0)
    
# for coverage
def test_const():
    t.eq(repr(p.MULTI), "<Multi>")
    t.eq(str(p.MULTI), "<Multi>")