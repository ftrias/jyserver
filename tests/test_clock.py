#!/usr/env/bin python3

from context import jyserver
from jyserver import Server, Client
import time

class App(Client):
    def __init__(self):
        self.start0 = time.time()
        self.running = True

    def isRunning(self):
        return self.running

    def failtask(self, v, v2):
        print(v, v2)
        print(self.js.dom.time.innerHTML)

    def reenter(self, v, v2):
        print(v, v2)
        self.js.dom.tx.innerHTML = "Tested!"

    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
        self.js.dom.b2.innerHTML = "Restart"
        self.js.dom.b2.onclick = self.restart

    def restart(self):
        self.running = True
        self.js.dom.b2.innerHTML = "Pause"
        self.js.dom.b2.onclick = self.stop

    def clickme(self):
        count = 0
        page = self.h(html="""
Please click again and again: <p id="text">COUNT</p>
Or <a href="/">go back</a>'
""")
        while page.alive():
            count += 1
            self.js.dom.text.innerHTML = count
            time.sleep(1)
        print("clickme done")

    def index(self):
        page = self.h(html="""
<script>
function executeTask() {
    app.running = !app.running;
    console.log("running =", app.running);
    console.log("isrunning =", app.isRunning());
    console.log("isrunning =", app.reenter(99, 15));
}
</script>
<p id="tx">R</p>
<p id="time">NOW</p>
<button id="b1" onclick="server.reset()">Reset to 0</button>
<button id="b2" onclick="server.stop()">Pause on server</button>
<button id="b3" onclick="executeTask()">Pause from JS</button>
<button id="b4" onclick="app.failtask(10,15)">Cause exception</button>
<button id="b4" onclick="app.failtask()">Cause exception2</button>
<a href="clickme">page2</a>
""")
        while page.alive():
            if self.running:
                self.js.dom.time.innerHTML = "{:.1f}".format(time.time() - self.start0)
            time.sleep(1)
        print("index done")
 
httpd = Server(App, verbose=True)
print("serving at port", httpd.port)
# import webbrowser
# webbrowser.open(f'http://localhost:{httpd.port}')
httpd.start(cookies=True)