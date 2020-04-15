#!/usr/env/bin python3

from context import jyserver
from jyserver.Server import Server, Client
import time

class App(Client):
    def __init__(self):
        self.start0 = time.time()
    def index(self):
        self.h(html = '''
        All browser tabs should be the same
        <p id="time">WHEN</p>
        ''')        
        for _ in range(100):
            self.js.dom.time.innerHTML = "{:.1f}".format(time.time() - self.start0)
            time.sleep(1)
 
httpd = Server(App)
print("serving at port", httpd.port)
# import webbrowser
# webbrowser.open(f'http://localhost:{httpd.port}')
httpd.start()