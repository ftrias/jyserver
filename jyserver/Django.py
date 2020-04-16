'''
Module for using jyserver in Django. This module provides to new
decorators.

Decorators
-----------

* @use

    Link an application object to the Django app

* @task

    Helper that wraps a function inside a separate thread so that
    it can execute concurrently.

Example (assumes working setup)
-------------
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
'''

from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

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

@csrf_exempt
def process(request):
    '''
    Used to process browser requests. Must be added to your `urls.py`
    to process `/_process_srv0` as in:
    ```
        url(r'^_process_srv0$', process, name='process'),
    ```
    '''
    if request.method == 'POST':
        req = json.loads(request.body)
        result = context.processCommand(req)
        if result is None:
            return HttpResponse('')
        return HttpResponse(result)
    else:
        return HttpResponse("GET reqeust not allowed")

def use(appClass):
    '''
    Link a class to an app object. Pass Flask's `app` object.
    '''
    global context
    context = jyserver.ClientContext(appClass)
    context.render = context.render_django
    return context
