import os
import t

from pystache.lookup import TemplateLookup

ROOT_DIR = os.path.dirname(__file__)
LOOKUP_DIR = os.path.join(ROOT_DIR, "data", "lookups")
OTHER_DIR = os.path.join(ROOT_DIR, "data", "lookups", "otherdir")

class Ctx(object):
    def foo(self):
        return "zing"

def test_basic():
    tlu = TemplateLookup(LOOKUP_DIR)
    tpl = tlu.get_template("basic")
    t.eq(tpl.render(Ctx()), "zing")
    tpl = tlu.get_template("basic.mustache")
    t.eq(tpl.render(Ctx()), "zing")

def test_other_ext():
    tlu = TemplateLookup(LOOKUP_DIR, extension="foo")
    tpl = tlu.get_template("other_ext")
    t.eq(tpl.render(Ctx()), "zing")

def test_partial():
    tlu = TemplateLookup(LOOKUP_DIR)
    tpl = tlu.get_template("partial")
    t.eq(tpl.render(Ctx()), "zing")

def test_subdir():
    tlu = TemplateLookup(LOOKUP_DIR)
    tpl = tlu.get_template("subdir/basic")
    t.eq(tpl.render(Ctx()), "zing")
    tpl = tlu.get_template("subdir/basic.mustache")
    t.eq(tpl.render(Ctx()), "zing")

def test_subdir_partial():
    tlu = TemplateLookup(LOOKUP_DIR)
    tpl = tlu.get_template("subdir_partial")
    t.eq(tpl.render(Ctx()), "zing")

def test_multi_dirs():
    tlu = TemplateLookup([LOOKUP_DIR, OTHER_DIR])
    tpl = tlu.get_template("basic2")
    t.eq(tpl.render(Ctx()), "zing")
    tpl = tlu.get_template("basic2.mustache")
    t.eq(tpl.render(Ctx()), "zing")
    tpl = tlu.get_template("otherdir/basic2")
    t.eq(tpl.render(Ctx()), "zing")