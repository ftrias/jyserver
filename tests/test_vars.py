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
function fsetTestApp(){return server.setTestText()}
function add2(a,b){return a+b}
</script>
<p id="time">NOW</p>
'''
    def addNumbers(self, a, b):
        return a+b

    def setTestText(self):
        self.js.dom.time.innerHTML = "ABC123"

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
        v = self.js.multNum(5,6)
        self.assertEqual(v, 30)
        self.js.fset("TEST123")
        self.assertEqual(self.js.dom.time.innerHTML, "TEST123")
        self.js.fsetTestApp()
        self.assertEqual(self.js.dom.time.innerHTML, "ABC123")
        self.js.fsetApp(12, 20)
        self.assertEqual(self.js.dom.time.innerHTML, "32")

    def test_float(self):
        self.js.valfloat = 1.5
        self.assertTrue(self.js.valfloat * 2 == 3.0)

    def test_dict(self):
        self.js.valfloat = 1.5
        self.assertTrue(self.js.valfloat * 2 == 3.0)
        self.js.dict = {5:-99,9:-999}
        self.assertTrue(5 in self.js.dict)
        self.assertEqual(self.js.dict[9], -999)

        with self.assertRaises(KeyError):
            self.js.dict[1]
        
        self.js.dict[10] = 45.175
        self.assertIn(10, self.js.dict)
        self.assertEqual(self.js.dict[10], 45.175)

    def test_array(self):
        self.js.arr = [5,'10',15]
        self.assertEqual(self.js.arr, [5, '10', 15])
        self.js.arr += [30, 32]
        self.assertEqual(self.js.arr, [5, '10', 15, 30, 32])

    def test_arith(self):
        self.js.counter = 0
        v = self.js.counter
        self.assertEqual(self.js.counter, 0)
        self.js.counter = 1
        self.assertEqual(self.js.counter, 1)
        self.js.counter += 10
        self.assertEqual(self.js.counter, 11)
        self.js.counter = 100 + self.js.counter
        self.assertEqual(self.js.counter, 111)
        self.assertEqual(v, 111)

    def test_dom(self):
        self.js.dom.time.innerHTML = "{:.1f}".format(self.js.counter)
        self.assertEqual(self.js.dom.time.innerHTML, "111.0")
        self.js.dom.time.xyz = "abc"
        self.assertEqual(self.js.dom.time.xyz, "abc")
        self.js.dom.time.innerHTML = "DONE"
        self.assertEqual(self.js.dom.time.innerHTML, "DONE")

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