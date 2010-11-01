
import os
import threading

from pystache.template import Template

class LookupError(Exception):
    def __init__(self, mesg):
        self.mesg = mesg
    
    def __str__(self):
        return "LookupError: %s" % self.mesg


class TemplateInfo(object):
    def __init__(self, fname, template_opts):
        self.fname = fname
        self.mtime = os.stat(fname).st_mtime
        self.template_opts = template_opts
        self.template = Template(filename=self.fname, **self.template_opts)
        self.lock = threading.Lock()

    def recheck_fs(self):
        mtime = os.stat(self.fname).st_mtime
        with self.lock:
            if mtime == self.mtime:
                return
            self.mtime = mtime
            self.template = Template(filename=self.fname, **self.template_opts)


class TemplateLookup(object):
    def __init__(self, directories, extension=None,
                            filesystem_checks=False, template_opts=None):
        
        self.templates = {}
        if isinstance(directories, basestring):
            directories = [directories]
        self.directories = [os.path.abspath(d) for d in directories]
        self.extension = extension or ".mustache"
        if not self.extension.startswith("."):
            self.extension = "." + self.extension
        self.filesystem_checks = filesystem_checks
        self.template_opts = template_opts or {}
        if "extension" not in self.template_opts:
            self.template_opts["extension"] = self.extension
        if "lookup" not in self.template_opts:
            self.template_opts["lookup"] = self
        self.lock = threading.Lock()
    
    def get_template(self, name):
        tmplinfo = self.templates.get(name, None)
        if not tmplinfo:
            tmplinfo = self.load_template(name)
        if self.filesystem_checks:
            tmplinfo.recheck_fs()
        return tmplinfo.template

    def load_template(self, name):
        with self.lock:
            try:
                return self.templates[name]
            except KeyError:
                pass
            ret = TemplateInfo(self.find_template(name), self.template_opts)
            self.templates[name] = ret
            return ret
    
    def find_template(self, name):
        name = name.strip().lstrip("/")
        for d in self.directories:
            fname = os.path.join(d, name)
            for fn in [fname, fname + self.extension]:
                if os.path.exists(fn):
                    return fn
        raise LookupError("Failed to find template: %s" % name)

