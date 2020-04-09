#!/usr/env/bin python3

from jyserver import Server, Client
import time

class App(Client):
    def test1(self, n1, n2):
        return n1+n2

    def button1(self):
        # js.document.getElementById("txt").innerHTML = "BUTTON"
        self.js.dom.txt.innerHTML = "BUTTON"
        print("BUTTON1")

    def other(self, options):
        return "Other page: " + str(options)

httpd = Server(App)
print("serving at port", httpd.port)
httpd.start(wait=False)

js = httpd.js()
js.val("info", js.document.getElementById("txt").innerHTML)
for i in range(100):
    print("STEP", i)
    js.statevar = {"c":123,"d":(5,"x",3)}
    js.statevar.c = 99
    js["info"] = "test%d" % i
    m = js.statevar.eval()
    print(m)
    n = js.square(i).eval()
    print(i,n)
    time.sleep(1)