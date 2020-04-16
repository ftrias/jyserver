# Jyserver Web Framework with Pythonic Javascript Syntax

Jyserver is a framework for simplifying the creation of font ends for apps and
kiosks by providing real-time access to the browser's DOM and Javascript from
the server using Python syntax. It also provides access to the Python code from
the browser's Javascript. It can be used stand-alone or with other
frameworks such as Flask, Django, etc.

jyserver uses Python's dynamic syntax evaluation so that you can write
Python code that will dynamically be converted to JS and executed on the
browser. On the browser end, it uses JS's dynamic Proxy object to rewrite JS
code for execution by the server. All of this is done transparently without any
additional libraries or code. See examples below.

Documentation: [Class documentation](https://ftrias.github.io/jyserver/)

Git (and examples): [github:ftrias/jyserver](https://github.com/ftrias/jyserver)

Tutorial: [Dev.to article](https://dev.to/ftrias/simple-kiosk-framework-in-python-2ane)

Tutorial Flask/Bottle: [Dev.to Flask article](https://dev.to/ftrias/access-js-dom-from-flask-app-using-jyserver-23h9)

## Standalone Example:

```python
from jserver import Client, Server
class App(Client):
    def __init__(self):
        # For simplicity, this is the web page we are rendering. 
        # The module will add the relevant JS code to 
        # make it all work. You can also use an html file.
        self.html = """
            <p id="time">TIME</p>
            <button id="reset" 
                onclick="server.reset()">Reset</button>
        """

    # Called by onclick
    def reset(self):
        # reset counter so elapsed time is 0
        self.start0 = time.time()
        # executed on client
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    # If there is a "main" function, it gets executed. Program
    # ends when the function ends. If there is no main, then
    # server runs forever.
    def main(self):
        # start counter so elapsed time is 0
        self.start0 = time.time()
        while True:
            # get current elapsed time, rounded to 0.1 seconds
            t = "{:.1f}".format(time.time() - self.start0)
            # update the DOM on the client
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

httpd = Server(App)
print("serving at port", httpd.port)
httpd.start()
```

## Flask Example:

```html
<p id="time">TIME</p>
<button id="reset" onclick="server.reset()">Reset</button>
```

```python
import jyserver.Flask as js
import time
from flask import Flask, render_template, request

app = Flask(__name__)

@js.use(app)
class App():
    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    @js.task
    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

@app.route('/')
def index_page(name=None):
    App.main()
    return App.render(render_template('flask-simple.html')
```

## Django example

```python
from django.shortcuts import render
import jyserver.Django as js
import time

@js.use
class App():
    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    @js.task
    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

def hello_world(request):
    App.main()
    return App.render(render(request, 'hello_world.html', {}))
```

In `urls.py` add this path:

```python
from jyserver.Django import process
...
    url(r'^_process_srv0$', process, name='process'),
```

## Bottle example

A Bottle application using the built-in server can only be single threaded and thus
all features may not work as expected. Most significantly, you cannot
evaluate Javascript expressions from server callbacks. This limitation
is not present if using a multi-threaded server such as tornado.

```python
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

## Internals

How does this work? In the standalone example, the process is below. 
Flask/Bottle/Django is identical except for the httpd server.

1. The server will listen for new http requests.

2. When "/" is requested, jyserver will insert special Javascript code into the
   HTML that enables communication before sending it to the browser. This code
   creates the `server` Proxy object.

3. This injected code will cause the browser to send an asynchronous http
   request to the server asking for new commands for the browser to execute.
   Then it waits for a response in the background. Requests are sent via
   POST on /_process_srv0, which the server intercepts.

4. When the user clicks on the button `reset`, the `server` Proxy object is
   called. It will extract the method name--in this case `reset`--and then make
   an http request to the server to execute that statement.

5. The server will receive this http request, look at the App class, find a
   method with that name and execute it.

6. The executed method `reset()` first increases the variable `start0`. Then it
   begins building a Javascript command by using the special `self.js` command.
   `self.js` uses Python's dynamic language features `__getattr__`,
   `__setattr__`, etc. to build Javascript syntax on the fly.

7. When this "dynamic" statement get assigned a value (in our case `"0.0"`), it
   will get converted to Javascript and sent to the browser, which has been
   waiting for new commands in step 3. The statement will look like:
   `document.getElementById("time").innerHTML = "0.0"`

8. The browser will get the statement, evaluate it and return the results to the
   server. Then the browser will query for new commands in the background.

It seems complicated but this process usually takes less than a 0.01 seconds. If
there are multiple statements to execute, they get queued and processed
together, which cuts back on the back-and-forth chatter.

All communication is initiated by the browser. The server only listens for
special GET and POST requests.

## Overview of operation

The browser initiates all communcation. The server listens for connections and
sends respnses. Each page request is processed in its own thread so results may
finish out of order and any waiting does not stall either the browser or the
server.

| Browser   |   Server  |
|-----------|-----------|
| Request pages |  Send pages with injected Javascript |
| Query for new commands | Send any queued commands |
| As commands finish, send back results | Match results with commands |
| Send server statements for evaluation; wait for results |  Executes then and sends back results |

When the browser queries for new commands, the server returns any pending
commands that the browser needs to execute. If there are no pending commands, it
waits for 5-10 seconds for new commands to queue before closing the connection.
The browser, upon getting an empty result will initiate a new connection to
query for results. Thus, although there is always a connection open between the
browser and server, this connection is reset every 5-10 seconds to avoid a
timeout.

## Other features

### Assign callables in Python. 

Functions are treated as first-class objects and can be assigned.

```python
class App(Client):
    def stop(self):
        self.running = False
        self.js.dom.b2.onclick = self.restart
    def restart(self):
        self.running = True
        self.js.dom.b2.onclick = self.stop
```

If a `main` function is given, it is executed. When it finishes, the server is
terminated. If no `main` function is given, the server waits for requests in an
infinite loop.

### Lazy evaluation provides live data

Statements are evaluated lazily by `self.js`. This means that they are executed
only when they are resolved to an actual value, which can cause some statements
to be evaluated out of order. For example, consider:

```python
v = self.js.var1
self.js.var1 = 10
print(v)
```

This will always return `10` no matter what `var1` is initially. This is
because the assignment `v = self.js.var1` assigns a Javascript object and not
the actual value. The object is sent to the browser to be evaluated only when
it is used by an operation. Every time you use `v` in an operation, it will be
sent to the browser for evaluation. In this way, it provides a live link to the
data.

This behavior can be changed by calling `v = self.js.var1.eval()`, casting it
such as `v = int(self.js.var)` or performing some operation such as adding as in
`v = self.js.var + 10`.

## Installation

Available using pip or conda

```bash
pip install jyserver
```

Source code available on [github:ftrias/jyserver](https://github.com/ftrias/jyserver)
