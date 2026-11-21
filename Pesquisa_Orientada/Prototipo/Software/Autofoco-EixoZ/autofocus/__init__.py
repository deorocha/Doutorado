"""Autofoco Z — pacote de módulos do scanner histológico."""
from .metrics import (
    METRICS, DISPLAY,
    metric_laplacian, metric_tenengrad, metric_brenner, metric_fft_hf,
    metric_mscg,
)

from .hardware import (
    MockZAxis, MockCamera, OpenCVCamera,
    ESP8266SerialZAxis, ESP8266WiFiZAxis,
    load_uploaded_image,
)

from .sweep import run_sweep, run_sweep_brent, run_sweep_dispatch

from .plotting import (
    make_fig, make_fig_per_metric, make_accuracy_fig,
    make_histogram_fig, make_histogram_comparison_fig,
    make_histogram_gallery_fig, make_table,
)

__all__ = [
    "METRICS", "DISPLAY",
    "metric_laplacian", "metric_tenengrad", "metric_brenner", "metric_fft_hf",
    "metric_mscg",
    "MockZAxis", "MockCamera", "OpenCVCamera",
    "ESP8266SerialZAxis", "ESP8266WiFiZAxis", "load_uploaded_image",
    "run_sweep", "run_sweep_brent", "run_sweep_dispatch",
    "make_fig", "make_fig_per_metric", "make_accuracy_fig",
    "make_histogram_fig", "make_histogram_comparison_fig",
    "make_histogram_gallery_fig", "make_table",
]
