from flask import Flask, render_template, request
app = Flask(__name__)

import jyserver.Flask as jsf
import time
@jsf.use(app)
class App:
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

    @jsf.task
    def main(self):
        self.running = True
        self.start0 = time.time()
        for i in range(1000):
            if self.running:
                t = "{:.1f}".format(time.time() - self.start0)
                self.js.dom.time.innerHTML = t
            time.sleep(.1)

@app.route('/')
def index_page(name=None):
    App.main()
    return App.render(render_template('clock.html'))