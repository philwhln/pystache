import glob
import os

import t

from pystache import Template

dirname = os.path.dirname(__file__)
datadir = os.path.join(dirname, "data")

def load_context(fname):
    ns = globals()
    execfile(fname, ns)
    return ns

def load_template(fname):
    base = os.path.basename(fname)
    fname = os.path.join(datadir, "templates", base)
    fname = fname[:-3] + ".mustache"
    return Template(filename=fname)
    
def load_output(fname):
    base = os.path.basename(fname)
    fname = os.path.join(datadir, "output", base)
    fname = fname[:-3] + ".txt"
    with open(fname) as handle:
        return handle.read()

def run(fname):
    ns = load_context(fname)
    tmpl = load_template(fname)
    out = load_output(fname)
    t.eq(tmpl.render(ns["ctx"]), out)

def make_tests():
    pattern = os.path.join(datadir, "contexts", "*.py")
    for fname in glob.glob(pattern):
        yield run, fname
