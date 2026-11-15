# Seamline

> The public deployment snapshot includes the frontend, Flask backend, cached data and saved evidence. It imports an existing prototype.

A research application for comparing MODIS and VIIRS active-fire observations over Pakistan using NASA FIRMS data.

Explore detections on a map, compare regions and periods, inspect saved scientific evidence, and export the selected results. Detections are satellite fire pixels, not counts of individual fires or burned area.

## Source layout

| Path | Responsibility |
|---|---|
| `c08/app.py` | Flask routes and downloads. |
| `c08/analysis.py` | Shared calculations for the interface and exports. |
| `c08/continuity.py` | Read-only adapter for cached current observations. |
| `c08/points.py`, `c08/studio.py` | Detection-map data and comparison requests. |
| `c08/web/` | Browser interface, maps, charts and local assets. |
| `data/` | Detection table, current observations, boundaries and coverage example. |
| `experiments/` | Frozen protocols, calibration decisions and evaluation results. |
| `reports/c08/` | Methods report, presentation and saved evidence. |
| `research/metadata/` | Provider missing-date records. |
| `wsgi.py`, `Dockerfile` | Server startup, readiness and Linux container configuration. |
| `requirements*.txt` | Pinned application and deployment dependencies. |

## Run locally

Use Python 3.13 and a project-local virtual environment:

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m c08.app
```

Open http://127.0.0.1:8766 after startup. Cached data is included; ordinary app startup requires no NASA API credentials. This Flask development command is for local use.

## Deploy on Vercel

Import this repository into a Vercel project. Use the repository root, the Flask framework preset and `main` as the production branch. Leave the install and build settings at the repository defaults and keep Fluid Compute enabled. The configuration selects Python 3.13 and runs `wsgi.py`. It includes the browser assets from `c08/web/` in the function so Flask can serve `/static/` on the hosted app. It opts into Vercel's Large Functions beta for the scientific Python bundle. The cached demo needs no API keys.

After the first deployment, open `/healthz` on the generated URL and confirm it reports `ready`. Then load the map, change the selected region and date, and try a detections download. A local Flask check does not verify Vercel's hosted build or runtime.

## Container deployment

```sh
docker build -t seamline .
docker run --rm -p 8080:8080 seamline
```

The container runs Gunicorn as a non-root user, binds to `PORT` (default `8080`), and exposes `/healthz` after the dataset and default analysis load. Begin with one worker and measure memory and cold-start time on the selected host. Data are file-backed Parquet/CSV inputs; no SQL service is required. A static-only website host cannot serve the Python APIs.

Local application routes, WSGI readiness and 288 monthly API/CSV rows were verified during packaging. **The Linux image build and hosted deployment are not yet verified.** Deployment configuration alone does not establish a live service.

## Scientific constraints

- Preserve the frozen historical dataset, configurations and saved experiments. Do not refit or rerun held-out experiments during deployment.
- Retain stream, type, partial-period and support flags. Missing observations are not zero burning.
- The saved NOAA-20 bridge has restricted Punjab support. Daily conversion remains experimental.
- Saved outlook evaluation failed its release gate: the application reports **Forecast unavailable**.
- Orbits are illustrative, not live tracking. This public package uses schematic spacecraft.

## Contributing

Start from current `main`. Use separate branches such as `akbar/frontend`, `mughees/backend` and `hasnain/deployment`; review and merge actual changes. Do not overwrite newer teammate work with unchanged snapshot ZIPs. Use commit subjects describing behavior, such as `fix: preserve keyboard focus after loading` or `docs: explain deployment configuration`.

## Provenance and licensing

This repository imports an existing prototype whose development and scientific evidence predate the public snapshot. See the [source provenance recorded in Git history](https://github.com/HasnainMemon04/_seamline_/blob/d1c4bc2bcd3a594b497e799607f2c12fa0f70db8/PROVENANCE.json), [AI_USAGE.json](AI_USAGE.json) and [RESOURCES.json](RESOURCES.json) for source history, AI assistance and resources.

Original source is licensed under [Apache 2.0](LICENSE). Data, fonts and vendor assets retain their own terms; see [NOTICE](NOTICE) and accompanying licenses. [NASA FIRMS](https://www.earthdata.nasa.gov/data/tools/firms) is the principal active-fire data source.
