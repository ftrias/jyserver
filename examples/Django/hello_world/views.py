# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render

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
    return App.render(render(request, 'hello_world.html', {}))
