import jyserver.FastAPI as jsf
import time
import uvicorn

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@jsf.use(app)
class App:
    def reset(self):
        self.start0 = time.time()
        self.js.dom.time.innerHTML = "{:.1f}".format(0)
    def stop(self):
        self.running = False
        self.js.dom.b2.innerHTML = "Restart"
        self.js.dom.b2.onclick = self.restart
    def restart(self):
        self.running = True
        self.js.dom.b2.innerHTML = "Pause"
        self.js.dom.b2.onclick = self.stop

    @jsf.task
    def main(self):
        self.running = True
        self.start0 = time.time()
        for i in range(1000):
            if self.running:
                t = "{:.1f}".format(time.time() - self.start0)
                self.js.dom.time.innerHTML = t
            time.sleep(.1)

@app.get('/', response_class=HTMLResponse)
async def index_page():
    App.main()
    html =  """
<p id="time">WHEN</p>
<button id="b1" onclick="server.reset()">Reset</button>
<button id="b2" onclick="server.stop()">Pause</button>
"""
    return App.render(html)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
