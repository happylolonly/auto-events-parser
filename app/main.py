from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import router as api_router

app = FastAPI(title="Da Nang Auto Events Parser")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/add", response_class=HTMLResponse)
async def add_event(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="add.html")


app.include_router(api_router)
