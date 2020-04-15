from flask import Flask, render_template, request
app = Flask(__name__)

import jyserver.Flask as jsf
@jsf.use(app)
class App:
    def __init__(self):
        self.count = 0
    def increment(self):
        self.count += 1
        self.js.document.getElementById("count").innerHTML = self.count

@app.route('/')
def index_page(name=None):
    return App.render(render_template('flask-simple.html'))