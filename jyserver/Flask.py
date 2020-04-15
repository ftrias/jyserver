from flask import Flask, request
import json
import jyserver
import threading

def task(func):
    def wrapper(*args):
        server_thread = threading.Thread(target=func, args=args, daemon=True)
        server_thread.start()
    return wrapper

def use(flaskapp):
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