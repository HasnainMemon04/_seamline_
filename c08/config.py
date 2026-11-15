"""Paths, sensor registry and fixed constants shared by the pipeline.

Values here are declared before analysis. Changing a value that affects the
science (filters, grid, splits) requires a new experiment ID in experiments/.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_COUNTRY = DATA / "raw" / "firms_country"
RAW_NRT = DATA / "raw" / "firms_nrt"
RAW_BOUNDARIES = DATA / "raw" / "boundaries"
PROCESSED = DATA / "processed"
BOUNDARIES = DATA / "boundaries"
MANIFEST = DATA / "manifest.json"
EXPERIMENTS = ROOT / "experiments"
REPORTS = ROOT / "reports" / "c08"

COUNTRY = "Pakistan"
FIRMS_COUNTRY_BASE = "https://firms.modaps.eosdis.nasa.gov/data/country"
USER_AGENT = "Seamline-C08-research-prototype/0.3 (NASA Space Apps 2026 learning project)"

# Download budget for one acquisition run, checked against HEAD sizes before any GET.
DOWNLOAD_BUDGET_BYTES = 400 * 1024**2
# Keep this much disk free; the laptop's C: drive is nearly full. Hasnain lowered the floor from 2 GB to
# 200 MB on 8 Nov 2026 ("dont care of storage even till space left by on 200 mg"); see DECISIONS.md.
MIN_FREE_DISK_BYTES = 200 * 1024**2


@dataclass(frozen=True)
class CountrySource:
    """One FIRMS country-archive family (one folder on the FIRMS server)."""

    key: str            # FIRMS folder name
    instrument: str
    platforms: tuple[str, ...]
    first_year: int
    last_year: int
    product: str
    doi: str


# Years are the span requested; files that do not exist are recorded as absent.
COUNTRY_SOURCES = (
    CountrySource("modis", "MODIS", ("Terra", "Aqua"), 2000, 2025,
                  "MODIS Collection 6.1 active fire (MCD14ML via FIRMS country archive)",
                  "10.5067/FIRMS/MODIS/MCD14ML"),
    CountrySource("viirs-snpp", "VIIRS", ("SNPP",), 2012, 2025,
                  "VIIRS 375 m S-NPP active fire, Collection 2 (VNP14IMG via FIRMS country archive)",
                  "10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002"),
    CountrySource("viirs-jpss1", "VIIRS", ("NOAA20",), 2018, 2025,
                  "VIIRS 375 m NOAA-20 active fire, Collection 2 (VJ114IMG via FIRMS country archive)",
                  "10.5067/FIRMS/VIIRS/VJ114IMGT_NRT.002"),
)

# Public FIRMS near-real-time regional files (last 7 days, no key needed).
NRT_SOURCES = {
    "MODIS_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_South_Asia_7d.csv",
    "SNPP_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_7d.csv",
    "NOAA20_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_Asia_7d.csv",
    "NOAA21_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_South_Asia_7d.csv",
}

# Product-specific quality rules (confidence is not a probability for either sensor).
MODIS_MIN_CONFIDENCE = 30          # FIRMS: low < 30, nominal 30-79, high >= 80
VIIRS_KEEP_CONFIDENCE = ("n", "h")  # nominal and high; "l" (low) excluded
