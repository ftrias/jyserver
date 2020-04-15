#!/usr/env/bin python3

from context import jyserver
from jyserver.Server import Server, Client
import time

class App(Client):
    def __init__(self):
        self.html = '''
<p id="time">NOW</p>
'''
 
httpd = Server(App, verbose=False)
print("serving at port", httpd.port)
# import webbrowser
# webbrowser.open(f'http://localhost:{httpd.port}')
httpd.start(wait=False)

start0 = time.time()
js = httpd.js()
for _ in range(100):
    js.dom.time.innerHTML = "{:.1f}".format(time.time() - start0)
    time.sleep(1)