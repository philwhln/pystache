
import os
import threading

from pystache.template import Template

class LookupError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "LookupError: %s" % self.mesg


class TemplateLookup(object):
    def __init__(self, directories, extension=None, template_opts=None):
        self.directories = os.path.abspath(d for d in directories)
        self.extension = extension or ".mustache"
        if not self.extension.startswith("."):
            self.extension = "." + self.extension
        self.filesystem_checks = filesystem_checks
        self.template_opts = template_opts or {}
        if "extension" not in self.template_opts:
            self.template_opts["extension"] = self.extension
        if "lookup" not in self.template_opts:
            self.template_opts["lookup"] = self
        self.cache_lock = threading.RLock()
    
    def get_template(self, name):
        name = name.strip().lstrip("/")
        for d in self.directories:
            fname = os.path.join(d, name)
            if os.path.exists(fname):
                return Template(filename=fname, **self.template_opts)
        raise LookupError("Failed to find template: %s" % name)