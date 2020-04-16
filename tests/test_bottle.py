import context

from bottle import route, run
import jyserver.Bottle as js

import unittest
from template_vars import TemplateApp, TemplateVarTest, test_html

@js.use
class App(TemplateApp):
    pass

@route('/')
def hello_world():
    html = test_html
    return App.render(html)

@js.task
def runApp():
    # import asyncio
    # asyncio.set_event_loop(asyncio.new_event_loop())
    # run(port=8080, server='tornado')
    run(port=8080)

if __name__ == '__main__': 

    TemplateVarTest.js = App.getJS()
    runApp()
    # import webbrowser
    # webbrowser.open(f'http://localhost:{httpd.port}')
    unittest.main() 