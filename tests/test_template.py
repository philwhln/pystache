import t

from pystache import Template, render

def test_empty():
    t.eq(render(""), "")

def test_basic():
    t.eq(render("foo"), "foo")

def test_basic_ctx():
    t.eq(render("{{foo}}", {"foo": "bar"}), "bar")

def test_with_class():
    class Foo(object):
        foo = "bar"
    t.eq(render("{{foo}}", Foo()), "bar")

def test_class_method():
    class Foo(object):
        def __init__(self, a):
            self.a = a
        def foo(self):
            return self.a
    t.eq(render("{{foo}}", Foo(2)), "2")

def test_dotted():
    class Obj(object):
        bar = {"bing": "4"}
        def __str__(self):
            return "obj"
    ctx = {
        "foo1.bar": "1",
        "foo2": {"bar": "2"},
        "foo3": {"bar": lambda: {"bing": "3"}},
        "foo4": Obj()
    }
    # Found
    t.eq(render("{{foo2.bar}}", ctx), "2")
    t.eq(render("{{foo3.bar.bing}}", ctx), "3")
    t.eq(render("{{foo4.bar.bing}}", ctx), "4")
    t.eq(render("{{foo4.__str__}}", ctx), "obj")

    # Not found
    t.eq(render("{{foo1.bar}}", ctx), "")
    t.eq(render("{{foo2.bing}}", ctx), "")
    t.eq(render("{{foo3.bar.bar}}", ctx), "")
    t.eq(render("{{foo4.bar.zing}}", ctx), "")

def test_backup():
    ctx = {
        "foo": {"bar": {"bing": "1"}},
        "bar": {"baz": {"bing": "2", "foo": "3"}},
        "baz": "4"
    }
    t.eq(render("{{#foo}}{{baz^}}{{/foo}}", ctx), "4")
    t.eq(render("{{#foo}}{{#bar}}{{baz^^}}{{/bar}}{{/foo}}", ctx), "4")
    t.eq(render("{{#bar}}{{#baz}}{{foo^^.bar.bing}}{{/baz}}{{/bar}}", ctx), "1")
    t.eq(
        render(
            "{{#bar}}{{#baz}}{{#bing}}{{foo^}}{{/bing}}{{/baz}}{{/bar}}",
            ctx
        ),
        "3"
    )
    t.eq(render("{{#foo}}{{#bar}}{{baz^^^}}{{/bar}}{{/foo}}", ctx), "4")
    t.eq(render("{{#foo}}{{#bar}}{{baz^^^^}}{{/bar}}{{/foo}}", ctx), "4")
    t.eq(render("{{#foo}}{{#bar}}{{baz^^^^^^^^}}{{/bar}}{{/foo}}", ctx), "4")

def test_view_section():
    t.eq(render("{{#foo}}bar{{/foo}}", {"foo": [1]}), "bar")

def test_empty_section():
    t.eq(render("{{#foo}}{{/foo}}", {"foo": []}), "")

def test_view_section_subctx():
    ctx = {"foo": [{"item": "ohai"}, {"item": "there"}]}
    t.eq(render("{{#foo}}{{item}}{{/foo}}", ctx), "ohaithere")
    t.eq(render("{{#foo}}ohai{{/foo}}", {"foo": False}), "")

def test_view_inv_section():
    t.eq(render("{{^foo}}ohai{{/foo}}"), "ohai")
    t.eq(render("{{^foo}}ohai{{/foo}}", {"foo": False}), "ohai")
    t.eq(render("{{^foo}}ohai{{/foo}}", {"foo": True}), "")
