
NOT_FOUND = object()


class ContextMiss(object):
    def __init__(self, name):
        self.name = name
    
    def __str__(self):
        return "ContextMiss: Can't find value for: %s" % self.name

class Context(object):
    def __init__(self, view):
        self.stack = [view]

    def push(self, ctx):
        self.stack.append(ctx)
    
    def pop(self):
        self.stack.pop()

    def partial(self, name):
        return self._curr_view().partial(name)
    
    def get(self, name):
        ret = NOT_FOUND
        for c in self.stack[::-1]:
            try:
                ret = c[name]
                break
            except TypeError:
                pass

            ret = getattr(c, name, NOT_FOUND)
            if ret is NOT_FOUND:
                continue

            if callable(ret):
                ret = ret()
            break

        if ret is NOT_FOUND and self._curr_view().RAISE_ON_MISS:
            raise ContextMiss(name)
        elif ret is NOT_FOUND:
            return ""
        else:
            return ret
    
    def _curr_view(self):
        from pystache.view import View
        for ctx in self.stack[::-1]:
            if isinstance(ctx, View):
                return ctx
