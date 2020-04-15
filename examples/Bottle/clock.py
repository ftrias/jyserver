from bottle import route, run

import jyserver.Bottle as js
import time

@js.use
class App():
    def reset(self):
        self.start0 = time.time()

    @js.task
    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

@route('/')
def index():
    html = """
<p id="time">WHEN</p>
<button id="b1" onclick="server.reset()">Reset</button>
"""
    App.main()
    return App.render(html)

run(host='localhost', port=8080)
