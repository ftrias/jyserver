'''
Module for using jyserver in Flask. This module provides to new
decorators.

Decorators
-----------

* @use

    Link an application object to the Flask app

* @task

    Helper that wraps a function inside a separate thread so that
    it can execute concurrently.

Example
-------------
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
'''

from flask import Flask, request
import json
import jyserver
import threading

def task(func):
    '''
    Decorator wraps the function in a separate thread for concurrent
    execution.
    '''
    def wrapper(*args):
        server_thread = threading.Thread(target=func, args=args, daemon=True)
        server_thread.start()
    return wrapper

def use(flaskapp):
    '''
    Link a class to an app object. Pass Flask's `app` object.
    '''
    def decorator(appClass):
        global context
        context = jyserver.ClientContext(appClass)

        @flaskapp.route('/_process_srv0', methods=['GET', 'POST'])
        def process():
            if request.method == 'POST':
                req = json.loads(request.data)
                result = context.processCommand(req)
                if result is None:
                    return ''
                return result
            else:
                return "GET reqeust not allowed"
        return context

    return decorator