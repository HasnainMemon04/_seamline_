"""Seamline (called FireBridge until 12 Nov 2026): a harmonised MODIS/VIIRS burning-activity calendar.

C08, NASA Space Apps 2026. Local research prototype; see docs/STATUS.md for what
is implemented, tested and validated, and docs/PROVENANCE.md for when and by whom
each part was made.

A FIRMS hotspot row is one fire-affected pixel seen on one satellite pass. It is
not one fire and not burned area. Everything in this package counts "detected
burning activity" and keeps the satellite of origin on every number.
"""

__version__ = "0.2.0"
