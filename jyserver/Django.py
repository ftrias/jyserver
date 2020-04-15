from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

import json
import jyserver
import threading

def task(func):
    def wrapper(*args):
        server_thread = threading.Thread(target=func, args=args, daemon=True)
        server_thread.start()
    return wrapper

@csrf_exempt
def process(request):
    if request.method == 'POST':
        req = json.loads(request.body)
        result = context.processCommand(req)
        if result is None:
            return HttpResponse('')
        return HttpResponse(result)
    else:
        return HttpResponse("GET reqeust not allowed")

def use(appClass):
    global context
    context = jyserver.ClientContext(appClass)
    context.render = context.render_django
    return context
