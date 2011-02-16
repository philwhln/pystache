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

def test_tag_content():
    tests = [
        ("{{abcdefghijklmnopqrstuvwxyz}}", "abcdefghijklmnopqrstuvwxyz"),
        ("{{ABCDEFGHIJKLMNOPQRSTUVWXYZ}}", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        ("{{01234567890}}", "01234567890"),
        ("{{?!/-_}}", "?!/-_"),
    ]
    def run_tag_content_test(data):
        r = p.Parser(data[0])
        r.parse()
        t.eq(r.result, [p.MULTI, [p.TAG, p.ETAG, data[1]]])
    for case in tests:
        yield run_tag_content_test, case

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
            [p.MULTI, [p.TAG, const, "foo", "", [p.MULTI, [p.STATIC, ""]]]]
        ),
        ("{{%sfoo}}{{bar}}{{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", "{{bar}}", [
                p.MULTI, [p.TAG, p.ETAG, "bar"],
            ]]]
        ),
        ("{{%sfoo}} {{bar}}{{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", " {{bar}}", [
                p.MULTI, [p.STATIC, " "], [p.TAG, p.ETAG, "bar"]
            ]]]
        ),
        ("{{%sfoo}}{{bar}} {{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", "{{bar}} ", [
                p.MULTI, [p.TAG, p.ETAG, "bar"], [p.STATIC, " "]
            ]]]
        ),
        ("{{%sfoo}} {{bar}} {{/foo}}" % tagtype,
            [p.MULTI, [p.TAG, const, "foo", " {{bar}} ", [
                p.MULTI,
                [p.STATIC, " "],
                [p.TAG, p.ETAG, "bar"],
                [p.STATIC, " "]
            ]]]
        ),
        ("{{%sfoo}}{{%sbar}}{{/bar}}{{/foo}}" % (tagtype, tagtype),
            [p.MULTI, [p.TAG, const, "foo", "{{%sbar}}{{/bar}}" % tagtype, [
                p.MULTI, [p.TAG, const, "bar", "", [p.MULTI, [p.STATIC, ""]]]
            ]]]
        ),
        ("{{%sfoo}}{{/foo}}{{%sbar}}{{/bar}}" % (tagtype, tagtype),
            [p.MULTI,
                [p.TAG, const, "foo", "", [p.MULTI, [p.STATIC, ""]]],
                [p.TAG, const, "bar", "", [p.MULTI, [p.STATIC, ""]]]
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

def test_else():
    tests = [
        ("{{#foo}}{{^}}{{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", "", [p.MULTI, [p.STATIC, ""]]],
                [p.TAG, p.INV_SECTION, "foo", "", [p.MULTI, [p.STATIC, ""]]]
            ]
        ),
        ("{{#foo}}{{bar}}{{^}}{{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", "{{bar}}", [
                    p.MULTI, [p.TAG, p.ETAG, "bar"],
                ]],
                [p.TAG, p.INV_SECTION, "foo", "", [p.MULTI, [p.STATIC, ""]]]
            ]
        ),
        ("{{#foo}}{{^}}{{bar}}{{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", "", [p.MULTI, [p.STATIC, ""]]],
                [p.TAG, p.INV_SECTION, "foo", "{{bar}}", [
                    p.MULTI, [p.TAG, p.ETAG, "bar"]                    
                ]]
            ]
        ),
        ("{{#foo}}{{bar}} {{^}}{{bing}} {{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", "{{bar}} ", [
                    p.MULTI,
                    [p.TAG, p.ETAG, "bar"],
                    [p.STATIC, " "]
                ]],
                [p.TAG, p.INV_SECTION, "foo", "{{bing}} ", [
                    p.MULTI,
                    [p.TAG, p.ETAG, "bing"],
                    [p.STATIC, " "]
                ]]
            ]
        ),
        ("{{#foo}} {{bar}}{{^}} {{bing}}{{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", " {{bar}}", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bar"]
                ]],
                [p.TAG, p.INV_SECTION, "foo", " {{bing}}", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bing"]
                ]]
            ]
        ),
        ("{{#foo}} {{bar}} {{^}} {{bing}} {{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", " {{bar}} ", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bar"],
                    [p.STATIC, " "]
                ]],
                [p.TAG, p.INV_SECTION, "foo", " {{bing}} ", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bing"],
                    [p.STATIC, " "]
                ]]
            ]
        ),
        ("{{#foo}} {{#bar}}before{{^}}after{{/bar}}{{^}} {{bing}} {{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", " {{#bar}}before{{^}}after{{/bar}}",[
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.SECTION, "bar", "before", [
                        p.MULTI, [p.STATIC, "before"]
                    ]],
                    [p.TAG, p.INV_SECTION, "bar", "after", [
                        p.MULTI, [p.STATIC, "after"]
                    ]]
                ]],
                [p.TAG, p.INV_SECTION, "foo", " {{bing}} ", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bing"],
                    [p.STATIC, " "]
                ]]
            ]
        ),
        ("{{#foo}} {{bing}} {{^}} {{#bar}}before{{^}}after{{/bar}}{{/foo}}",
            [p.MULTI,
                [p.TAG, p.SECTION, "foo", " {{bing}} ", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.ETAG, "bing"],
                    [p.STATIC, " "]
                ]],
                [p.TAG, p.INV_SECTION, "foo",
                        " {{#bar}}before{{^}}after{{/bar}}", [
                    p.MULTI,
                    [p.STATIC, " "],
                    [p.TAG, p.SECTION, "bar", "before", [
                        p.MULTI, [p.STATIC, "before"]
                    ]],
                    [p.TAG, p.INV_SECTION, "bar", "after", [
                        p.MULTI, [p.STATIC, "after"]
                    ]]
                ]]
            ]
        ),
    ]
    def run_section_test(data):
        r = p.Parser(data[0])
        r.parse()
        t.eq(r.result, data[1])
    for case in tests:
        yield run_section_test, case
    
    tests = [
        "{{#foo}}{{^}}",
        "{{^foo}}{{^}}{{/foo}}",
        "{{^}}{{/foo}}"
    ]
    def run_section_error_test(data):
        t.raises(p.ParseError, p.Parser(data).parse)
    for case in tests:
        yield run_section_error_test, case

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
