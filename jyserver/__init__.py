'''
Jyserver is a framework for simplifying the creation of font ends for apps and
kiosks by providing real-time access to the browser's DOM and Javascript from
the server using Python syntax. It also provides access to the Python code from
the browser's Javascript.

The difference between this framework and others (such as Django, Flask, etc.)
is that jyserver uses Python dynamic syntax evaluation so that you can write
Python code that will dynamically be converted to JS and executed on the
browser. On the browser end, it uses JS's dynamic Proxy object to rewrite JS
code for execution by the server. All of this is done transparently without any
additional libraries or code. See example below.

Documentation: [Class documentation](https://ftrias.github.io/jyserver/)

Tutorial: [Dev.to article](https://dev.to/ftrias/simple-kiosk-framework-in-python-2ane)

Self-contained example:
-------------------------------
```
class App(Client):
    def __init__(self):
        self.html = """
        <p id="time">TIME</p>
        <button id="reset" onclick="server.reset()">Reset</button>
        """

    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    def main(self):
        self.start0 = time.time()
        while True:
            self.js.dom.time.innerHTML = "{:.1f}".format(time.time() - self.start0)
            time.sleep(0.1)

httpd = Server(App)
print("serving at port", httpd.port)
httpd.start()
```
'''

from socketserver import ThreadingTCPServer
from http.server import SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qsl, unquote

import json
import threading
import queue
import os
import copy
import re
import time
import uuid

#
# This is the Javascript code that gets injected into the HTML
# page.
#
# evalBrowser()     Queries the server for any pending commands. If
#                   there are no pending commands, the connection
#                   is kept open by the server until a pending
#                   command is issued, or a timeout. At the end of
#                   the query, the function gets scheduled for execution
#                   again. We schedule it instead of calling so we
#                   don't overflow the stack.
#
# sendBrowser(e, q) Evaluate expression `e` and then send the results
#                   to the server. This is used by the server to
#                   resolve Javascript statements.
#
# server            Proxy class that is used by the web browser's
#                   Javascript code to evaluate statements on
#                   the server.
#
JSCRIPT = b"""
    function evalBrowser() {
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (request.readyState==4 && request.status==200){
                try {
                    // console.log(request.responseText)
                    eval(request.responseText)
                }
                catch(e) {}
                setTimeout(evalBrowser, 1);
            }
        }
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"task":"eval", "session": UID}));
    }
    function sendBrowser(expression, query) {
        var value
        var error = ""
        try {
            value = eval(expression)
        }
        catch (e) {
            value = 0
            error = e.message 
        }
        var request = new XMLHttpRequest();
        request.open("POST", "/_process_srv0");
        request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        request.send(JSON.stringify({"task":"state", "session":UID, "value":value, "query":query, "error": error}));
    }
    server  = new Proxy({}, { 
        get : function(target, property) { 
            return function(...args) {
                var request = new XMLHttpRequest();
                request.open("POST", "/_process_srv0", false);
                request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
                request.send(JSON.stringify({"task":"run", "function":property, "session":UID, "args":args}));
                if (request.status === 200) {
                    var result = JSON.parse(request.responseText)
                    return result
                }
            }            
        }
    });
    evalBrowser()
"""

class Client:
    '''
    Client class contains all methods and code that is executed on the server
    and browser. Users of this library should inherit this class and implement
    methods. There are three types of methods:

    Attributes
    ------------
    home
        Optional filename to send when "/" is requested
    html
        Optional HTML to send when "/" is requested. If neither
        `home` nor `html` are set, then it will send "index.html"
    state
    
    Optional Methods
    ------------
    * main(self)

        If this is implemented, then the server will begin execution of this
        function immediately. The server will terminate when this function
        terminates.

    * page(self)

        When the browser clicks on a link (or issues a GET) a method with the
        name of the page is executed. For example, clicking on link "http:/pg1"
        will cause a method named "pg1" to be executed.

    * func(self)

        When the browser executes a "server" command, the server runs a method
        with the same name. For example, if the browser runs the Javascript
        code:

            server.addnum(15, 65)

        then this method will be called:

            def func(self, param1, param2)
    '''
    def __init__(self):
        self.js : JSchain = None

class Server(ThreadingTCPServer):
    '''
    Server implements the web server, waits for connections and processes
    commands. Each browser request is handled in its own thread and so requests
    are asynchronous. The server starts listening when the "start()" method is
    called.

    Methods
    ------------
    start(wait, cookies)
    '''

    PORT = 8080
    allow_reuse_address = True

    def __init__(self, appClass, port=PORT, ip=None, verbose=False):
        '''
        Parameters
        -------------
        appClass
            Class that inherits Client. Note that this is the
            class name and not an instance.
        port
            Port to listen to (default is PORT)
        ip
            IP address to bind (default is all)
        '''
        self.verbose = verbose
        # apps keeps track of running applications
        self.apps = {}
        # Instantiate objects of this class; must inherit from Client
        self.appClass = appClass
        # If single is true, then only one Client instance is allowed
        self.single = False
        # The port number
        self.port = port
        # Patterns for matching HTML to figure out where to inject the javascript code
        self._pscript = re.compile(
            b'\\<script.*\\s+src\\s*=\\s*"appscript.js"')
        self._plist = [re.compile(b'\\{JSCRIPT\\}', re.IGNORECASE),
                       re.compile(b'\\<script\\>', re.IGNORECASE),
                       re.compile(b'\\<\\/head\\>', re.IGNORECASE),
                       re.compile(b'\\<body\\>', re.IGNORECASE),
                       re.compile(b'\\<html\\>', re.IGNORECASE)]
        if ip is None:
            ip = '127.0.0.1'
        # Create the server object. Must call start() to begin listening.
        super(Server, self).__init__((ip, port), Handler)

    def js(self):
        '''
        If you are implementing a single application without a "main"
        function, you can call this to retrieve the JS object and set
        up for single instance execution.
        '''
        self.single = True
        return self._getApp('SINGLE', True).js

    def _getNewUID(self):
        '''
        Create a new session id.
        '''
        return uuid.uuid1().hex

    def _getApp(self, uid, create = False):
        '''
        Retrieve the Client instance for a given session id. If `create` is
        True, then if the app is not found a new one will be created. Otherwise
        if the app is not found, return None.
        '''
        if self.single:
            uid = 'SINGLE'
        if uid and not isinstance(uid, str):
            # if uid is a cookie, get it's value
            uid = uid.value

        # existing app? return it
        if uid in self.apps:
            return self.apps[uid]
        elif create:
            # this is a new session, assign it a new id
            if uid is None:
                uid = self._getNewUID()
            self.log_message("NEW APP %s", uid)
            # Instantiate Client, call initialize and save it.
            a = self.appClass()
            a._state = JSstate()
            a.js = JS(a._state) # for access by Client class
            self.apps[uid] = a
            a.uid = uid
            # If there is a "main" function, then start a new thread to run it.
            # _mainRun will run main and terminate the server after main returns.
            if hasattr(a, "main"):
                server_thread = threading.Thread(
                    target=self._mainRun, args=(uid,))
                server_thread.daemon = True
                server_thread.start()
            return a
        raise ValueError(f"Invalid or empty seession id: {uid}")

    def _getQuery(self, uid, query):
        '''
        Each query sent to the browser is assigned to it's own Queue to wait for 
        a response. This function returns the Queue for the given session id and query.
        '''
        return self._getApp(uid)._state._queries[query]

    def _getHome(self, uid):
        '''
        Get the home page when "/" is queried and inject the appropriate javascript
        code. Returns a byte string suitable for replying back to the browser.
        '''
        app = self._getApp(uid)
        if hasattr(app, "html"):
            return self._insertJS(uid, app.html.encode("utf8"))
        elif hasattr(app, "home"):
            path = app.home
        else:
            path = "index.html"
        with open(path, "rb") as f:
            block = f.read()
            return self._insertJS(uid, block)

    def _getNextTask(self, uid):
        '''
        Wait for new tasks and return the next one. It will wait for 1 second and if
        there are no tasks return None.
        '''
        try:
            return self._getApp(uid)._state._tasks.get(timeout=1)
        except queue.Empty:
            return None

    def _run(self, uid, function, args):
        '''
        Called by the framework to execute a method. This function will look for a method
        with the given name. If it is found, it will execute it. If it is not found it
        will return a string saying so. If there is an error during execution it will
        return a string with the error message.
        '''
        self.log_message("RUN %s %s", function, args)
        app = self._getApp(uid)
        if function == "_callfxn":
            # first argument is the function name
            # subsequent args are optional
            fxn = args.pop(0)
            f = app._state._fxn[fxn]
        elif hasattr(app, function):
            f = getattr(app, function)
        else:
            f = None

        if f:
            try:
                result = f(*args)
            except Exception as ex:
                result = str(ex)
        else:
            result = "Unsupported: " + function + "(" + str(args) + ")"
        return result

    def _page(self, uid, path, query):
        '''
        Called by framework to return a queried page. When the browser requests a web page
        (for example when a user clicks on a link), the path will get put in `path` and
        any paramters passed through GET or POST will get passed in `query`. This will
        look for a Client method with the same name as the page requested. If found, it will
        execute it and return the results. If not, it will return "not found", status 404.
        '''
        fxn = path[1:].replace('/', '_')
        app = self._getApp(uid)
        if hasattr(app, fxn):
            f = getattr(app, fxn)
            return f({"page": path, "query": query})
        return "Not found", 404

    def _insertJS(self, uid, html):
        '''
        Insert the Javascript library into HTML. The strategy is that it will look for patterns
        to figure out where to insert. If "<script src="appjscript.js">" is found, it will not
        make changes and will return the Javascript when the browser requests the appjscript.js
        file. Otherwise, it will insert it into a <script> section, the <head> or at the start
        of the HTML. In any case, this function will insert the global variable UID containing
        the session id.
        '''
        U = "var UID='{}';\n".format(uid).encode("utf8")
        m = self._pscript.search(html)
        if m:
            sx, ex = m.span()
            return html[:sx] + "<script>"+U+"</script>" + html[sx:]
        for i, p in enumerate(self._plist):
            m = p.search(html)
            if m:
                sx, ex = m.span()
                if i == 0:
                    return html[:sx] + U + JSCRIPT + html[ex:]
                elif i == 1:
                    return html[:sx] + b"<script>" + U + JSCRIPT + b"</script>" + html[sx:]
                elif i == 2:
                    return html[:sx] + b"<script>" + U + JSCRIPT + b"</script>" + html[sx:]
                else:
                    return html[:sx] + b"<head><script>" + U + JSCRIPT + b"</script></head>" + html
        return b"<head><script>" + U + JSCRIPT + b"</script></head>" + html

    def _mainRun(self, uid):
        '''
        Run the main function. When the function ends, terminate the server.
        '''
        try:
            self._getApp(uid, True).main()
        except Exception as ex:
            print("FATAL ERROR", ex)
        finally:
            self.shutdown()

    def _runServer(self):
        '''
        Begin running the server until terminated.
        '''
        self.serve_forever()

    def start(self, wait=True, cookies=True):
        '''
        Start listening to the port and processing requests.

        Parameters
        ------------
        wait
            Start listening and wait for server to terminate. If this
            is false, start server on new thread and continue execution.
        cookies
            If True, try to use cookies to keep track of sessions. This
            enables the browser to open multiple windows that all share
            the same Client object. If False, then cookies are disabled
            and each tab will be it's own session.
        '''
        self.useCookies = cookies
        if wait or hasattr(self.appClass, "main"):
            self.serve_forever()
        else:
            server_thread = threading.Thread(target=self._runServer)
            server_thread.daemon = True
            server_thread.start()

    def log_message(self, format, *args):
        if self.verbose:
            print(format % args)

class Handler(SimpleHTTPRequestHandler):
    '''
    Handler is created for each request by the Server. This class
    handles the page requests and delegates tasks.
    '''

    def reply(self, data, num=200):
        '''
        Reply to the client with the given status code. If data is given as a string
        it will be encoded at utf8. Cookies are sent if they are used.
        '''
        self.send_response(num)
        if self.server.useCookies:
            self.send_header(
                "Set-Cookie", self.cookies.output(header='', sep=''))
        self.end_headers()
        if data is None:
            return
        if isinstance(data, bytes):
            self.wfile.write(data)
        else:
            self.wfile.write(data.encode("utf8"))

    def replyFile(self, path, num=200):
        '''
        Reply to client with given file.
        '''
        with open(path, "rb") as f:
            block = f.read()
            result = self.server._insertJS(self.uid, block)
            self.reply(result)

    def processCookies(self):
        '''
        Read in cookies and extract the session id.
        '''
        if self.server.useCookies:
            self.cookies = SimpleCookie(self.headers.get('Cookie'))
            if "UID" in self.cookies:
                self.uid = self.cookies["UID"]
            else:
                self.uid = None

    def setNewUID(self):
        '''
        If we have a new session id, set it in the approriate places.
        '''
        if self.server.useCookies:
            self.cookies = SimpleCookie(self.headers.get('Cookie'))

        if hasattr(self, "uid"):
            app = self.server._getApp(self.uid)
        else:
            app = None
        if app is None:
            app = self.server._getApp(uuid.uuid1().hex, True)
        self.uid = app.uid

        if self.server.useCookies:
            self.cookies["UID"] = self.uid

    def do_GET(self):
        '''
        Called by parent to process GET requests. Forwards requests to do_PAGE.
        '''
        self.processCookies()
        qry = urlparse(self.path)
        req = dict(parse_qsl(qry.query))
        if "session" in req:
            self.uid = req["session"]
        if qry.path == "/":
            self.setNewUID()
            self.reply(self.server._getHome(self.uid))
        elif qry.path == "/appscript.js":
            self.reply(JSCRIPT)
        else:
            self.do_PAGE(qry)

    def do_POST(self):
        '''
        Called by parent to process POST requests. Handles the built-in
        /state and /run requests and forwards all others to do_PAGE.
        '''
        self.processCookies()
        l = int(self.headers["Content-length"])
        data = self.rfile.read(l)
        if self.path == "/_process_srv0":
            req = json.loads(data)
            self.uid = req["session"]
            task = req["task"]
            if task == "state":
                # The browser is replying to a request for data. First, find
                # the corresponding Queue for our request.
                q = self.server._getQuery(self.uid, req['query'])
                # Add the results to the Queue, the code making the request is
                # currently waiting with a get(). This will cause that code
                # to wake up and process the results.
                q.put(req)
                # confirm to the server that we have processed this.
                self.reply(str(req))
            elif task == "run":
                # here, the browser is requesting we execute a statement and
                # return the results.
                result = self.server._run(self.uid, req['function'], req['args'])
                self.reply(json.dumps(JS._v(result)))
            elif task == "eval":
                # the Browser is requesting we evaluate an expression and
                # return the results.
                script = self.server._getNextTask(self.uid)
                self.log_message("EVAL JS %s", script)
                self.reply(script)
        else:
            self.do_PAGE(data)

    def do_PAGE(self, qry):
        '''
        Process page requests except /state and /run.
        '''
        self.log_message("PAGE %s", qry)
        if os.path.exists(qry.path[1:]):
            # try to send a file with the given name if it exists.
            self.replyFile(qry.path[1:])
        else:
            # otherwise, pass on the request to the Client object. It will
            # execute a method with the same name if it exists.
            reply = self.server._page(self.uid, qry.path, qry)
            if isinstance(reply, list) or isinstance(reply, tuple):
                self.reply(*reply)
            else:
                self.reply(reply)

    def log_message(self, format, *args):
        if self.server.verbose:
            print(format % args)

class JSstate:
    '''
    JState keeps track of the Javascript state on the browser.

    Attributes
    ------------
    _tasks
        A queue of pending tasks that must be performed on the
        browser.
    _fxn
        Map to keep track of callables that the browser's 
        Javascript is allowed to call.
    _queries
        When python requests a statement to be evaluated, a
        unique query id is assigned. Then a Queue is created
        to wait for reasults. This maps ids to Queues.
    '''

    def __init__(self):
        self._tasks = queue.Queue()
        self._fxn = {}
        self._queries = {}
        self._error = None

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

        dom.button1.innerHTML

    Becomes

        document.getElementById("button1").innerHTML

    Example
    --------------
    ```
    state = JSstate()
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
        if self._last() == 'dom':
            # substitute the `dom` shortcut
            self.chain[-1] = 'document'
            self._add('getElementById')
            self._add('("{}")'.format(attr), dot=False)
        else:
            # add the item to the chain
            self._add(attr)
        return self

    def __setattr__(self, attr, value):
        '''
        Called during assigment, as in `self.js.x = 10` or during a call
        assignement as in `self.js.onclick = func`, where func is a function.
        '''
        value = JS._v(value)
        if attr == "chain" or attr == "state" or attr == "keep":
            # ignore our own attributes. If an attribute is added to "self" it
            # should be added here. I suppose this could be evaluated dynamically
            # using the __dict__ member.
            super(JSchain, self).__setattr__(attr, value)
            return value
        if callable(value):
            # is this a function call?
            idx = id(value)
            self.state._fxn[idx] = value
            self._add(attr)
            self._add(f"=function(){{server._callfxn({idx});}}", dot=False)
        else:
            # otherwise, regular assignment
            self._add(attr)
            self._add("=" + json.dumps(value), dot=False)
        return self

    def __call__(self, *args, **kwargs):
        '''
        Called when we are using in a functiion context, as in
        `self.js.func(15)`.
        '''
        # evaluate the arguments
        p1 = [json.dumps(JS._v(v)) for v in args]
        p2 = [json.dumps(JS._v(v)) for k, v in kwargs.items()]
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

    def _addTask(self, stmt):
        '''
        Add a task to the queue. If the queue is too long (5 in this case)
        the browser is too slow for the speed at which we are sending commands.
        In that case, wait for up to one second before sending the command.
        Perhaps the wait time and queue length should be configurable because they
        affect responsiveness.
        '''
        for _ in range(10):
            if self.state._tasks.qsize() < 5:
                self.log_message("ADD TASK %s", stmt)
                self.state._tasks.put(stmt)
                return
            time.sleep(0.1)
        self.state._error = TimeoutError("Timeout inserting task: " + stmt)

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

        # Is this a temporary expression that cannot evaluated?
        if self.keep:
            stmt = self._statement()
            self._addTask(stmt)
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
            raise ValueError("Expression cannot be evaluated")
        stmt = self._statement()
        q = queue.Queue()
        idx = id(q)
        self.state._queries[idx] = q
        data = json.dumps(stmt)
        self._addTask("sendBrowser({}, {})".format(data, idx))
        try:
            result = q.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("Timout waiting on: "+stmt)
        if result["error"] != "":
            raise ValueError(result["error"])
        return result["value"]

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

    def __getitem__(self, key): return self.eval().__getitem__(key)
    def __iter__(self): return self.eval().__iter__()
    def __reversed__(self): return self.eval().__reversed__()
    def __contains__(self, item): return self.eval().__contains__(item)
    def __missing__(self, key): return self.eval().__missing__(key)


class JS:
    '''
    JS handles the lifespan of JSchain objects and things like setting
    and evaluation.

    Example:
    --------------
    ```
    state = JSstate()
    js = JS(state)
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
        value = JS._v(value)
        # don't process our own attributes
        if attr == "state" or attr == "linkset" or attr == "linkcall":
            super(JS, self).__setattr__(attr, value)
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
        value = JS._v(value)
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
