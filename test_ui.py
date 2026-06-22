import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import webbrowser
import threading
import time

app = FastAPI()

# Serve static files (CSS, JS, Fonts)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="ui/templates")

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})

@app.get("/workflows")
async def workflows(request: Request):
    return templates.TemplateResponse(request=request, name="workflows.html", context={})

@app.get("/logs")
async def logs(request: Request):
    return templates.TemplateResponse(request=request, name="logs.html", context={})

@app.get("/settings")
async def settings(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html", context={})

@app.get("/developer")
async def developer(request: Request):
    return templates.TemplateResponse(request=request, name="developer.html", context={})

import socket

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

port = get_free_port()

def open_browser():
    time.sleep(1)
    webbrowser.open(f"http://localhost:{port}")

if __name__ == "__main__":
    print(f"Starting test UI server on http://localhost:{port}")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port)
