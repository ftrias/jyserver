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
        self.js.dict = {5:-99,9:-999}
        self.js.arr = [5,'10',15]
        self.js.counter = 0
        print("dict", self.js.dict)
        for i in range(100):
            if i in self.js.dict:
                print(i,"contains",self.js.dict[i])
            else:
                self.js.dict[i] = i*100 + 9
                print(i,"is",self.js.dict[i])

            if i in self.js.arr:
                print(i,"already in array")
            else:
                self.js.arr += [i]
                print("array is now", self.js.arr)

            if self.running:
                self.js.counter += 1
                self.js.dom.time.innerHTML = "{:.1f}".format(self.js.counter)
                if self.js.counter < 10:
                    print(self.js.counter * 10)
                else:
                    print(100 + self.js.counter)

            time.sleep(1)
 
httpd = Server(App, verbose=False)
print("serving at port", httpd.port)
import webbrowser
# webbrowser.open(f'http://localhost:{httpd.port}')
httpd.start()