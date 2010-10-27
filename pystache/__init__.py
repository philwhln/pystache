from pystache.template import Template
from pystache.lookup import TemplateLookup

def render(source, context=None):
    return Template(source).render(context)
