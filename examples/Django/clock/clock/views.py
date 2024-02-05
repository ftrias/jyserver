# -*- coding: utf-8 -*-
from django.http import HttpResponse

import jyserver.Django as js
import time

@js.use
class App():
    def reset(self):
        print("RESET")
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    @js.task
    def main(self):
        self.start0 = time.time()
        while True:
            t = "{:.1f}".format(time.time() - self.start0)
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

def hello_world(request):
    App.main()
    html =  """
<p id="time">WHEN</p>
<button id="b1" onclick="server.reset()">Reset</button>
<button id="b2" onclick="server.stop()">Pause</button>
"""
    return App.render(HttpResponse(html))
