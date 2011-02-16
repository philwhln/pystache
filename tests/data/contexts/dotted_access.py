class Obj(object):
    bar = {"bing": "4"}

ctx = {
    "foo1.bar": "1",
    "foo2": {"bar": "2"},
    "foo3": {"bar": lambda: {"bing": "3"}},
    "foo4": Obj()
}