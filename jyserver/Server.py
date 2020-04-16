'''
Module for using jyserver standalone. This module uses the built-in
http.server module. It serves as a framework for integration into
other servers.

Example
-------------
```python
from jserver import Client, Server
class App(Client):
    def __init__(self):
        self.html = """
            <p id="time">TIME</p>
            <button id="reset" 
                onclick="server.reset()">Reset</button>
        """

    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
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

from jyserver import ClientContext

import json
import threading
import queue
import os
import copy
import re
import time
import uuid


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
    js
        JS object for constructing and executing Javascript.

    Methods
    -----------

    h(file, html)
        Return appropriate HTML for the active page. Can only
        be called once per page. Must be called if implementing
        custom pages.
    
    Optional Methods
    ------------
    * main(self)

        If this is implemented, then the server will begin execution of this
        function immediately. The server will terminate when this function
        terminates.

    * index(self)

        If `index` is defined, it will execute this function. The function
        is responsible for returning the HTML with the h() method.

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

            def func(self, 15, 65)
    '''
    def __init__(self):
        self.js = None
        self._state = None

    def h(self, html=None, file=None):
        '''
        Convert text to html and wrap with script code. Return the HTML as a
        byte string. Must be called if implementing a custom page
        such as `index`.
        '''
        return self._state.htmlsend(html, file)

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
        # Instantiate objects of this class; must inherit from Client
        self.appClass = appClass
        self.contextMap = {}
        # The port number
        self.port = port
        if ip is None:
            ip = '127.0.0.1'
        # Create the server object. Must call start() to begin listening.
        super(Server, self).__init__((ip, port), Handler)

    # def getContext(self):
    #     return self._getContextForPage('SINGLE')

    def js(self):
        '''
        If you are implementing a single application without a "main"
        function, you can call this to retrieve the JS object and set
        up for single instance execution.
        '''
        return self._getContextForPage('SINGLE', True).getJS()

    def _getContextForPage(self, uid, create = False):
        c = ClientContext._getContextForPage(uid, self.appClass, create=create, verbose=self.verbose)
        return c
        
    def stop(self):
        # self._BaseServer__shutdown_request = True
        self._runmode = False
        # self.shutdown()

    def _runServer(self):
        '''
        Begin running the server until terminated.
        '''
        self._runmode = True
        while self._runmode:
            self.handle_request()
        # self.serve_forever()
        self.log_message("SERVER TERMINATED")

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
            self._runServer()
        else:
            server_thread = threading.Thread(target=self._runServer, daemon=True)
            server_thread.start()

    def log_message(self, format, *args):
        if self.verbose:
            print(format % args)
    def log_error(self, format, *args):
        print(format % args)

class Handler(SimpleHTTPRequestHandler):
    '''
    Handler is created for each request by the Server. This class
    handles the page requests and delegates tasks.
    '''

    def getContext(self):
        return self.server._getContextForPage(self.uid)

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

        if isinstance(data, str):
            data = data.encode("utf8")

        try:
            self.wfile.write(data)
            self.log_message("REPLY DONE")
        except Exception as ex:
            traceback.print_exc()
            self.server.log_error("Error sending: %s", str(ex))

    def replyFile(self, path, num=200):
        '''
        Reply to client with given file.
        '''
        with open(path, "rb") as f:
            block = f.read()
            result = HtmlPage(block).html(self.uid)
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

    def do_GET(self):
        '''
        Called by parent to process GET requests. Forwards requests to do_PAGE.
        '''
        if not self.server._runmode: return
        self.processCookies()
        qry = urlparse(self.path)
        req = dict(parse_qsl(qry.query))
        self.server.log_message("GET %s %s", qry, req)
        if "session" in req:
            pageid = req["session"]
            self.uid = HtmlPage.pageMap[pageid]
        else:
            self.uid = None
            # self.setNewUID()

        if qry.path == "/":
            # result = self.server._getHome(self.uid)
            c = self.getContext()
            result = c.showHome()
            if callable(result):
                self.log_message("HOME CALL %s", result)
                c.showPage(self, result, qry)
            else:
                self.log_message("HOME SEND %s", result)
                self.reply(result)
        elif qry.path == "/appscript.js":
            self.reply(JSCRIPT)
        else:
            self.do_PAGE(qry)

    def do_POST(self):
        '''
        Called by parent to process POST requests. Handles the built-in
        /state and /run requests and forwards all others to do_PAGE.
        '''
        if not self.server._runmode: return
        self.processCookies()
        l = int(self.headers["Content-length"])
        data = self.rfile.read(l)
        self.log_message("HTTP POST %s", data)
        if self.path == "/_process_srv0":
            self.log_message("PROCESS %s", data)
            req = json.loads(data)  
            c = self.getContext()
            results = c.processCommand(req)
            self.reply(results)
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
            c = self.getContext()
            c.showPage(self, qry.path, qry)

    def log_message(self, format, *args):
        if self.server.verbose:
            print(format % args)

