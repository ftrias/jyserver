#!/usr/env/bin python3

from context import jyserver
from jyserver import Server, Client
import time

class App(Client):
    def __init__(self):
        self.html = '''
<p id="time">NOW</p>
<button id="b1" onclick="server.reset()">Reset to 0</button>
<button id="b2" onclick="server.stop()">Pause on server</button>
'''
        self.start0 = time.time()
        self.running = True
        
    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    def stop(self):
        self.running = False
        self.js.dom.b2.innerHTML = "Restart"
        self.js.dom.b2.onclick = self.restart

    def restart(self):
        self.running = True
        self.js.dom.b2.innerHTML = "Pause"
        self.js.dom.b2.onclick = self.stop

    def main(self):
        for _ in range(100):
            if self.running:
                self.js.dom.time.innerHTML = "{:.1f}".format(time.time() - self.start0)
            time.sleep(1)
 
import webbrowser
httpd = Server(App, verbose=False)
print("serving at port", httpd.port)
# webbrowser.open(f'http://localhost:{httpd.port}')
httpd.start(cookies=True)