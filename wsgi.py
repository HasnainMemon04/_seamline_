"""Deployment entry point, created during packaging; source application predates this release."""
from c08.app import app, _params
from c08 import analysis
# Fail startup on missing data instead of reporting a healthy but unusable app.
analysis.detections()
analysis.analyse(**_params({'region': 'Punjab', 'month': [2025, 11]}))
app.add_url_rule('/healthz', 'deployment_health', lambda: {'status': 'ready', 'mode': 'cached-research-demo'})
