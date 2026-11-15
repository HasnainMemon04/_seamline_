# File catalog

Every tracked file is listed below. These descriptions explain purpose; GitHub separately shows the latest commit touching each file.

Scientific inputs, protocols and saved results are read-only baselines. Ordinary deployment does not rerun scientific experiments.

## Repository and deployment files

| File | Purpose |
|---|---|
| [.dockerignore](.dockerignore) | Excludes Git metadata, credentials and local environments from the container build. |
| [.gitattributes](.gitattributes) | Preserves exact source, scientific input and evidence bytes across operating systems. |
| [.gitignore](.gitignore) | Excludes credentials, environments, bytecode and test caches. |
| [AI_USAGE.json](AI_USAGE.json) | Records known AI assistance, uncertain historical attribution and contributor disclosures. |
| [Dockerfile](Dockerfile) | Defines the Python Linux container, non-root user, Gunicorn process and readiness probe. |
| [FILE_MAP.md](FILE_MAP.md) | Complete tracked-file catalog with individual purpose descriptions. |
| [LICENSE](LICENSE) | Apache 2.0 terms for original source code. |
| [NOTICE](NOTICE) | Project copyright, NASA acknowledgments and third-party licensing notices. |
| [PROVENANCE.json](PROVENANCE.json) | Records snapshot origin, actual prior-work history and source-file hashes. |
| [README.md](README.md) | Application overview, source layout, operation and collaboration instructions. |
| [RESOURCES.json](RESOURCES.json) | Links NASA sources, boundary provenance and scientific evidence. |
| [RUN.txt](RUN.txt) | Concise launch instructions and current verification limits. |
| [requirements.deploy.txt](requirements.deploy.txt) | Adds the pinned Gunicorn server to the application dependency lock. |
| [requirements.lock.txt](requirements.lock.txt) | Pins Python application and research-utility dependencies. |
| [wsgi.py](wsgi.py) | Loads data and default analysis, exposes Flask through WSGI and registers /healthz. |

## Application and analysis modules

| File | Purpose |
|---|---|
| [c08/__init__.py](c08/__init__.py) | Declares the Seamline Python package. |
| [c08/__main__.py](c08/__main__.py) | Seamline command line:  python -m c08 <command> |
| [c08/acquire.py](c08/acquire.py) | Resumable, hashed downloads of public FIRMS files (no key or login needed). |
| [c08/analysis.py](c08/analysis.py) | Region analysis behind the app and its exports (one function, so screen = export). |
| [c08/app.py](c08/app.py) | Serves Flask routes, analysis endpoints and downloadable exports. |
| [c08/boundaries.py](c08/boundaries.py) | Pakistan province boundaries (geoBoundaries gbOpen PAK ADM1). |
| [c08/burned_area.py](c08/burned_area.py) | Protocol P02 D3: MODIS burned area (MCD64A1 Collection 6.1) for Punjab, October-November 2003-2025. |
| [c08/config.py](c08/config.py) | Paths, sensor registry and fixed constants shared by the pipeline. |
| [c08/continuity.py](c08/continuity.py) | Read-only, hash-checked 2026+ cached observations. See CURRENT_RECORD_CONTRACT.md. |
| [c08/coverage.py](c08/coverage.py) | Observation coverage example: "Was this area actually observed?" |
| [c08/figures.py](c08/figures.py) | Sanity and result figures for Punjab (reports/c08/figures/*.png). |
| [c08/handover.py](c08/handover.py) | Satellite Handover Simulator: a historical sensor-withholding replay of the saved 2026 bridge test (P04 G03). |
| [c08/harmonize.py](c08/harmonize.py) | Candidate harmonisation models and metrics from Protocol P01 (sections 6-7). |
| [c08/ingest.py](c08/ingest.py) | Validated ingestion of the cached FIRMS files into one tidy detection table. |
| [c08/observe.py](c08/observe.py) | Protocol P02 D1 and D2: a camera model (forward observation operator) and the clock test. |
| [c08/outlook.py](c08/outlook.py) | Protocol O01 runner: an experimental, retrospective outlook for detected burning activity. |
| [c08/p01.py](c08/p01.py) | Protocol P01 experiments: E00 first-run proof, E01 selection, E02 held-out evaluation. |
| [c08/p02_posthoc.py](c08/p02_posthoc.py) | Post-hoc checks of Protocol P02, added 3 Nov 2026 after the checker's report. |
| [c08/p04.py](c08/p04.py) | Protocol P04 runner: tests G01, G02, G03 and G04, each run once (G05 is withdrawn). |
| [c08/p04_devcheck.py](c08/p04_devcheck.py) | Checks CHECK REPORT P04 asks for before any P04 test data is opened (B2, B3, B5, B6). |
| [c08/points.py](c08/points.py) | Read-only display path for the map: the observed detections of one month, and facts about each area. |
| [c08/report.py](c08/report.py) | Methods and evidence report: reports/c08/methods_report.html (+ .pdf via Edge, if installed). |
| [c08/reproduce.py](c08/reproduce.py) | Historical reproduction utilities; not a routine deployment check or instruction to rerun holdouts. |
| [c08/series.py](c08/series.py) | Monthly detected-burning-activity counts per region, platform and pass. |
| [c08/showcase.py](c08/showcase.py) | Showcase cards: the project's story, read from saved result files only (GET /api/showcase). |
| [c08/slides.py](c08/slides.py) | Seven-slide deck: reports/c08/slides.html (+ slides.pdf via Edge). python -m c08.slides |
| [c08/studio.py](c08/studio.py) | Comparison Studio: two selections side by side (two areas over one period, or one area over two periods). |

## Browser interface and assets

| File | Purpose |
|---|---|
| [c08/web/app.js](c08/web/app.js) | Coordinates application state, API requests, charts, exports and guided tours. |
| [c08/web/assets/seamline-mark.svg](c08/web/assets/seamline-mark.svg) | Application vector artwork: seamline-mark. |
| [c08/web/assets/world/PROVENANCE.json](c08/web/assets/world/PROVENANCE.json) | Source and licensing metadata for world geometry. |
| [c08/web/assets/world/land.geojson](c08/web/assets/world/land.geojson) | World land geometry for map context. |
| [c08/web/assets/world/rivers.geojson](c08/web/assets/world/rivers.geojson) | River geometry for map context. |
| [c08/web/explore.js](c08/web/explore.js) | Controls map selections, filtering, playback, inspection and canvas fallback. |
| [c08/web/features.js](c08/web/features.js) | Connects extended analysis and evidence features to the interface. |
| [c08/web/fonts/FONTS.json](c08/web/fonts/FONTS.json) | Bundled browser font: FONTS. |
| [c08/web/fonts/InstrumentSans-OFL.txt](c08/web/fonts/InstrumentSans-OFL.txt) | Font license: InstrumentSans-OFL. |
| [c08/web/fonts/InstrumentSans-var.woff2](c08/web/fonts/InstrumentSans-var.woff2) | Bundled browser font: InstrumentSans-var. |
| [c08/web/fonts/SchibstedGrotesk-OFL.txt](c08/web/fonts/SchibstedGrotesk-OFL.txt) | Font license: SchibstedGrotesk-OFL. |
| [c08/web/fonts/SchibstedGrotesk-var.woff2](c08/web/fonts/SchibstedGrotesk-var.woff2) | Bundled browser font: SchibstedGrotesk-var. |
| [c08/web/fx3d.js](c08/web/fx3d.js) | Renders illustrative orbital paths, schematic spacecraft and map effects. |
| [c08/web/index.html](c08/web/index.html) | Defines workspace structure, navigation, controls and script entry points. |
| [c08/web/intro.js](c08/web/intro.js) | Handles loading-screen readiness, dismissal and keyboard focus. |
| [c08/web/layers.js](c08/web/layers.js) | Manages map overlay layers and their controls. |
| [c08/web/manifest.webmanifest](c08/web/manifest.webmanifest) | Defines browser application identity, icons and installation metadata. |
| [c08/web/map3d.js](c08/web/map3d.js) | Implements the MapLibre map engine, terrain, camera and 3D layers. |
| [c08/web/satellite-era.js](c08/web/satellite-era.js) | Filters spacecraft by launch date and computes illustrative orbit phase. |
| [c08/web/satellite-intro.css](c08/web/satellite-intro.css) | Styles the responsive loading screen and orbital illustration. |
| [c08/web/science.js](c08/web/science.js) | Presents scientific context and supporting analysis in the interface. |
| [c08/web/showcase.css](c08/web/showcase.css) | Styles story cards and showcase views. |
| [c08/web/showcase.js](c08/web/showcase.js) | Renders showcase stories from saved scientific results. |
| [c08/web/style.css](c08/web/style.css) | Defines layout, typography, themes, controls and responsive behavior. |
| [c08/web/terrain/4/10/6.png](c08/web/terrain/4/10/6.png) | Local terrain map tile/asset: 4/10/6.png. |
| [c08/web/terrain/4/10/7.png](c08/web/terrain/4/10/7.png) | Local terrain map tile/asset: 4/10/7.png. |
| [c08/web/terrain/4/11/6.png](c08/web/terrain/4/11/6.png) | Local terrain map tile/asset: 4/11/6.png. |
| [c08/web/terrain/4/11/7.png](c08/web/terrain/4/11/7.png) | Local terrain map tile/asset: 4/11/7.png. |
| [c08/web/terrain/5/21/12.png](c08/web/terrain/5/21/12.png) | Local terrain map tile/asset: 5/21/12.png. |
| [c08/web/terrain/5/21/13.png](c08/web/terrain/5/21/13.png) | Local terrain map tile/asset: 5/21/13.png. |
| [c08/web/terrain/5/21/14.png](c08/web/terrain/5/21/14.png) | Local terrain map tile/asset: 5/21/14.png. |
| [c08/web/terrain/5/22/12.png](c08/web/terrain/5/22/12.png) | Local terrain map tile/asset: 5/22/12.png. |
| [c08/web/terrain/5/22/13.png](c08/web/terrain/5/22/13.png) | Local terrain map tile/asset: 5/22/13.png. |
| [c08/web/terrain/5/22/14.png](c08/web/terrain/5/22/14.png) | Local terrain map tile/asset: 5/22/14.png. |
| [c08/web/terrain/5/23/12.png](c08/web/terrain/5/23/12.png) | Local terrain map tile/asset: 5/23/12.png. |
| [c08/web/terrain/5/23/13.png](c08/web/terrain/5/23/13.png) | Local terrain map tile/asset: 5/23/13.png. |
| [c08/web/terrain/5/23/14.png](c08/web/terrain/5/23/14.png) | Local terrain map tile/asset: 5/23/14.png. |
| [c08/web/terrain/6/42/24.png](c08/web/terrain/6/42/24.png) | Local terrain map tile/asset: 6/42/24.png. |
| [c08/web/terrain/6/42/25.png](c08/web/terrain/6/42/25.png) | Local terrain map tile/asset: 6/42/25.png. |
| [c08/web/terrain/6/42/26.png](c08/web/terrain/6/42/26.png) | Local terrain map tile/asset: 6/42/26.png. |
| [c08/web/terrain/6/42/27.png](c08/web/terrain/6/42/27.png) | Local terrain map tile/asset: 6/42/27.png. |
| [c08/web/terrain/6/42/28.png](c08/web/terrain/6/42/28.png) | Local terrain map tile/asset: 6/42/28.png. |
| [c08/web/terrain/6/43/24.png](c08/web/terrain/6/43/24.png) | Local terrain map tile/asset: 6/43/24.png. |
| [c08/web/terrain/6/43/25.png](c08/web/terrain/6/43/25.png) | Local terrain map tile/asset: 6/43/25.png. |
| [c08/web/terrain/6/43/26.png](c08/web/terrain/6/43/26.png) | Local terrain map tile/asset: 6/43/26.png. |
| [c08/web/terrain/6/43/27.png](c08/web/terrain/6/43/27.png) | Local terrain map tile/asset: 6/43/27.png. |
| [c08/web/terrain/6/43/28.png](c08/web/terrain/6/43/28.png) | Local terrain map tile/asset: 6/43/28.png. |
| [c08/web/terrain/6/44/24.png](c08/web/terrain/6/44/24.png) | Local terrain map tile/asset: 6/44/24.png. |
| [c08/web/terrain/6/44/25.png](c08/web/terrain/6/44/25.png) | Local terrain map tile/asset: 6/44/25.png. |
| [c08/web/terrain/6/44/26.png](c08/web/terrain/6/44/26.png) | Local terrain map tile/asset: 6/44/26.png. |
| [c08/web/terrain/6/44/27.png](c08/web/terrain/6/44/27.png) | Local terrain map tile/asset: 6/44/27.png. |
| [c08/web/terrain/6/44/28.png](c08/web/terrain/6/44/28.png) | Local terrain map tile/asset: 6/44/28.png. |
| [c08/web/terrain/6/45/24.png](c08/web/terrain/6/45/24.png) | Local terrain map tile/asset: 6/45/24.png. |
| [c08/web/terrain/6/45/25.png](c08/web/terrain/6/45/25.png) | Local terrain map tile/asset: 6/45/25.png. |
| [c08/web/terrain/6/45/26.png](c08/web/terrain/6/45/26.png) | Local terrain map tile/asset: 6/45/26.png. |
| [c08/web/terrain/6/45/27.png](c08/web/terrain/6/45/27.png) | Local terrain map tile/asset: 6/45/27.png. |
| [c08/web/terrain/6/45/28.png](c08/web/terrain/6/45/28.png) | Local terrain map tile/asset: 6/45/28.png. |
| [c08/web/terrain/6/46/24.png](c08/web/terrain/6/46/24.png) | Local terrain map tile/asset: 6/46/24.png. |
| [c08/web/terrain/6/46/25.png](c08/web/terrain/6/46/25.png) | Local terrain map tile/asset: 6/46/25.png. |
| [c08/web/terrain/6/46/26.png](c08/web/terrain/6/46/26.png) | Local terrain map tile/asset: 6/46/26.png. |
| [c08/web/terrain/6/46/27.png](c08/web/terrain/6/46/27.png) | Local terrain map tile/asset: 6/46/27.png. |
| [c08/web/terrain/6/46/28.png](c08/web/terrain/6/46/28.png) | Local terrain map tile/asset: 6/46/28.png. |
| [c08/web/terrain/7/84/48.png](c08/web/terrain/7/84/48.png) | Local terrain map tile/asset: 7/84/48.png. |
| [c08/web/terrain/7/84/49.png](c08/web/terrain/7/84/49.png) | Local terrain map tile/asset: 7/84/49.png. |
| [c08/web/terrain/7/84/50.png](c08/web/terrain/7/84/50.png) | Local terrain map tile/asset: 7/84/50.png. |
| [c08/web/terrain/7/84/51.png](c08/web/terrain/7/84/51.png) | Local terrain map tile/asset: 7/84/51.png. |
| [c08/web/terrain/7/84/52.png](c08/web/terrain/7/84/52.png) | Local terrain map tile/asset: 7/84/52.png. |
| [c08/web/terrain/7/84/53.png](c08/web/terrain/7/84/53.png) | Local terrain map tile/asset: 7/84/53.png. |
| [c08/web/terrain/7/84/54.png](c08/web/terrain/7/84/54.png) | Local terrain map tile/asset: 7/84/54.png. |
| [c08/web/terrain/7/84/55.png](c08/web/terrain/7/84/55.png) | Local terrain map tile/asset: 7/84/55.png. |
| [c08/web/terrain/7/84/56.png](c08/web/terrain/7/84/56.png) | Local terrain map tile/asset: 7/84/56.png. |
| [c08/web/terrain/7/85/48.png](c08/web/terrain/7/85/48.png) | Local terrain map tile/asset: 7/85/48.png. |
| [c08/web/terrain/7/85/49.png](c08/web/terrain/7/85/49.png) | Local terrain map tile/asset: 7/85/49.png. |
| [c08/web/terrain/7/85/50.png](c08/web/terrain/7/85/50.png) | Local terrain map tile/asset: 7/85/50.png. |
| [c08/web/terrain/7/85/51.png](c08/web/terrain/7/85/51.png) | Local terrain map tile/asset: 7/85/51.png. |
| [c08/web/terrain/7/85/52.png](c08/web/terrain/7/85/52.png) | Local terrain map tile/asset: 7/85/52.png. |
| [c08/web/terrain/7/85/53.png](c08/web/terrain/7/85/53.png) | Local terrain map tile/asset: 7/85/53.png. |
| [c08/web/terrain/7/85/54.png](c08/web/terrain/7/85/54.png) | Local terrain map tile/asset: 7/85/54.png. |
| [c08/web/terrain/7/85/55.png](c08/web/terrain/7/85/55.png) | Local terrain map tile/asset: 7/85/55.png. |
| [c08/web/terrain/7/85/56.png](c08/web/terrain/7/85/56.png) | Local terrain map tile/asset: 7/85/56.png. |
| [c08/web/terrain/7/86/48.png](c08/web/terrain/7/86/48.png) | Local terrain map tile/asset: 7/86/48.png. |
| [c08/web/terrain/7/86/49.png](c08/web/terrain/7/86/49.png) | Local terrain map tile/asset: 7/86/49.png. |
| [c08/web/terrain/7/86/50.png](c08/web/terrain/7/86/50.png) | Local terrain map tile/asset: 7/86/50.png. |
| [c08/web/terrain/7/86/51.png](c08/web/terrain/7/86/51.png) | Local terrain map tile/asset: 7/86/51.png. |
| [c08/web/terrain/7/86/52.png](c08/web/terrain/7/86/52.png) | Local terrain map tile/asset: 7/86/52.png. |
| [c08/web/terrain/7/86/53.png](c08/web/terrain/7/86/53.png) | Local terrain map tile/asset: 7/86/53.png. |
| [c08/web/terrain/7/86/54.png](c08/web/terrain/7/86/54.png) | Local terrain map tile/asset: 7/86/54.png. |
| [c08/web/terrain/7/86/55.png](c08/web/terrain/7/86/55.png) | Local terrain map tile/asset: 7/86/55.png. |
| [c08/web/terrain/7/86/56.png](c08/web/terrain/7/86/56.png) | Local terrain map tile/asset: 7/86/56.png. |
| [c08/web/terrain/7/87/48.png](c08/web/terrain/7/87/48.png) | Local terrain map tile/asset: 7/87/48.png. |
| [c08/web/terrain/7/87/49.png](c08/web/terrain/7/87/49.png) | Local terrain map tile/asset: 7/87/49.png. |
| [c08/web/terrain/7/87/50.png](c08/web/terrain/7/87/50.png) | Local terrain map tile/asset: 7/87/50.png. |
| [c08/web/terrain/7/87/51.png](c08/web/terrain/7/87/51.png) | Local terrain map tile/asset: 7/87/51.png. |
| [c08/web/terrain/7/87/52.png](c08/web/terrain/7/87/52.png) | Local terrain map tile/asset: 7/87/52.png. |
| [c08/web/terrain/7/87/53.png](c08/web/terrain/7/87/53.png) | Local terrain map tile/asset: 7/87/53.png. |
| [c08/web/terrain/7/87/54.png](c08/web/terrain/7/87/54.png) | Local terrain map tile/asset: 7/87/54.png. |
| [c08/web/terrain/7/87/55.png](c08/web/terrain/7/87/55.png) | Local terrain map tile/asset: 7/87/55.png. |
| [c08/web/terrain/7/87/56.png](c08/web/terrain/7/87/56.png) | Local terrain map tile/asset: 7/87/56.png. |
| [c08/web/terrain/7/88/48.png](c08/web/terrain/7/88/48.png) | Local terrain map tile/asset: 7/88/48.png. |
| [c08/web/terrain/7/88/49.png](c08/web/terrain/7/88/49.png) | Local terrain map tile/asset: 7/88/49.png. |
| [c08/web/terrain/7/88/50.png](c08/web/terrain/7/88/50.png) | Local terrain map tile/asset: 7/88/50.png. |
| [c08/web/terrain/7/88/51.png](c08/web/terrain/7/88/51.png) | Local terrain map tile/asset: 7/88/51.png. |
| [c08/web/terrain/7/88/52.png](c08/web/terrain/7/88/52.png) | Local terrain map tile/asset: 7/88/52.png. |
| [c08/web/terrain/7/88/53.png](c08/web/terrain/7/88/53.png) | Local terrain map tile/asset: 7/88/53.png. |
| [c08/web/terrain/7/88/54.png](c08/web/terrain/7/88/54.png) | Local terrain map tile/asset: 7/88/54.png. |
| [c08/web/terrain/7/88/55.png](c08/web/terrain/7/88/55.png) | Local terrain map tile/asset: 7/88/55.png. |
| [c08/web/terrain/7/88/56.png](c08/web/terrain/7/88/56.png) | Local terrain map tile/asset: 7/88/56.png. |
| [c08/web/terrain/7/89/48.png](c08/web/terrain/7/89/48.png) | Local terrain map tile/asset: 7/89/48.png. |
| [c08/web/terrain/7/89/49.png](c08/web/terrain/7/89/49.png) | Local terrain map tile/asset: 7/89/49.png. |
| [c08/web/terrain/7/89/50.png](c08/web/terrain/7/89/50.png) | Local terrain map tile/asset: 7/89/50.png. |
| [c08/web/terrain/7/89/51.png](c08/web/terrain/7/89/51.png) | Local terrain map tile/asset: 7/89/51.png. |
| [c08/web/terrain/7/89/52.png](c08/web/terrain/7/89/52.png) | Local terrain map tile/asset: 7/89/52.png. |
| [c08/web/terrain/7/89/53.png](c08/web/terrain/7/89/53.png) | Local terrain map tile/asset: 7/89/53.png. |
| [c08/web/terrain/7/89/54.png](c08/web/terrain/7/89/54.png) | Local terrain map tile/asset: 7/89/54.png. |
| [c08/web/terrain/7/89/55.png](c08/web/terrain/7/89/55.png) | Local terrain map tile/asset: 7/89/55.png. |
| [c08/web/terrain/7/89/56.png](c08/web/terrain/7/89/56.png) | Local terrain map tile/asset: 7/89/56.png. |
| [c08/web/terrain/7/90/48.png](c08/web/terrain/7/90/48.png) | Local terrain map tile/asset: 7/90/48.png. |
| [c08/web/terrain/7/90/49.png](c08/web/terrain/7/90/49.png) | Local terrain map tile/asset: 7/90/49.png. |
| [c08/web/terrain/7/90/50.png](c08/web/terrain/7/90/50.png) | Local terrain map tile/asset: 7/90/50.png. |
| [c08/web/terrain/7/90/51.png](c08/web/terrain/7/90/51.png) | Local terrain map tile/asset: 7/90/51.png. |
| [c08/web/terrain/7/90/52.png](c08/web/terrain/7/90/52.png) | Local terrain map tile/asset: 7/90/52.png. |
| [c08/web/terrain/7/90/53.png](c08/web/terrain/7/90/53.png) | Local terrain map tile/asset: 7/90/53.png. |
| [c08/web/terrain/7/90/54.png](c08/web/terrain/7/90/54.png) | Local terrain map tile/asset: 7/90/54.png. |
| [c08/web/terrain/7/90/55.png](c08/web/terrain/7/90/55.png) | Local terrain map tile/asset: 7/90/55.png. |
| [c08/web/terrain/7/90/56.png](c08/web/terrain/7/90/56.png) | Local terrain map tile/asset: 7/90/56.png. |
| [c08/web/terrain/7/91/48.png](c08/web/terrain/7/91/48.png) | Local terrain map tile/asset: 7/91/48.png. |
| [c08/web/terrain/7/91/49.png](c08/web/terrain/7/91/49.png) | Local terrain map tile/asset: 7/91/49.png. |
| [c08/web/terrain/7/91/50.png](c08/web/terrain/7/91/50.png) | Local terrain map tile/asset: 7/91/50.png. |
| [c08/web/terrain/7/91/51.png](c08/web/terrain/7/91/51.png) | Local terrain map tile/asset: 7/91/51.png. |
| [c08/web/terrain/7/91/52.png](c08/web/terrain/7/91/52.png) | Local terrain map tile/asset: 7/91/52.png. |
| [c08/web/terrain/7/91/53.png](c08/web/terrain/7/91/53.png) | Local terrain map tile/asset: 7/91/53.png. |
| [c08/web/terrain/7/91/54.png](c08/web/terrain/7/91/54.png) | Local terrain map tile/asset: 7/91/54.png. |
| [c08/web/terrain/7/91/55.png](c08/web/terrain/7/91/55.png) | Local terrain map tile/asset: 7/91/55.png. |
| [c08/web/terrain/7/91/56.png](c08/web/terrain/7/91/56.png) | Local terrain map tile/asset: 7/91/56.png. |
| [c08/web/terrain/7/92/48.png](c08/web/terrain/7/92/48.png) | Local terrain map tile/asset: 7/92/48.png. |
| [c08/web/terrain/7/92/49.png](c08/web/terrain/7/92/49.png) | Local terrain map tile/asset: 7/92/49.png. |
| [c08/web/terrain/7/92/50.png](c08/web/terrain/7/92/50.png) | Local terrain map tile/asset: 7/92/50.png. |
| [c08/web/terrain/7/92/51.png](c08/web/terrain/7/92/51.png) | Local terrain map tile/asset: 7/92/51.png. |
| [c08/web/terrain/7/92/52.png](c08/web/terrain/7/92/52.png) | Local terrain map tile/asset: 7/92/52.png. |
| [c08/web/terrain/7/92/53.png](c08/web/terrain/7/92/53.png) | Local terrain map tile/asset: 7/92/53.png. |
| [c08/web/terrain/7/92/54.png](c08/web/terrain/7/92/54.png) | Local terrain map tile/asset: 7/92/54.png. |
| [c08/web/terrain/7/92/55.png](c08/web/terrain/7/92/55.png) | Local terrain map tile/asset: 7/92/55.png. |
| [c08/web/terrain/7/92/56.png](c08/web/terrain/7/92/56.png) | Local terrain map tile/asset: 7/92/56.png. |
| [c08/web/terrain/7/93/48.png](c08/web/terrain/7/93/48.png) | Local terrain map tile/asset: 7/93/48.png. |
| [c08/web/terrain/7/93/49.png](c08/web/terrain/7/93/49.png) | Local terrain map tile/asset: 7/93/49.png. |
| [c08/web/terrain/7/93/50.png](c08/web/terrain/7/93/50.png) | Local terrain map tile/asset: 7/93/50.png. |
| [c08/web/terrain/7/93/51.png](c08/web/terrain/7/93/51.png) | Local terrain map tile/asset: 7/93/51.png. |
| [c08/web/terrain/7/93/52.png](c08/web/terrain/7/93/52.png) | Local terrain map tile/asset: 7/93/52.png. |
| [c08/web/terrain/7/93/53.png](c08/web/terrain/7/93/53.png) | Local terrain map tile/asset: 7/93/53.png. |
| [c08/web/terrain/7/93/54.png](c08/web/terrain/7/93/54.png) | Local terrain map tile/asset: 7/93/54.png. |
| [c08/web/terrain/7/93/55.png](c08/web/terrain/7/93/55.png) | Local terrain map tile/asset: 7/93/55.png. |
| [c08/web/terrain/7/93/56.png](c08/web/terrain/7/93/56.png) | Local terrain map tile/asset: 7/93/56.png. |
| [c08/web/terrain/TILES.json](c08/web/terrain/TILES.json) | Local terrain map tile/asset: TILES.json. |
| [c08/web/vendor/maplibre/LICENSE.txt](c08/web/vendor/maplibre/LICENSE.txt) | Upstream MapLibre license notice. |
| [c08/web/vendor/maplibre/VERSION.json](c08/web/vendor/maplibre/VERSION.json) | Bundled MapLibre browser asset: VERSION.json. |
| [c08/web/vendor/maplibre/maplibre-gl.css](c08/web/vendor/maplibre/maplibre-gl.css) | Bundled MapLibre browser asset: maplibre-gl.css. |
| [c08/web/vendor/maplibre/maplibre-gl.js](c08/web/vendor/maplibre/maplibre-gl.js) | Bundled MapLibre browser asset: maplibre-gl.js. |

## Cached scientific inputs

| File | Purpose |
|---|---|
| [data/coverage/MYD14A1_2025-08-05_h24v05_aoi.npz](data/coverage/MYD14A1_2025-08-05_h24v05_aoi.npz) | Saved daily coverage grid: MYD14A1_2025-08-05_h24v05_aoi. |
| [data/coverage/MYD14A1_2025-11-01_h24v05_aoi.npz](data/coverage/MYD14A1_2025-11-01_h24v05_aoi.npz) | Saved daily coverage grid: MYD14A1_2025-11-01_h24v05_aoi. |
| [data/coverage/manifest.json](data/coverage/manifest.json) | Coverage-example inventory and source/class metadata. |
| [data/manifest.json](data/manifest.json) | Acquisition inventory with source identifiers, retrieval metadata and file hashes. |
| [data/processed/pak_detections.parquet](data/processed/pak_detections.parquet) | Frozen Pakistan detection table: 1,565,651 rows and 22 columns; read-only runtime input. |
| [data/raw/boundaries/pak_adm1.geojson](data/raw/boundaries/pak_adm1.geojson) | Full-resolution province geometry used to assign detections. |
| [data/raw/boundaries/pak_adm1_simplified.geojson](data/raw/boundaries/pak_adm1_simplified.geojson) | Simplified province display geometry. |
| [data/raw/boundaries/pak_adm1_source.json](data/raw/boundaries/pak_adm1_source.json) | Pakistan administrative-boundary source and licensing metadata. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-01_5d.csv) | Cached FIRMS observations: 2026-08-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-06_5d.csv) | Cached FIRMS observations: 2026-08-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-11_5d.csv) | Cached FIRMS observations: 2026-08-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-16_5d.csv) | Cached FIRMS observations: 2026-08-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-21_5d.csv) | Cached FIRMS observations: 2026-08-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-26_5d.csv) | Cached FIRMS observations: 2026-08-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-08-31_1d.csv) | Cached FIRMS observations: 2026-08-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-01_5d.csv) | Cached FIRMS observations: 2026-09-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-06_5d.csv) | Cached FIRMS observations: 2026-09-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-11_5d.csv) | Cached FIRMS observations: 2026-09-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-16_5d.csv) | Cached FIRMS observations: 2026-09-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-21_5d.csv) | Cached FIRMS observations: 2026-09-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-09-26_5d.csv) | Cached FIRMS observations: 2026-09-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-01_5d.csv) | Cached FIRMS observations: 2026-10-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-06_5d.csv) | Cached FIRMS observations: 2026-10-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-11_5d.csv) | Cached FIRMS observations: 2026-10-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-16_5d.csv) | Cached FIRMS observations: 2026-10-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-21_5d.csv) | Cached FIRMS observations: 2026-10-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-26_5d.csv) | Cached FIRMS observations: 2026-10-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_NRT/2026-10-31_1d.csv) | Cached FIRMS observations: 2026-10-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-01_5d.csv) | Cached FIRMS observations: 2026-01-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-06_5d.csv) | Cached FIRMS observations: 2026-01-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-11_5d.csv) | Cached FIRMS observations: 2026-01-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-16_5d.csv) | Cached FIRMS observations: 2026-01-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-21_5d.csv) | Cached FIRMS observations: 2026-01-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-26_5d.csv) | Cached FIRMS observations: 2026-01-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-01-31_1d.csv) | Cached FIRMS observations: 2026-01-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-01_5d.csv) | Cached FIRMS observations: 2026-02-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-06_5d.csv) | Cached FIRMS observations: 2026-02-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-11_5d.csv) | Cached FIRMS observations: 2026-02-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-16_5d.csv) | Cached FIRMS observations: 2026-02-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-21_5d.csv) | Cached FIRMS observations: 2026-02-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-26_3d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-02-26_3d.csv) | Cached FIRMS observations: 2026-02-26_3d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-01_5d.csv) | Cached FIRMS observations: 2026-03-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-06_5d.csv) | Cached FIRMS observations: 2026-03-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-11_5d.csv) | Cached FIRMS observations: 2026-03-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-16_5d.csv) | Cached FIRMS observations: 2026-03-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-21_5d.csv) | Cached FIRMS observations: 2026-03-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-26_5d.csv) | Cached FIRMS observations: 2026-03-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-03-31_1d.csv) | Cached FIRMS observations: 2026-03-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-01_5d.csv) | Cached FIRMS observations: 2026-04-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-06_5d.csv) | Cached FIRMS observations: 2026-04-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-11_5d.csv) | Cached FIRMS observations: 2026-04-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-16_5d.csv) | Cached FIRMS observations: 2026-04-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-21_5d.csv) | Cached FIRMS observations: 2026-04-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-04-26_5d.csv) | Cached FIRMS observations: 2026-04-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-01_5d.csv) | Cached FIRMS observations: 2026-05-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-06_5d.csv) | Cached FIRMS observations: 2026-05-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-11_5d.csv) | Cached FIRMS observations: 2026-05-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-16_5d.csv) | Cached FIRMS observations: 2026-05-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-21_5d.csv) | Cached FIRMS observations: 2026-05-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-26_5d.csv) | Cached FIRMS observations: 2026-05-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-05-31_1d.csv) | Cached FIRMS observations: 2026-05-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-01_5d.csv) | Cached FIRMS observations: 2026-06-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-06_5d.csv) | Cached FIRMS observations: 2026-06-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-11_5d.csv) | Cached FIRMS observations: 2026-06-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-16_5d.csv) | Cached FIRMS observations: 2026-06-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-21_5d.csv) | Cached FIRMS observations: 2026-06-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-06-26_5d.csv) | Cached FIRMS observations: 2026-06-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-01_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-01_5d.csv) | Cached FIRMS observations: 2026-07-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-06_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-06_5d.csv) | Cached FIRMS observations: 2026-07-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-11_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-11_5d.csv) | Cached FIRMS observations: 2026-07-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-16_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-16_5d.csv) | Cached FIRMS observations: 2026-07-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-21_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-21_5d.csv) | Cached FIRMS observations: 2026-07-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-26_5d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-26_5d.csv) | Cached FIRMS observations: 2026-07-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-31_1d.csv](data/raw/firms_api/VIIRS_NOAA20_SP/2026-07-31_1d.csv) | Cached FIRMS observations: 2026-07-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-01_5d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-01_5d.csv) | Cached FIRMS observations: 2026-10-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-06_5d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-06_5d.csv) | Cached FIRMS observations: 2026-10-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-11_5d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-11_5d.csv) | Cached FIRMS observations: 2026-10-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-16_5d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-16_5d.csv) | Cached FIRMS observations: 2026-10-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-21_5d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-21_5d.csv) | Cached FIRMS observations: 2026-10-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-26_4d.csv](data/raw/firms_api/VIIRS_NOAA21_NRT/2026-10-26_4d.csv) | Cached FIRMS observations: 2026-10-26_4d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-01_5d.csv) | Cached FIRMS observations: 2026-08-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-06_5d.csv) | Cached FIRMS observations: 2026-08-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-11_5d.csv) | Cached FIRMS observations: 2026-08-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-16_5d.csv) | Cached FIRMS observations: 2026-08-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-21_5d.csv) | Cached FIRMS observations: 2026-08-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-26_5d.csv) | Cached FIRMS observations: 2026-08-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-08-31_1d.csv) | Cached FIRMS observations: 2026-08-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-01_5d.csv) | Cached FIRMS observations: 2026-09-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-06_5d.csv) | Cached FIRMS observations: 2026-09-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-11_5d.csv) | Cached FIRMS observations: 2026-09-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-16_5d.csv) | Cached FIRMS observations: 2026-09-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-21_5d.csv) | Cached FIRMS observations: 2026-09-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-09-26_5d.csv) | Cached FIRMS observations: 2026-09-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-01_5d.csv) | Cached FIRMS observations: 2026-10-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-06_5d.csv) | Cached FIRMS observations: 2026-10-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-11_5d.csv) | Cached FIRMS observations: 2026-10-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-16_5d.csv) | Cached FIRMS observations: 2026-10-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-21_5d.csv) | Cached FIRMS observations: 2026-10-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-26_5d.csv) | Cached FIRMS observations: 2026-10-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_NRT/2026-10-31_1d.csv) | Cached FIRMS observations: 2026-10-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-01_5d.csv) | Cached FIRMS observations: 2026-01-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-06_5d.csv) | Cached FIRMS observations: 2026-01-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-11_5d.csv) | Cached FIRMS observations: 2026-01-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-16_5d.csv) | Cached FIRMS observations: 2026-01-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-21_5d.csv) | Cached FIRMS observations: 2026-01-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-26_5d.csv) | Cached FIRMS observations: 2026-01-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-01-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-01-31_1d.csv) | Cached FIRMS observations: 2026-01-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-01_5d.csv) | Cached FIRMS observations: 2026-02-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-06_5d.csv) | Cached FIRMS observations: 2026-02-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-11_5d.csv) | Cached FIRMS observations: 2026-02-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-16_5d.csv) | Cached FIRMS observations: 2026-02-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-21_5d.csv) | Cached FIRMS observations: 2026-02-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-02-26_3d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-02-26_3d.csv) | Cached FIRMS observations: 2026-02-26_3d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-01_5d.csv) | Cached FIRMS observations: 2026-03-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-06_5d.csv) | Cached FIRMS observations: 2026-03-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-11_5d.csv) | Cached FIRMS observations: 2026-03-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-16_5d.csv) | Cached FIRMS observations: 2026-03-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-21_5d.csv) | Cached FIRMS observations: 2026-03-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-26_5d.csv) | Cached FIRMS observations: 2026-03-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-03-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-03-31_1d.csv) | Cached FIRMS observations: 2026-03-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-01_5d.csv) | Cached FIRMS observations: 2026-04-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-06_5d.csv) | Cached FIRMS observations: 2026-04-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-11_5d.csv) | Cached FIRMS observations: 2026-04-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-16_5d.csv) | Cached FIRMS observations: 2026-04-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-21_5d.csv) | Cached FIRMS observations: 2026-04-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-04-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-04-26_5d.csv) | Cached FIRMS observations: 2026-04-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-01_5d.csv) | Cached FIRMS observations: 2026-05-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-06_5d.csv) | Cached FIRMS observations: 2026-05-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-11_5d.csv) | Cached FIRMS observations: 2026-05-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-16_5d.csv) | Cached FIRMS observations: 2026-05-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-21_5d.csv) | Cached FIRMS observations: 2026-05-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-26_5d.csv) | Cached FIRMS observations: 2026-05-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-05-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-05-31_1d.csv) | Cached FIRMS observations: 2026-05-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-01_5d.csv) | Cached FIRMS observations: 2026-06-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-06_5d.csv) | Cached FIRMS observations: 2026-06-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-11_5d.csv) | Cached FIRMS observations: 2026-06-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-16_5d.csv) | Cached FIRMS observations: 2026-06-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-21_5d.csv) | Cached FIRMS observations: 2026-06-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-06-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-06-26_5d.csv) | Cached FIRMS observations: 2026-06-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-01_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-01_5d.csv) | Cached FIRMS observations: 2026-07-01_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-06_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-06_5d.csv) | Cached FIRMS observations: 2026-07-06_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-11_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-11_5d.csv) | Cached FIRMS observations: 2026-07-11_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-16_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-16_5d.csv) | Cached FIRMS observations: 2026-07-16_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-21_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-21_5d.csv) | Cached FIRMS observations: 2026-07-21_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-26_5d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-26_5d.csv) | Cached FIRMS observations: 2026-07-26_5d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_api/VIIRS_SNPP_SP/2026-07-31_1d.csv](data/raw/firms_api/VIIRS_SNPP_SP/2026-07-31_1d.csv) | Cached FIRMS observations: 2026-07-31_1d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261102T1200Z/J1_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261102T1200Z/J1_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: J1_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261102T1200Z/J2_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261102T1200Z/J2_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: J2_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261102T1200Z/MODIS_C6_1_South_Asia_7d.csv](data/raw/firms_nrt/20261102T1200Z/MODIS_C6_1_South_Asia_7d.csv) | Cached FIRMS observations: MODIS_C6_1_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261102T1200Z/SUOMI_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261102T1200Z/SUOMI_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: SUOMI_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261113T0615Z/J1_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261113T0615Z/J1_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: J1_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261113T0615Z/J2_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261113T0615Z/J2_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: J2_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261113T0615Z/MODIS_C6_1_South_Asia_7d.csv](data/raw/firms_nrt/20261113T0615Z/MODIS_C6_1_South_Asia_7d.csv) | Cached FIRMS observations: MODIS_C6_1_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |
| [data/raw/firms_nrt/20261113T0615Z/SUOMI_VIIRS_C2_South_Asia_7d.csv](data/raw/firms_nrt/20261113T0615Z/SUOMI_VIIRS_C2_South_Asia_7d.csv) | Cached FIRMS observations: SUOMI_VIIRS_C2_South_Asia_7d; retain stream/date qualifiers from data/manifest.json. |

## Frozen protocols and results

| File | Purpose |
|---|---|
| [experiments/E00_first_run/punjab_monthly_selection_years.csv](experiments/E00_first_run/punjab_monthly_selection_years.csv) | Saved experiment artifact for E00_first_run; retain original values and limitations. |
| [experiments/E00_first_run/result.json](experiments/E00_first_run/result.json) | Saved scientific results for E00_first_run; retain original values and limitations. |
| [experiments/E01_selection/result.json](experiments/E01_selection/result.json) | Saved scientific results for E01_selection; retain original values and limitations. |
| [experiments/E01_selection/selection.json](experiments/E01_selection/selection.json) | Saved model-selection decision for E01_selection; retain original values and limitations. |
| [experiments/E02_evaluation/result.json](experiments/E02_evaluation/result.json) | Saved scientific results for E02_evaluation; retain original values and limitations. |
| [experiments/E03_sensitivity/result.json](experiments/E03_sensitivity/result.json) | Saved scientific results for E03_sensitivity; retain original values and limitations. |
| [experiments/O01_outlook/audit.json](experiments/O01_outlook/audit.json) | Saved experiment artifact for O01_outlook; retain original values and limitations. |
| [experiments/O01_outlook/holdout.json](experiments/O01_outlook/holdout.json) | Saved experiment artifact for O01_outlook; retain original values and limitations. |
| [experiments/O01_outlook/model.json](experiments/O01_outlook/model.json) | Saved experiment artifact for O01_outlook; retain original values and limitations. |
| [experiments/O01_outlook/predictions_holdout.csv](experiments/O01_outlook/predictions_holdout.csv) | Saved experiment artifact for O01_outlook; retain original values and limitations. |
| [experiments/O01_outlook/validation.json](experiments/O01_outlook/validation.json) | Saved experiment artifact for O01_outlook; retain original values and limitations. |
| [experiments/P02_F00_fit/result.json](experiments/P02_F00_fit/result.json) | Saved scientific results for P02_F00_fit; retain original values and limitations. |
| [experiments/P02_F01_camera/result.json](experiments/P02_F01_camera/result.json) | Saved scientific results for P02_F01_camera; retain original values and limitations. |
| [experiments/P02_F02_clock/result.json](experiments/P02_F02_clock/result.json) | Saved scientific results for P02_F02_clock; retain original values and limitations. |
| [experiments/P02_F03_burned_area/result.json](experiments/P02_F03_burned_area/result.json) | Saved scientific results for P02_F03_burned_area; retain original values and limitations. |
| [experiments/P04_G01_terra_step/result.json](experiments/P04_G01_terra_step/result.json) | Saved scientific results for P04_G01_terra_step; retain original values and limitations. |
| [experiments/P04_G02_season_dates/result.json](experiments/P04_G02_season_dates/result.json) | Saved scientific results for P04_G02_season_dates; retain original values and limitations. |
| [experiments/P04_G03_bridge_2026/result.json](experiments/P04_G03_bridge_2026/result.json) | Saved scientific results for P04_G03_bridge_2026; retain original values and limitations. |
| [experiments/P04_G04_headline/result.json](experiments/P04_G04_headline/result.json) | Saved scientific results for P04_G04_headline; retain original values and limitations. |
| [experiments/PROTOCOL_O01.md](experiments/PROTOCOL_O01.md) | Frozen scientific protocol: PROTOCOL_O01. |
| [experiments/PROTOCOL_P01.md](experiments/PROTOCOL_P01.md) | Frozen scientific protocol: PROTOCOL_P01. |
| [experiments/PROTOCOL_P02.md](experiments/PROTOCOL_P02.md) | Frozen scientific protocol: PROTOCOL_P02. |
| [experiments/PROTOCOL_P04.md](experiments/PROTOCOL_P04.md) | Frozen scientific protocol: PROTOCOL_P04. |

## Analysis artifacts

| File | Purpose |
|---|---|
| [reports/c08/ingest_report.json](reports/c08/ingest_report.json) | Ingestion validation and input summary (JSON). |
| [reports/c08/methods_report.html](reports/c08/methods_report.html) | Rendered methods, evidence and limitations report (HTML). |
| [reports/c08/methods_report.pdf](reports/c08/methods_report.pdf) | Rendered methods, evidence and limitations report (PDF). |
| [reports/c08/p02_posthoc.json](reports/c08/p02_posthoc.json) | Saved P02 post-hoc checks (JSON). |
| [reports/c08/p04_devcheck.json](reports/c08/p04_devcheck.json) | Saved P04 development checks (JSON). |
| [reports/c08/reproduction_check.json](reports/c08/reproduction_check.json) | Saved numerical reproduction check (JSON). |
| [reports/c08/s02_review_2026-11-05.json](reports/c08/s02_review_2026-11-05.json) | Saved analysis report: s02_review_2026-11-05 (JSON). |
| [reports/c08/seamline/handover_replay.json](reports/c08/seamline/handover_replay.json) | Saved sensor-handover replay (JSON). |
| [reports/c08/slides.html](reports/c08/slides.html) | Existing presentation deck (HTML). |
| [reports/c08/slides.pdf](reports/c08/slides.pdf) | Existing presentation deck (PDF). |
| [reports/c08/verification_log.json](reports/c08/verification_log.json) | Historical verification log (JSON). |

## Provider metadata

| File | Purpose |
|---|---|
| [research/metadata/provider_missing_dates.json](research/metadata/provider_missing_dates.json) | Provider missing-date evidence for the frozen historical analysis. |
| [research/metadata/provider_missing_dates_2026-11-08.json](research/metadata/provider_missing_dates_2026-11-08.json) | Provider missing-date evidence recorded 2026-11-08. |
