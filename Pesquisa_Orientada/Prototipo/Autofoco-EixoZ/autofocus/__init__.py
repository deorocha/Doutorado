"""Autofoco Z — pacote de módulos do scanner histológico."""
from .metrics import (
    METRICS, DISPLAY,
    metric_laplacian, metric_tenengrad, metric_brenner, metric_fft_hf,
)
from .hardware import (
    MockZAxis, MockCamera, OpenCVCamera,
    ESP8266SerialZAxis, ESP8266WiFiZAxis,
    load_uploaded_image,
)
from .sweep import run_sweep
from .plotting import (
    make_fig, make_fig_per_metric, make_accuracy_fig,
    make_histogram_fig, make_histogram_comparison_fig,
    make_histogram_gallery_fig, make_table,
)

__all__ = [
    "METRICS", "DISPLAY",
    "metric_laplacian", "metric_tenengrad", "metric_brenner", "metric_fft_hf",
    "MockZAxis", "MockCamera", "OpenCVCamera",
    "ESP8266SerialZAxis", "ESP8266WiFiZAxis", "load_uploaded_image",
    "run_sweep",
    "make_fig", "make_fig_per_metric", "make_accuracy_fig",
    "make_histogram_fig", "make_histogram_comparison_fig",
    "make_histogram_gallery_fig", "make_table",
]
