import context

import jyserver.Flask as jsf
import time

from flask import Flask, render_template, request
app = Flask(__name__)

@jsf.use(app)
class App:
    def addNumbers(self, a, b):
        return a+b

    def setTestText(self):
        self.js.dom.time.innerHTML = "ABC123"

    def throwError(self):
        raise ValueError("Throw error message")

    @jsf.task
    def runMain(self, mx):
        for i in range(mx):
            self.js.dom.time.innerHTML = i
            time.sleep(1)

@app.route('/hello/')
@app.route('/hello/<name>')
def hello(name=None):
    App.runMain(10)
    return App.render(render_template('flask1.html', name=name))

@app.route('/')
def hello_world():
    return 'Hello, World!'
                 