from jyserver.Server import Client, Server
class App(Client):
    def __init__(self):
        self.count = 0
    def increment(self):
        self.count += 1
        self.js.document.getElementById("count").innerHTML = self.count
httpd = Server(App)
print("serving at port", httpd.port)
httpd.start()