from pystache.template import Template
from pystache.view import View

def render(template, context=None, **kwargs):
    if context is None:
        context = {}
    else:
        context = context.copy()
    return Template(template, context).render()
