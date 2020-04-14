#!/usr/env/bin python3

import unittest
from context import jyserver
from jyserver import Server, Client
import time

class App(Client):
    def __init__(self):
        self.html = '''
<script>
function multNum(a,b){return a*b}
function fset(a){document.getElementById("time").innerHTML = a}
function fsetApp(a,b){document.getElementById("time").innerHTML = app.addNumbers(a,b)}
function faddApp(a,b){return app.addNumbers(a,b)}
function fsetTestApp(){return server.nothingHere()}
function fsetThrow(){return server.throwError()}
function fThrow(i){fnothing();}
function fsetTest(){document.getElementById("time").innerHTML = "TEST"}
function add2(a,b){return a+b}
</script>
<p id="time">NOW</p>
'''
    def addNumbers(self, a, b):
        return a/0

    def throwError(self):
        raise ValueError("Throw error message")

class MyTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        global httpd
        self.js = httpd.js()
    
    @classmethod
    def tearDownClass(self):
        global httpd
        httpd.stop()

    def test_call(self):
        # this throws in the browser's context, so we don't see it 
        # except as a console message
        self.js.fsetThrow()

    def test_call_throw(self):
        with self.assertRaises(RuntimeError):
            self.js.fThrow(0).eval()

    def test_dict(self):
        self.js.dict = {5:10}
        with self.assertRaises(KeyError):
            self.js.dict[1]

    def test_dom_excpetion(self):
        with self.assertRaises(RuntimeError):
            print(self.js.dom.time1.innerHTML)
        with self.assertRaises(RuntimeError):
            self.js.dom.time1.innerHTML = "thisfail"

if __name__ == '__main__': 

    httpd = Server(App, verbose=False)
    print("serving at port", httpd.port)
    import webbrowser
    # webbrowser.open(f'http://localhost:{httpd.port}')
    httpd.start(wait=False)
  
    unittest.main() 