'''
Module for using jyserver in Bottle. This module provides to new
decorators.

Decorators
-----------

* @use

    Link an application object to the Bottle app

* @task

    Helper that wraps a function inside a separate thread so that
    it can execute concurrently.

Example
-------------
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
'''

from bottle import route, request

import json
import jyserver
import threading

def task(func):
    '''
    Decorator wraps the function in a separate thread for concurrent
    execution.
    '''
    def wrapper(*args):
        server_thread = threading.Thread(target=func, args=(args), daemon=True)
        server_thread.start()
    return wrapper

def use(appClass):
    '''
    Link a class to an app object.
    '''
    global context
    context = jyserver.ClientContext(appClass)

    @route('/_process_srv0', method='POST')
    def process():
        if request.method == 'POST':
            result = context.processCommand(request.json)
            if result is None:
                return ''
            return result
    return context