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
