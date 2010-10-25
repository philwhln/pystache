from pystache.view import View

def render(source, context=None):
    v = View(source=source, context=context)
    return v.render()