
from django.conf import settings
from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template import loader
from django.template.loaders.app_directories import Loader as ADLoader
from django.template.loaders.filesystem import Loader as FSLoader
from django.shortcuts import render_to_response as r2r

from pystache.lookup import LookupError, TemplateLookup
from pystache.template import Template


_lookup = None


def render_to_string(template_name, context=None, context_instance=None):
    tmpl = loader.get_template(template_name)
    if isinstance(tmpl, Template):
        return tmpl.render(context)
    else:
        return loader.render_to_string(tmpl, context, context_instance)


def render_to_response(*args, **kwargs):
    http_kwargs = {'mimetype': kwargs.pop('mimetype', None)}
    return HttpResponse(render_to_string(*args, **kwargs), **http_kwargs)


def get_lookup():
    global _lookup
    if _lookup is None:
        opts = getattr(settings, "PYSTACHE_TEMPLATE_OPTS", {})
        _lookup = TemplateLookup(settings.TEMPLATE_DIRS, **opts)
    return _lookup


class AppDirectoriesLoader(ADLoader):
    is_usable = True
    def load_template(self, template_name, template_dirs=None):
        lookup = get_lookup()
        try:
            return (lookup.get_template(template_name), template_name)
        except LookupError:
            raise TemplateDoesNotExist("No pystache template for: %s" %
                    template_name)


class FileSystemLoader(FSLoader):
    is_usable = True
    def load_template(self, template_name, template_dirs=None):
        lookup = get_lookup()
        try:
            return (lookup.get_template(template_name), template_name)
        except LookupError:
            raise TemplateDoesNotExist("No pystache template for: %s" %
                    template_name)



