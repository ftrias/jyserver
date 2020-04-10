# Jyserver Web Framework with Pythonic Javascript Syntax

Jyserver is a framework for simplifying the creation of font ends
for apps and kiosks by providing real-time access to the browser's DOM and 
Javascript from the server using Python syntax. It also
provides access to the Python code from the browser's Javascript.

The difference between this framework and others (such as Django,
Flask, etc.) is that jyserver uses Python dynamic syntax evaluation
so that you can write Python code that will dynamically be converted
to JS and executed on the browser. On the browser end,
it uses JS's dynamic Proxy object to rewrite JS code for execution by
the server. All of this is done transparently without any additional
libraries or code. See example below.

This module uses threads and queues to ensure responsiveness.

```
Browser           Server
Javascript  --->  execute as python server code
JS & DOM    <---  execute statements
            <---  query and change values
```

## Example:

```python
from jserver import Client, Server
class App(Client):
    def __init__(self):
        # For simplicity, this is the web page we are rendering. 
        # The module will add the relevant JS code to 
        # make it all work. You can also use an html file.
        self.html = """
            <p id="time">TIME</p>
            <button id="reset" 
                onclick="server.reset()">Reset</button>
        """

    # Called by onclick
    def reset(self):
        # reset counter so elapsed time is 0
        self.start0 = time.time()
        # executed on client
        self.js.dom.time.innerHTML = "{:.1f}".format(0)

    # If there is a "main" function, it gets executed. Program
    # ends when the function ends. If there is no main, then
    # server runs forever.
    def main(self):
        # start counter so elapsed time is 0
        self.start0 = time.time()
        while True:
            # get current elapsed time, rounded to 0.1 seconds
            t = "{:.1f}".format(time.time() - self.start0)
            # update the DOM on the client
            self.js.dom.time.innerHTML = t
            time.sleep(0.1)

httpd = Server(App)
print("serving at port", httpd.port)
httpd.start()
```