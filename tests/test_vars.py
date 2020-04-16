from context import jyserver

from jyserver.Server import Server, Client

import unittest
from template_vars import TemplateApp, TemplateVarTest, test_html

class App(TemplateApp):
    def __init__(self):        
        self.html = test_html

if __name__ == '__main__': 

    httpd = Server(App, verbose=False, port=8080)
    TemplateVarTest.js = httpd.js()

    print("serving at port", httpd.port)
    # import webbrowser
    # webbrowser.open(f'http://localhost:{httpd.port}')
    httpd.start(wait=False)
  
    unittest.main() 
    httpd.stop()