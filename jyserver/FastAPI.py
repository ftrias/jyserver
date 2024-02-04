'''
Module for using jyserver in FastAPI. This module provides to new
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
import jyserver.FastAPI as js
import time

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(__name__)

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

@app.get('/', response_class=HTMLResponse)
async def index_page():
    App.main()
    html =  """
<p id="time">TIME</p>
<button id="reset" onclick="server.reset()">Reset</button>
"""
    return App.render(html)
'''

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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

def use(myapp):
    '''
    Link a class to an app object. Pass `app` object.
    '''
    def decorator(appClass):
        global context
        context = jyserver.ClientContext(appClass)

        @myapp.post('/_process_srv0')
        async def process(item: Request):
            req = await item.json()
            result = context.processCommand(req)
            if result is None: result = ''
            return Response(content=result, media_type="text/plain")
        return context

    return decorator