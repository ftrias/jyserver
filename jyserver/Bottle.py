from bottle import route, request

import json
import jyserver
import threading

def task(func):
    def wrapper(*args):
        server_thread = threading.Thread(target=func, args=(args), daemon=True)
        server_thread.start()
    return wrapper

def use(appClass):
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