"""Seamline local web app: python -m c08.app  ->  http://127.0.0.1:8766

Screen and exports call the same c08.analysis functions. No external scripts,
fonts or tiles are loaded, so the cached demo works offline. No credentials are
read or sent; the server binds to localhost only.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

import pandas as pd
from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from . import analysis, boundaries, config, continuity, series
from . import showcase  # story cards, read from saved result files only
from . import handover, points, studio  # Seamline additions: map points, handover replay, Comparison Studio

WEB = config.ROOT / "c08" / "web"
app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 10_000


def _params(payload) -> dict:
    if not isinstance(payload, dict):
        raise analysis.AnalysisError("Send a JSON object")
    try:
        years = tuple(int(v) for v in payload.get("years", (analysis.FIRST_YEAR, analysis.LAST_YEAR)))
        month = payload.get("month")
        month = (int(month[0]), int(month[1])) if month else None
        if month and not 1 <= month[1] <= 12:
            raise ValueError("month must be 1-12")
        # Impossible years never reach the date code (they gave HTTP 500 before: readiness check, api-03).
        if any(not 1 <= y <= 9999 for y in years + ((month[0],) if month else ())):
            raise ValueError("year out of range")
    except (TypeError, ValueError, IndexError, OverflowError):  # OverflowError: e.g. a year of 1e400
        # A plain message, not Python's error text (readiness check, api-04).
        raise analysis.AnalysisError("Check the years and month: years are [start, end] as whole numbers, and the "
                                     "month is [year, month] with the month from 1 to 12.") from None
    if len(years) != 2:
        raise analysis.AnalysisError("Years need a start and an end")
    bbox = payload.get("bbox")
    return {"region": None if bbox else payload.get("region", "Punjab"), "bbox": bbox, "years": years,
            "month": month, "model": payload.get("model", analysis.MODEL_DEFAULT)}


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/favicon.ico")
def favicon():
    """Browsers ask for this on their own; answer "no content" rather than a JSON 404 (readiness check, api-05)."""
    return "", 204


@app.get("/report")
def report():
    f = config.REPORTS / "methods_report.html"
    if not f.is_file():
        raise analysis.AnalysisError("The methods report is not built yet. Run: python -m c08.report")
    return send_file(f)


@app.get("/slides")
def slides():
    f = config.REPORTS / "slides.html"
    if not f.is_file():
        raise analysis.AnalysisError("The slides are not built yet. Run: python -m c08.slides")
    return send_file(f)


@app.get("/api/meta")
def meta():
    return jsonify(analysis.meta() | {"evidence": analysis.evidence()})


@app.get("/api/boundaries")
def bounds():
    return jsonify(boundaries.simplified_geojson())


@app.get("/api/showcase")
def showcase_cards():
    """The five story cards (headline, seam, clock, season, log), read fresh from the saved result files.

    Nothing is computed from detection rows, so the P04 lock is not involved: a P04 card shows its test
    only once that test's result file exists, and says "Waiting for the frozen test" until then."""
    return jsonify(showcase.cards())


@app.get("/api/areas")
def areas():
    """Bounds, polygon size and centre of each selectable area, and the map's supported extent."""
    return jsonify(points.areas())


@app.post("/api/points")
def map_points():
    """Observed detections of one month for the map: {"region" or "bbox", "day_month": [year, month]}.
    The same rows as the detections export for that area, cut to the month."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise analysis.AnalysisError("Send a JSON object")
    ym = payload.get("day_month")
    if not isinstance(ym, (list, tuple)) or len(ym) != 2:
        raise analysis.AnalysisError("day_month needs a year and a month")
    bbox = payload.get("bbox")
    return jsonify(points.month_points(region=None if bbox else payload.get("region", "Punjab"), bbox=bbox,
                                       year=ym[0], month=ym[1]))


def _pair(payload) -> tuple[dict, dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("a"), dict) or not isinstance(payload.get("b"), dict):
        raise analysis.AnalysisError('Send {"a": selection, "b": selection}')
    return _params(payload["a"]), _params(payload["b"])


@app.post("/api/compare")
def compare():
    """Comparison Studio: two selections, each analysed on its own terms, and what may be said about the pair."""
    a, b = _pair(request.get_json(silent=True))
    return jsonify(studio.compare(a, b))


@app.get("/api/handover")
def handover_replay():
    """The saved 2026 bridge test as a day-by-day replay (built once by: python -m c08.handover build)."""
    try:
        return jsonify(handover.load() | {"available": True})
    except FileNotFoundError as e:
        return jsonify(available=False, reason=str(e))


@app.get("/api/coverage")
def coverage_layer():
    """The observation-coverage example (real fire-mask classes), or the exact reason it is not available."""
    from . import coverage
    return jsonify(coverage.summary())


@app.get("/api/coverage/<key>")
def coverage_grid(key):
    from . import coverage
    return jsonify(coverage.grid(key))


@app.get("/api/outlook")
def outlook():
    """The experimental outlook's saved evaluation and release-gate result (never computed on request)."""
    from . import outlook as ol
    return jsonify(ol.summary())


@app.post("/api/analyze")
def analyze():
    return jsonify(analysis.analyse(**_params(request.get_json(silent=True))))


@app.post("/api/daily")
def daily():
    """One month, day by day: {"region" or "bbox", "model", "day_month": [year, month]}."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise analysis.AnalysisError("Send a JSON object")
    ym = payload.get("day_month")
    if not isinstance(ym, (list, tuple)) or len(ym) != 2:
        raise analysis.AnalysisError("day_month needs a year and a month")
    bbox = payload.get("bbox")
    return jsonify(analysis.daily(region=None if bbox else payload.get("region", "Punjab"), bbox=bbox,
                                  year=ym[0], month=ym[1], model=payload.get("model", analysis.MODEL_DEFAULT)))


class _Sink:
    """Write-only buffer that a ZipFile streams into; take() hands over what is ready."""

    def __init__(self):
        self.parts = []

    def write(self, b):
        self.parts.append(bytes(b))
        return len(b)

    def flush(self):
        pass

    def take(self) -> bytes:
        out = b"".join(self.parts)
        self.parts.clear()
        return out


def _zip_stream(chunks, member: str):
    """Compress CSV blocks into a one-file ZIP while sending it, so memory stays small."""
    sink = _Sink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        with zf.open(member, "w", force_zip64=True) as f:
            for c in chunks:
                f.write(c)
                yield sink.take()
    yield sink.take()


def _compare_zip(payload, stamp: str):
    """Both panes of a comparison in one ZIP: the pair's summary and definitions, each pane's monthly values, and
    provenance. One snapshot: every file is computed from the same two selections."""
    a, b = _pair(payload)
    c = studio.compare(a, b)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        light = {k: ({kk: vv for kk, vv in v.items() if kk not in ("calendar", "series")} if k in ("a", "b") else v)
                 for k, v in c.items()}
        zf.writestr("comparison.json", json.dumps({"exported_utc": stamp, "product": "Seamline", "request": {"a": a, "b": b},
                                                   **light, "data_identity": analysis.data_identity(),
                                                   "inputs": analysis.meta(),
                                                   "provenance_contract": analysis.provenance_contract(),
                                                   "ingest_report": "reports/c08/ingest_report.json",
                                                   "protocol": "experiments/PROTOCOL_P01.md"}, indent=2, default=str))
        for key in ("a", "b"):
            t = pd.DataFrame(c[key]["series"])
            t.insert(0, "pane", key.upper())
            t.insert(1, "region", c[key]["region"])
            t["model"], t["units"], t["reference"] = c[key]["model"], c[key]["units"], c[key]["reference"]
            t["data_identity"] = c[key].get("data_identity", analysis.data_identity())
            t["row_kind"] = "derived monthly value (not observation-level)"
            zf.writestr(f"pane_{key}_monthly.csv", t.to_csv(index=False))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"seamline_comparison_{stamp}.zip")


@app.post("/api/export/<kind>")
def export(kind):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    if kind in ("compare", "compare.zip"):  # the page asks for "compare": Edge answered a fetch of a path ending in .zip with an empty 204
        return _compare_zip(request.get_json(silent=True), stamp)
    p = _params(request.get_json(silent=True))
    name = (p["region"] or "box").replace(" ", "_")
    if kind == "detections.csv":
        q, passes = analysis.detection_rows(region=p["region"], bbox=p["bbox"], years=p["years"], model=p["model"])
        row_kind = ("observation: one fire pixel on one satellite pass (quality-filtered; standard archive type 0, "
                    "or 2026 supplement stream/type_screen stated per row)"
                    if p["years"][1] >= continuity.FIRST_YEAR
                    else "observation: one fire pixel on one satellite pass (quality-filtered, type 0)")
        chunks = analysis.detections_csv_chunks(
            q, passes, extra={"row_kind": row_kind, "data_identity": analysis.data_identity()}, chunk=10_000)
        base = f"seamline_{name}_{p['years'][0]}-{p['years'][1]}_detections_csv_{stamp}"
        if len(q) <= analysis.EXPORT_PLAIN_MAX:
            headers = {"Content-Disposition": f'attachment; filename="{base}.csv"'}
            return Response(chunks, mimetype="text/csv", headers=headers)
        # Large selections (Punjab 2003-2025 is about 0.9 million rows) go out as a streamed ZIP.
        headers = {"Content-Disposition": f'attachment; filename="{base}.zip"'}
        if not q.attrs.get("rows_held_out"):  # no count while P04 rows are held out (it would leak them)
            headers["X-Detections-Rows"] = str(len(q))
        return Response(_zip_stream(chunks, base + ".csv"), mimetype="application/zip", headers=headers)
    if kind == "monthly.csv":
        r = analysis.analyse(**p)
        t = pd.DataFrame(r["months"])
        t.insert(0, "region", r["region"])
        t["model"] = r["model"]
        t["units"] = r["units"]
        t["reference"] = r["reference"]
        t["passes"] = r["passes"]
        t["data_identity"] = r["data_identity"]
        t["row_kind"] = "derived monthly value (not observation-level)"
        for col in t.columns:
            t[col] = t[col].map(lambda value: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value)
        body, mime = t.to_csv(index=False).encode("utf-8"), "text/csv"
    elif kind == "provenance.json":
        r = analysis.analyse(**p)
        prov = {"exported_utc": stamp, "request": p, "region": r["region"], "model": r["model"],
                "data_identity": r["data_identity"], "current_record": r["current_record"],
                "provenance_contract": analysis.provenance_contract(),
                "calibration": r["calibration"], "warnings": r["warnings"], "units": r["units"],
                "reference": r["reference"], "inputs": analysis.meta(), "evidence": analysis.evidence(),
                "ingest_report": "reports/c08/ingest_report.json", "protocol": "experiments/PROTOCOL_P01.md",
                "protocol_p04": "experiments/PROTOCOL_P04.md",
                "resource_review": "docs/RESOURCE_RELEASE_2026-11-13.md",
                "change": r["change"], "comparison": r["comparison"], "latest": r["latest"]}
        body, mime = json.dumps(prov, indent=2, default=str).encode("utf-8"), "application/json"
    else:
        raise analysis.AnalysisError("Export must be monthly.csv, detections.csv, provenance.json or compare")
    return send_file(io.BytesIO(body), mimetype=mime, as_attachment=True,
                     download_name=f"seamline_{name}_{p['years'][0]}-{p['years'][1]}_{kind.replace('.', '_')}_{stamp}"
                                   f".{kind.rsplit('.', 1)[1]}")


@app.errorhandler(analysis.AnalysisError)
@app.errorhandler(series.SelectionError)
@app.errorhandler(continuity.ContinuityError)
def bad_request(e):
    return jsonify(status="error", message=str(e)), 400


@app.errorhandler(Exception)
def unexpected(e):
    if isinstance(e, HTTPException):  # 404, 405 and friends keep their own status
        return jsonify(status="error", message=e.description), e.code
    app.logger.exception("Unexpected error")
    return jsonify(status="error", message="Unexpected server error; the details are in the server log."), 500


def warm() -> None:
    """Load the detections and compute the page's default view once, so the first page load is quick (readiness
    check, 9 Nov). A failure here never stops the server: the page then computes the view on request."""
    analysis.detections()
    try:
        m = analysis.meta()
        y0, y1 = m["years"]
        model = m.get("default_model", "M2")
        for mo_year in ({min(2025, y1), y1}):
            analysis.analyse(**_params({"region": "Punjab", "years": [y0, y1], "month": [mo_year, 11],
                                        "model": model}))
    except Exception:  # noqa: BLE001 - a warm-up must never stop the server
        app.logger.exception("Warm-up of the default view failed")


def main(port: int = 8766) -> None:
    warm()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
