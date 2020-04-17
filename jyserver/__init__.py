'''
Jyserver is a framework for simplifying the creation of font ends for apps and
kiosks by providing real-time access to the browser's DOM and Javascript from
the server using Python syntax. It also provides access to the Python code from
the browser's Javascript. It can be used stand-alone or with other
frameworks such as Flask, Django, etc. See examples folder.

Source: https://github.com/ftrias/jyserver

Example using Bottle
-------------------------------
```
from bottle import route, run
import jyserver.Bottle as js
import time

@js.use
class App():
    def reset(self):
        self.start0 = time.time()

    @js.task
    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

@route('/')
def index():
    html = """
        <p id="time">WHEN</p>
        <button id="b1" onclick="server.reset()">Reset</button>
    """
    App.main()
    return App.render(html)

run(host='localhost', port=8080)
```
'''

from inspect import signature
import ctypes
import traceback

import json
import threading
import queue
import os
import copy
import re
import time
import uuid

from . import jscript

class ClientContext:
    contextMap = {}
    taskTimeout = 5

    def __init__(self, cls, uid=None, verbose=False):
        self.appClass = cls
        self.obj = cls()
        self.queries = {}
        self.lock = threading.Lock()
        self.fxn = {}
        self.verbose = verbose
        self.tasks = queue.Queue()
        self.uid = uid
        self._error = None
        self._signal = None
        self.obj.js = JSroot(self)
        self.singleThread = False

    def render(self, html):
        '''
        Add Javascript to the given html that will enable use of this
        module. If using Django, this gets reassigned to `render_django()`.
        '''
        page = HtmlPage(html=html)
        html = page.html(self.uid)
        return html

    def render_django(self, inp):
        '''
        Version of `render()` for use with Django.
        '''
        # for Django support
        page = HtmlPage(html=inp.content)
        inp.content = page.html(self.uid)
        return inp

    def htmlsend(self, html=None, file=None):
        page = HtmlPage(html=html, file=file)
        html = page.html(self.uid)
        self._handler.reply(html)
        self.log_message("SET SIGNAL %s", id(self._signal))
        self._signal.set()
        return page

    def hasMethod(self, name):
        return hasattr(self.obj, name)

    def callMethod(self, name, args=None):
        if hasattr(self.obj, name):
            f = getattr(self.obj, name)
            if args is None:
                f()
            else:
                f(*args)
        else:
            raise ValueError("Method not found: " + name)

    def __getattr__(self, attr):
        '''
        Unhandled calls to the context get routed to the app
        object.
        '''
        return self.obj.__getattribute__(attr)

    def getJS(self):
        '''
        Return the JS object tied to this context. Use the return value to
        create JS statements.
        '''
        return self.obj.js

    @classmethod
    def _getContextForPage(self, uid, appClass, create = False, verbose = False):
        '''
        Retrieve the Client instance for a given session id. If `create` is
        True, then if the app is not found a new one will be created. Otherwise
        if the app is not found, return None.
        '''
        if uid and not isinstance(uid, str):
            # if uid is a cookie, get it's value
            uid = uid.value

        # if we're not using cookies, direct links have uid of None
        if uid is None:
            # get first key
            if len(self.contextMap) > 0:
                uid = list(self.contextMap.items())[0][0]
            else:
                uid = None

        # existing app? return it
        if uid in self.contextMap:
            return self.contextMap[uid]
        else:
            # this is a new session or invalid session
            # assign it a new id
            # Instantiate Client, call initialize and save it.
            context = ClientContext(appClass, uid, verbose=verbose)
            self.contextMap[uid] = context
            context.log_message("NEW CONTEXT %s ID=%s", uid, id(self))
            # If there is a "main" function, then start a new thread to run it.
            # _mainRun will run main and terminate the server after main returns.
            context.mainRun()
            return context

        raise ValueError("Invalid or empty seession id: %s" % uid)

    def processCommand(self, req):
        '''
        Process the /_process_srv0 requests. All client requests are directed to this
        URL and the framework is responsible for calling this function to process
        them.
        '''
        pageid = req["session"]
        if pageid in HtmlPage.pageMap:
            self.uid = HtmlPage.pageMap[pageid]
        else:
            self.log_message("Invalid page id session %s", pageid)
            return 'Invalid pageid session: ' + pageid
            # raise RuntimeError("Invalid pageid session: " + pageid)

        HtmlPage.pageActive[pageid] = time.time()

        task = req["task"]
        self.log_message("RECEIVE TASK %s %s %s", task, self.uid, pageid)
        if task == "state":
            # The browser is replying to a request for data. First, find
            # the corresponding Queue for our request.
            q = self.getQuery(req['query'])
            # Add the results to the Queue, the code making the request is
            # currently waiting with a get(). This will cause that code
            # to wake up and process the results.
            q.put(req)
            # confirm to the server that we have processed this.
            return str(req)
        elif task == "run":
            # here, the browser is requesting we execute a statement and
            # return the results.
            result = self.run(req['function'], req['args'])
            return result
        elif task == "get":
            # here, the browser is requesting we execute a statement and
            # return the results.
            result = self.get(req['expression'])
            return result
        elif task == "set":
            # here, the browser is requesting we execute a statement and
            # return the results.
            result = self.set(req['property'], req['value'])
            return ''
        elif task == "async":
            # here, the browser is requesting we execute a statement and
            # return the results.
            result = self.run(req['function'], req['args'], block=False)
            return result
        elif task == "next":
            # the Browser is requesting we evaluate an expression and
            # return the results.
            script = self.getNextTask()
            self.log_message("NEXT TASK REQUESTED IS JS %s", script)
            return script
        elif task == "error":
            # return ''
            self._error = RuntimeError(req['error'] + ": " + req["expr"])
            return ''
        elif task == "unload":
            self.addEndTask()
            HtmlPage.expire(pageid)
            # HtmlPage.raiseException(pageid, RuntimeError("unload"))
            self.log_message("UNLOAD %s", pageid)
            return ''

    def getQuery(self, query):
        '''
        Each query sent to the browser is assigned to it's own Queue to wait for 
        a response. This function returns the Queue for the given session id and query.
        '''
        return self.queries[query]

    def addQuery(self):
        '''
        Set query is assigned to it's own Queue to wait for 
        a response. This function returns the Queue for the given session id and query.
        '''
        q = queue.Queue()
        self.queries[id(q)] = q
        return id(q), q

    def delQuery(self, query):
        '''
        Delete query is assigned to it's own Queue to wait for 
        a response. This function returns the Queue for the given session id and query.
        '''
        return self.queries[query]

    def addTask(self, stmt):
        '''
        Add a task to the queue. If the queue is too long (5 in this case)
        the browser is too slow for the speed at which we are sending commands.
        In that case, wait for up to one second before sending the command.
        Perhaps the wait time and queue length should be configurable because they
        affect responsiveness.
        '''
        for _ in range(10):
            if self.tasks.qsize() < 5:
                self.tasks.put(stmt)
                self.log_message("ADD TASK %s ON %d", stmt, id(self.tasks))
                return
            time.sleep(0.1)
        self._error = TimeoutError("Timeout (deadlock?) inserting task: " + stmt)


    def run(self, function, args, block=True):
        '''
        Called by the framework to execute a method. This function will look for a method
        with the given name. If it is found, it will execute it. If it is not found it
        will return a string saying so. If there is an error during execution it will
        return a string with the error message.
        '''
        self.log_message("RUN %s %s", function, args)
        if block:
            if not self.lock.acquire(blocking = False):
                raise RuntimeError("App is active and would block")
        
        try:
            if function == "_callfxn":
                # first argument is the function name
                # subsequent args are optional
                fxn = args.pop(0)
                f = self.fxn[fxn]
            elif callable(function):
                f = function
            elif hasattr(self.obj, function):
                f = getattr(self.obj, function)
            else:
                f = None

            if f:
                try:
                    result = f(*args)
                    ret = json.dumps({"value":JSroot._v(result)})
                except Exception as ex:
                    s = "%s: %s" % (type(ex).__name__, str(ex))
                    if self.verbose: traceback.print_exc()
                    self.log_message("Exception passed to browser: %s", s)
                    ret = json.dumps({"error":s})
            else:
                result = "Unsupported: " + function + "(" + str(args) + ")"
                ret = json.dumps({"error":str(result)})
            self.log_message("RUN RESULT %s", ret)
            return ret
        finally:
            if block:
                self.lock.release()

    def get(self, expr):
        '''
        Called by the framework to execute a method. This function will look for a method
        with the given name. If it is found, it will execute it. If it is not found it
        will return a string saying so. If there is an error during execution it will
        return a string with the error message.
        '''
        self.log_message("GET EXPR %s", expr)
        if not self.lock.acquire(blocking = False):
            raise RuntimeError("App is active and would block")
        
        try:
            if hasattr(self.obj, expr):
                value = getattr(self.obj, expr)
                if callable(value):
                    value = "(function(...args) { return handleApp('%s', args) })" % expr 
                    return json.dumps({"type":"expression", "expression":value})       
                else:
                    return json.dumps({"type":"value", "value":value})
            return None
        finally:
            self.lock.release()

    def set(self, expr, value):
        '''
        Called by the framework to set a propery.
        '''
        self.log_message("SET EXPR %s = %s", expr, value)
        self.obj.__setattr__(expr, value)
        return value

    def getNextTask(self):
        '''
        Wait for new tasks and return the next one. It will wait for 1 second and if
        there are no tasks return None.
        '''
        try:
            self.log_message("TASKS WAITING %d ON %d", self.tasks.qsize(), id(self.tasks))
            return self.tasks.get(timeout=self.taskTimeout)
        except queue.Empty:
            return None

    def addEndTask(self):
        '''
        Add a None task to end the queue.
        '''
        self.log_message("TASKS END %d ON %d", self.tasks.qsize(), id(self.tasks))
        self.tasks.put(None)

    def mainRun(self):
        '''
        If there is a method called `main` in the client app, then run it in its own
        thread.
        '''
        if hasattr(self.obj, "main"):
            server_thread = threading.Thread(
                target=self.mainRunThread, daemon=True)
            server_thread.start()

    def mainRunThread(self):
        '''
        Run the main function. When the function ends, terminate the server.
        '''
        try:
            self.obj.main()
        except Exception as ex:
            self.log_message("FATAL ERROR: %s", ex)

    def showPage(self, handler, path, query):
        '''
        Called by framework to return a queried page. When the browser requests a web page
        (for example when a user clicks on a link), the path will get put in `path` and
        any paramters passed through GET or POST will get passed in `query`. This will
        look for a Client method with the same name as the page requested. If found, it will
        execute it and return the results. If not, it will return "not found", status 404.
        '''
        if callable(path):
            f = path
        else:
            fxn = path[1:].replace('/', '_').replace('.', '_')
            if hasattr(self.obj, fxn):
                f = getattr(self.obj, fxn)
            elif path == "/favicon.ico":
                handler.reply("Not found %s" % path, 404)
                return
            else:
                raise RuntimeWarning("Page not found: " + path)
                # return "Not found", 404

        self._handler = handler
        self._signal = threading.Event()
        self.log_message("START PAGE %s %d", path, id(self._signal))
        server_thread = threading.Thread(target=self.run_callable, 
                args=(f, {"page": path, "query": query}), daemon=True)
        server_thread.start()
        self.log_message("WAIT ON SIGNAL %s %d", path, id(self._signal))
        self._signal.wait() # set when HTML is sent
        self._signal = None

    def run_callable(self, f, args):
        '''
        Execute a callable (function, etc) and catch any exceptions. This
        is called when running pages asynchonously.
        '''
        params = signature(f).parameters
        try:
            if len(params) == 0:
                f()
            else:
                f(args)
        except Exception as ex:
            traceback.print_exc()
            self.log_message("Exception: %s" % str(ex))

    def showHome(self):
        '''
        Get the home page when "/" is queried and inject the appropriate javascript
        code. Returns a byte string suitable for replying back to the browser.
        '''
        if hasattr(self.obj, "html"):
            block = self.obj.html.encode("utf8")
            page = HtmlPage(block)
            self.activePage = page.pageid
            return page.html(self.uid)
        elif hasattr(self.obj, "home"):
            path = self.obj.home
        elif os.path.exists("index.html"):
            path = "index.html"
        elif hasattr(self.obj, "index"):
            return self.obj.index
        else:
            raise ValueError("Could not find index or home")

        with open(path, "rb") as f:
            block = f.read()
            page = HtmlPage(block)
            self.activePage = page.pageid
            return page.html(self.uid)

    def log_message(self, format, *args):
        if self.verbose:
            print(format % args)

    def log_error(self, format, *args):
        print(format % args)

class HtmlPage:
    # Patterns for matching HTML to figure out where to inject the javascript code
    _pscript = re.compile(
        b'\\<script.*\\s+src\\s*=\\s*"jyserver.js"')
    _plist = [re.compile(b'\\{\\{JSCRIPT\\}\\}', re.IGNORECASE),
        re.compile(b'\\<script\\>', re.IGNORECASE),
        re.compile(b'\\<\\/head\\>', re.IGNORECASE),
        re.compile(b'\\<body\\>', re.IGNORECASE),
        re.compile(b'\\<html\\>', re.IGNORECASE)]

    pageMap = {}
    pageActive = {}
    # pageThread = {}
                       
    def __init__(self, html=None, file=None):
        if file:
            with open(file, "rb") as f:
                self.result = f.read()
        elif html:
            if isinstance(html, bytes):
                self.result = html
            else:
                self.result = html.encode("utf8")
        else:
            self.result = None
        self.pageid = uuid.uuid1().hex

    def alive(self):
        '''
        See if the current page is in the active page list and has not been
        expired.
        '''
        return self.pageid in self.pageActive

    @classmethod
    def expire(cls, item=None):
        '''
        Expire objects in the page cache.
        '''
        if item:
            del cls.pageActive[item]
            del cls.pageMap[item]
            
        old = time.time() - 5
        remove = []
        for k,v in cls.pageActive.items():
            if v < old:
                remove.append(k)
        for k in remove:
            del cls.pageActive[k]
            del cls.pageMap[k]

    def html(self, uid):
        '''
        Once the page has been loaded, this will return the appropriate
        HTML for the uid given.
        '''
        return self.insertJS(uid, self.result)

    def insertJS(self, uid, html):
        '''
        Insert the Javascript library into HTML. The strategy is that it will look for patterns
        to figure out where to insert. If "<script src="jyscript.js">" is found, it will not
        make changes and will return the Javascript when the browser requests the jyscript.js
        file. Otherwise, it will insert it into a <script> section, the <head> or at the start
        of the HTML. In any case, this function will insert the global variable UID containing
        the session id.
        '''
        self.pageMap[self.pageid] = uid
        # self.pageThread[self.pageid] = threading.get_ident()
        self.pageActive[self.pageid] = time.time()

        U = "var UID='{}';var PAGEID='{}';\n".format(uid, self.pageid).encode("utf8")
        m = self._pscript.search(html)
        if m:
            sx, ex = m.span()
            return html[:sx] + b"<script>"+U+b"</script>" + html[sx:]
        for i, p in enumerate(self._plist):
            m = p.search(html)
            if m:
                sx, ex = m.span()
                if i == 0:
                    return html[:sx] + U + jscript.JSCRIPT + html[ex:]
                elif i == 1:
                    return html[:sx] + b"<script>" + U + jscript.JSCRIPT + b"</script>" + html[sx:]
                elif i == 2:
                    return html[:sx] + b"<script>" + U + jscript.JSCRIPT + b"</script>" + html[sx:]
                else:
                    return html[:sx] + b"<head><script>" + U + jscript.JSCRIPT + b"</script></head>" + html
        return b"<head><script>" + U + jscript.JSCRIPT + b"</script></head>" + html

class JSchain:
    '''
    JSchain keeps track of the dynamically generated Javascript. It
    tracks names, data item accesses and function calls. JSchain
    is usually not used directly, but accessed through the JS class.

    Attributes
    -----------
    state
        A JSstate instance. This instance should be the same
        for all call of the same session.
        
    Notes
    -----------
    There is a special name called `dom` which is shorthand for
    lookups. For example,

        js.dom.button1.innerHTML

    Becomes

        js.document.getElementById("button1").innerHTML

    Example
    --------------
    ```
    state = JSstate(server)
    js = JSchain(state)
    js.document.getElementById("txt").value
    ```
    '''

    def __init__(self, state):
        self.state = state
        self.chain = []
        self.keep = True

    def _dup(self):
        '''
        Duplicate this chain for processing.
        '''
        js = JSchain(self.state)
        js.chain = self.chain.copy()  # [x[:] for x in self.chain]
        return js

    def _add(self, attr, dot=True):
        '''
        Add item to the chain. If `dot` is True, then a dot is added. If
        not, this is probably a function call and not dot should be added.
        '''
        if not attr:
            # this happens when __setattr__ is called when the first
            # item of a JSchain is an assignment
            return self
        if dot and len(self.chain) > 0:
            self.chain.append(".")
        self.chain.append(attr)
        return self

    def _prepend(self, attr):
        '''
        Add item to the start of the chain. 
        '''
        self.chain.insert(0, attr)
        return self

    def _last(self):
        '''
        Last item on the chain.
        '''
        return self.chain[-1]

    def __getattr__(self, attr):
        '''
        Called to process items in a dot chain in Python syntax. For example,
        in a.b.c, this will get called for "b" and "c".
        '''
        # __iter__ calls should be ignored
        if attr == "__iter__":
            return self
        return self.getdata(attr)

    def getdata(self, attr, adot=True):
        if self._last() == 'dom':
            # substitute the `dom` shortcut
            self.chain[-1] = 'document'
            self._add('getElementById')
            self._add('("{}")'.format(attr), dot=False)
        else:
            # add the item to the chain
            self._add(attr, dot=adot)
        return self

    def __setattr__(self, attr, value):
        value = JSroot._v(value)
        if attr == "chain" or attr == "state" or attr == "keep":
            # ignore our own attributes. If an attribute is added to "self" it
            # should be added here. I suppose this could be evaluated dynamically
            # using the __dict__ member.
            super(JSchain, self).__setattr__(attr, value)
            return value
        # print("SET", attr, value)
        self.setdata(attr, value)
        self.execExpression()

    def setdata(self, attr, value, adot=True):
        '''
        Called during assigment, as in `self.js.x = 10` or during a call
        assignement as in `self.js.onclick = func`, where func is a function.
        '''
        if callable(value):
            # is this a function call?
            idx = id(value)
            self.state.fxn[idx] = value
            self._add(attr, dot=adot)
            self._add("=function(){{server._callfxn(%s);}}" % idx, dot=False)
        else:
            # otherwise, regular assignment
            self._add(attr, dot=adot)
            self._add("=" + json.dumps(value), dot=False)
        return value

    def __setitem__(self, key, value):
        jkey = "['%s']" % str(key)
        self.setdata(jkey, value, adot=False)
        self.execExpression()
        return value

    def __getitem__(self, key):
        # all keys are strings in json, so format it
        key = str(key)
        c = self._dup()
        c._prepend("'%s' in " % key)
        haskey = c.eval()
        if not haskey:
            raise KeyError(key)
        jkey = "['%s']" % key
        c = self.getdata(jkey, adot=False)
        return c.eval()

    def __call__(self, *args, **kwargs):
        '''
        Called when we are using in a functiion context, as in
        `self.js.func(15)`.
        '''
        # evaluate the arguments
        p1 = [json.dumps(JSroot._v(v)) for v in args]
        p2 = [json.dumps(JSroot._v(v)) for k, v in kwargs.items()]
        s = ','.join(p1 + p2)
        # create the function call
        self._add('('+s+')', dot=False)
        return self

    def _statement(self):
        '''
        Join all the elements and return a string representation of the
        Javascript expression.
        '''
        return ''.join(self.chain)

    def __bytes__(self):
        '''
        Join the elements and return as bytes encode in utf8 suitable for
        sending back to the browser.
        '''
        return (''.join(self.chain)).encode("utf8")

    def evalAsync(self):
        if self.keep:
            stmt = self._statement()
            self.state.addTask(stmt)
            # mark it as evaluated
            self.keep = False

    def __del__(self):
        '''
        Execute the statment when the object is deleted.

        An object is deleted when it goes out of scope. That's when it is put
        together and sent to the browser for execution. 

        For statements,
        this happens when the statement ends. For example,

           self.js.func(1)

        goes out of scope when the statement after func(1). However,

           v = self.js.myvalue

        goes out of scope when the "v" goes out of scope, usually at then end of
        the function where it was used. In this case, the Javascript will be
        evaluated when "v" itself is evaluated. This happens when you perform
        an operation such as "v+5", saving or printing.

        "v" in the example above is assigned an object and not a value. This
        means that every time it is evaluated in an expression, it goes back 
        to the server and retrieves the current value.

        On the other hand,

           self.v = self.js.myvalue

        will probably never go out of scope because it is tied to the class.
        To force an evaluation, call the "eval()"
        method, as in "self.js.myvalue.eval()".
        '''
        if not self.keep: return
        # print("!!!DEL!!!")
        try:
            self.execExpression()
        except Exception as ex:
            self.state._error = ex
            self.state.log_error("Uncatchable exception: %s", str(ex))
            raise ex

    def execExpression(self):
        # Is this a temporary expression that cannot evaluated?
        if self.keep:
            stmt = self._statement()
            # print("EXEC", stmt)
            if self.state.singleThread:
                # print("ASYNC0", stmt)
                # can't run multiple queries, so just run it async
                self.state.addTask(stmt)
            else:
                # otherwise, wait for evaluation
                # print("SYNC", stmt)
                try:
                    self.eval()
                finally:
                    self.keep = False

            # mark it as evaluated
            self.keep = False

    def eval(self, timeout=10):
        '''
        Evaluate this object by converting it to Javascript, sending it to the browser
        and waiting for a response. This function is automatically called when the object
        is used in operators or goes out of scope so it rarely needs to
        be called directly.

        However, it is helpful
        to occasionally call this to avoid out-of-order results. For example,

            v = self.js.var1
            self.js.var1 = 10
            print(v)

        This will print the value 10, regardless of what var1 was before the assignment.
        That is because "v" is the abstract statemnt, not the evaluated value. 
        The assigment "var1=10" is evaluated immediately. However,
        "v" is evaluated by the Browser 
        when "v" is converted to a string in the print statement. If this is a problem,
        the code should be changed to:

            v = self.js.var1.eval()
            self.js.var1 = 10
            print(v)

        In that case, "v" is resolved immediately and hold the value of var1 before the
        assignment.

        Attributes
        -------------
        timeout
            Time to wait in seconds before giving up if no response is received.
        '''
        if not self.keep:
            return 0
            # raise ValueError("Expression cannot be evaluated")
        else:
            self.keep = False

        stmt = self._statement()
        # print("EVAL", stmt)

        c = self.state

        if not c.lock.acquire(blocking = False):
            c.log_error("App is active so you cannot wait for result of JS: %s" % stmt)
            c.addTask(stmt)
            return 0
            # raise RuntimeError("App is active so you cannot evaluate JS for: %s" % stmt)

        try:
            idx, q = c.addQuery()
            data = json.dumps(stmt)
            cmd = "sendFromBrowserToServer({}, {})".format(data, idx)
            c.addTask(cmd)
            try:
                c.log_message("WAITING ON RESULT QUEUE")
                result = q.get(timeout=timeout)
                c.log_message("RESULT QUEUE %s", result)
                c.delQuery(idx)
            except queue.Empty:
                c.log_message("TIMEOUT waiting on: %s", stmt)
                raise TimeoutError("Timout waiting on: %s" % stmt)
            if result["error"] != "":
                c.log_error("ERROR EVAL %s : %s", result["error"], stmt)
                raise RuntimeError(result["error"] + ": " + stmt)
            if "value" in result:
                return result["value"]
            else:
                return 0
        finally:
            c.lock.release()

    #
    # Magic methods. We create these methods for force the
    # Javascript to be evaluated if it is used in any
    # opreation.
    #
    def __cmp__(self, other): return self.eval().__cmp__(other)
    def __eq__(self, other): return self.eval().__eq__(other)
    def __ne__(self, other): return self.eval().__ne__(other)
    def __gt__(self, other): return self.eval().__gt__(other)
    def __lt__(self, other): return self.eval().__lt__(other)
    def __ge__(self, other): return self.eval().__ge__(other)
    def __le__(self, other): return self.eval().__le__(other)

    def __pos__(self): return self.eval().__pos__()
    def __neg__(self): return self.eval().__neg__()
    def __abs__(self): return self.eval().__abs__()
    def __invert__(self): return self.eval().__invert__()
    def __round__(self, n): return self.eval().__round__(n)
    def __floor__(self): return self.eval().__floor__()
    def __ceil__(self): return self.eval().__ceil__()
    def __trunc__(self): return self.eval().__trunc__()

    def __add__(self, other): return self.eval().__add__(other)
    def __and__(self, other): return self.eval().__and__(other)
    def __div__(self, other): return self.eval().__div__(other)
    def __divmod__(self, other): return self.eval().__divmod__(other)
    def __floordiv__(self, other): return self.eval().__floordiv__(other)
    def __lshift__(self, other): return self.eval().__lshift__(other)
    def __mod__(self, other): return self.eval().__mod__(other)
    def __mul__(self, other): return self.eval().__mul__(other)
    def __or__(self, other): return self.eval().__or__(other)
    def __pow__(self, other): return self.eval().__pow__(other)
    def __rshift__(self, other): return self.eval().__rshift__(other)
    def __sub__(self, other): return self.eval().__sub__(other)
    def __truediv__(self, other): return self.eval().__truediv__(other)
    def __xor__(self, other): return self.eval().__xor__(other)

    def __radd__(self, other): return self.eval().__radd__(other)
    def __rand__(self, other): return self.eval().__rand__(other)
    def __rdiv__(self, other): return self.eval().__rdiv__(other)
    def __rdivmod__(self, other): return self.eval().__rdivmod__(other)
    def __rfloordiv__(self, other): return self.eval().__rfloordiv__(other)
    def __rlshift__(self, other): return self.eval().__rlshift__(other)
    def __rmod__(self, other): return self.eval().__rmod__(other)
    def __rmul__(self, other): return self.eval().__rmul__(other)
    def __ror__(self, other): return self.eval().__ror__(other)
    def __rpow__(self, other): return self.eval().__rpow__(other)
    def __rrshift__(self, other): return self.eval().__rrshift__(other)
    def __rsub__(self, other): return self.eval().__rsub__(other)
    def __rtruediv__(self, other): return self.eval().__rtruediv__(other)
    def __rxor__(self, other): return self.eval().__rxor__(other)

    def __coerce__(self, other): return self.eval().__coerce__(other)
    def __complex__(self): return self.eval().__complex__()
    def __float__(self): return self.eval().__float__()
    def __hex__(self): return self.eval().__hex__()
    def __index__(self): return self.eval().__index__()
    def __int__(self): return self.eval().__int__()
    def __long__(self): return self.eval().__long__()
    def __oct__(self): return self.eval().__oct__()
    def __str__(self): return self.eval().__str__()
    def __dir__(self): return self.eval().__dir__()
    def __format__(self, formatstr): return self.eval().__format__(formatstr)
    def __hash__(self): return self.eval().__hash__()
    def __nonzero__(self): return self.eval().__nonzero__()
    def __repr__(self): return self.eval().__repr__()
    def __sizeof__(self): return self.eval().__sizeof__()
    def __unicode__(self): return self.eval().__unicode__()

    def __iter__(self): return self.eval().__iter__()
    def __reversed__(self): return self.eval().__reversed__()
    def __contains__(self, item): 
        d = self.eval()
        if isinstance(d, dict):
            # json makes all keys strings
            return d.__contains__(str(item))
        else:
            return d.__contains__(item)
    # def __missing__(self, key): return self.eval().__missing__(key)


class JSroot:
    '''
    JS handles the lifespan of JSchain objects and things like setting
    and evaluation on the root object.

    Example:
    --------------
    ```
    state = ClientContext(AppClass)
    js = JSroot(state)
    js.document.getElementById("txt").value = 25
    ```
    '''

    def __init__(self, state):
        # state is a JSstate instance unique for each session
        self.state = state
        # keep track of assignments
        self.linkset = {}
        # keep track of calls
        self.linkcall = {}

    @staticmethod
    def _v(value):
        '''
        If `value` is a JSchain, evaluate it. Otherwise, return value.
        '''
        if isinstance(value, JSchain):
            return value.eval()
        else:
            return value

    def __getattr__(self, attr):
        '''
        Called when using "." operator for the first time. Create a new chain and use it.
        Subsequent "." operators get processed by JSchain.
        '''
        # rasise any pending errors; these errors can get
        # generate on __del__() or other places that Python
        # will ignore.
        if self.state._error:
            e = self.state._error
            self.state._error = None
            raise e

        chain = JSchain(self.state)
        chain._add(attr)
        return chain

    def __setattr__(self, attr, value):
        '''
        Called when assiging attributes. This means no JSchain was created, so just process
        it directly.
        '''
        # if the value to be assigned is itself a JSchain, evaluate it
        value = JSroot._v(value)
        # don't process our own attributes
        if attr == "state" or attr == "linkset" or attr == "linkcall":
            super(JSroot, self).__setattr__(attr, value)
            return value
        # create a new JSchain
        c = self.__getattr__(attr)
        c.__setattr__(None, value)
        # c._add("=" + json.dumps(value), dot=False)
        return c

    def __getitem__(self, key):
        # this should never be called
        pass

    def __setitem__(self, key, value):
        value = JSroot._v(value)
        if key in self.linkcall:
            c = self.linkcall[key]
            if isinstance(c, JSchain):
                js = c._dup()
                if isinstance(value, list) or isinstance(value, tuple):
                    js.__call__(*value)
                else:
                    js.__call__(value)
            elif callable(c):
                c(value)
        elif key in self.linkset:
            c = self.linkset[key]
            if isinstance(c, JSchain):
                js = c._dup()
                js._add("=" + json.dumps(value), dot=False)

    def eval(self, stmt):
        '''
        Evaluate a Javascript statement `stmt` in on the Browser.
        '''
        chain = JSchain(self.state)
        chain._add(stmt)
        return chain.eval()

    def val(self, key, callback):
        self.linkset[key] = callback
        callback.keep = False

    def call(self, key, callback):
        self.linkcall[key] = callback
        if isinstance(callback, JSchain):
            callback.keep = False

    def __enter__(self):
        '''
        For use in "with" statements, as in:
            with server.js() as js:
                js.runme()
        '''
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
