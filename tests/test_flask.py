import context

from flask import Flask, render_template, request
import jyserver.Flask as js

import unittest
from template_vars import TemplateApp, TemplateVarTest, test_html

app = Flask(__name__)

@js.use(app)
class App(TemplateApp):
    pass

@app.route('/')
def hello_world():
    html = test_html
    return App.render(html)

@js.task
def runApp():
    app.run(port=8080)

if __name__ == '__main__': 

    TemplateVarTest.js = App.getJS()
    runApp()
    # import webbrowser
    # webbrowser.open(f'http://localhost:{httpd.port}')
    unittest.main() 