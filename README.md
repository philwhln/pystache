Pystache
========

A Python port of the [Mustache][mustache] templating language. The code is
largely based on a refactored port of the semi-current Ruby implementation.

Mustache was originally inspired by [ctemplate][ctemplate] and [et][et]. A
short summary of Mustache is that its a framework-agnostic way to render
logic-free views.

As ctemplates says, "It emphasizes separating logic from presentation:
it is impossible to embed application logic in this template language."

Pystache is written on Python 2.6 but should theoretically work on Python 2.5.
Please open a new [issue][issue] if you find an error.

Documentation
=============

The different Mustache tags are documented at [mustache(5)][mustache_5].

Install It
==========

    pip install pystache

Use It
======

    >>> import pystache
    >>> pystache.render('Hi {{person}}!', {'person': 'Mom'})
    u'Hi Mom!'

Contexts can be any object. A common pattern is to define a class that
will encompass the various logic required by your view. An example:

    import pystache
    
    class MyContext(object):
        def __init__(self, user):
            self.user = user
        
        def name(self):
            return u"%s, %s" % (self.user["last_name"], self.user["first_name"])

    template = """\
    Hi {{name}}!
    """

    user = {"first_name": "Paul", "last_name": "Davis"}

    pystache.render(template, MyContext(user))
    
Templates can also be parsed and reused with multiple contexts.

    import pystache
    
    template = """\
    Hi {{name}}!
    """
    
    greeting = pystache.Template(template)
    
    users = [
        {"first_name": "Paul", "last_name": "Davis"},
        {"first_name": "Jan", "last_name": "Lehnardt"}
    ]
    
    for user in users:
        print greeting.render(user)


Test It
=======

The `run-specs` script will download and run the latest mustach specs.

    ./run-specs

Authors
=======

* Chris Wanstrath <chris@ozmm.org>
* Paul J. Davis <paul.joseph.davis@gmail.com>



[ctemplate]: http://code.google.com/p/google-ctemplate/
[et]: http://www.ivan.fomichev.name/2008/05/erlang-template-engine-prototype.html
[mustache]: http://defunkt.github.com/mustache/
[mustache_5]: http://defunkt.github.com/mustache/mustache.5.html
