# FastAPI app entrypoint: mounts static assets, wires templates, root route.
from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.analysis import router as analysis_router
from .api.datasets import router as datasets_router
from .api.experiments import router as experiments_router
from .api.lab import router as lab_router
from .api.results import router as results_router
from .api.runs import router as runs_router

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="Pipeline Lab")

app.include_router(datasets_router)
app.include_router(experiments_router)
app.include_router(runs_router)
app.include_router(results_router)
app.include_router(lab_router)
app.include_router(analysis_router)

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")


@app.get("/")
def read_root(request: Request):
    """Render the shell page so the app is provably alive.

    Inputs: the incoming request (required by Jinja2Templates).
    Output: the rendered base.html shell as an HTML response.
    """
    return templates.TemplateResponse(request, "base.html", {})


@app.get("/datasets")
def datasets_page(request: Request):
    """Render the Datasets page: list + upload, wired to /api/datasets.

    Inputs: the incoming request.
    Output: the rendered datasets.html page.
    """
    return templates.TemplateResponse(request, "datasets.html", {"active_page": "datasets"})


@app.get("/experiment")
def experiment_page(request: Request):
    """Render the New Experiment page: build+launch a run.

    Inputs: the incoming request.
    Output: the rendered experiment.html page.
    """
    return templates.TemplateResponse(request, "experiment.html", {"active_page": "experiment"})


@app.get("/runs")
def runs_page(request: Request):
    """Render the Runs page: list launched runs, track one's status + log.

    Inputs: the incoming request.
    Output: the rendered runs.html page.
    """
    return templates.TemplateResponse(request, "runs.html", {"active_page": "runs"})


@app.get("/compose")
def compose_page(request: Request):
    """Render the Compose page: the card grid for the lab engine.

    Inputs: the incoming request.
    Output: the rendered compose.html page.
    """
    return templates.TemplateResponse(request, "compose.html", {"active_page": "compose"})


@app.get("/network")
def network_page(request: Request):
    """Render the Network page: the layered pipeline graph.

    Inputs: the incoming request.
    Output: the rendered network.html page.
    """
    return templates.TemplateResponse(request, "network.html", {"active_page": "network"})


@app.get("/trends")
def trends_page(request: Request):
    """Render the Trends page: x/y/group over the recorded columns.

    Inputs: the incoming request.
    Output: the rendered trends.html page.
    """
    return templates.TemplateResponse(request, "trends.html", {"active_page": "trends"})


@app.get("/results")
def results_page(request: Request):
    """Render the Results page: a succeeded run's real result tables.

    Inputs: the incoming request.
    Output: the rendered results.html page.
    """
    return templates.TemplateResponse(request, "results.html", {"active_page": "results"})


# --- Analysis pages ------------------------------------------------------
# These read the engine's lab.db directly, so they show every recorded
# run whether it was launched here or from the command line.


@app.get("/dashboard")
def dashboard_page(request: Request):
    """Render the Dashboard: headline numbers and the sweep list."""
    return templates.TemplateResponse(
        request, "dashboard.html", {"active_page": "dashboard"}
    )


@app.get("/findings")
def findings_page(request: Request):
    """Render the Findings page: what the results mean, explained."""
    return templates.TemplateResponse(
        request, "findings.html", {"active_page": "findings"}
    )


@app.get("/explorer")
def explorer_page(request: Request):
    """Render the Explorer: plot any recorded column against another."""
    return templates.TemplateResponse(
        request, "explorer.html", {"active_page": "explorer"}
    )


@app.get("/guide")
def guide_page(request: Request):
    """Render the User Guide: what this app is and how to use it."""
    return templates.TemplateResponse(
        request, "guide.html", {"active_page": "guide"}
    )
