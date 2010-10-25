import t

from pystache import View, render

def test_empty():
    t.eq(render(""), "")

def test_basic():
    t.eq(render("foo"), "foo")

def test_basic_ctx():
    t.eq(render("{{foo}}", {"foo": "bar"}), "bar")

def test_view_subclass():
    class Foo(View):
        foo = "bar"
    t.eq(Foo(source="{{foo}}").render(), "bar")

def test_view_section():
    t.eq(render("{{#foo}}bar{{/foo}}", {"foo": [1]}), "bar")

def test_view_section_subctx():
    ctx = {"foo": [{"item": "ohai"}, {"item": "there"}]}
    t.eq(render("{{#foo}}{{item}}{{/foo}}", ctx), "ohaithere")
    t.eq(render("{{#foo}}ohai{{/foo}}", {"foo": False}), "")


def test_view_inv_section():
    t.eq(render("{{^foo}}ohai{{/foo}}"), "ohai")
    t.eq(render("{{^foo}}ohai{{/foo}}", {"foo": False}), "ohai")
    t.eq(render("{{^foo}}ohai{{/foo}}", {"foo": True}), "")