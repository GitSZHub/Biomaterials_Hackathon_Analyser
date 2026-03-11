"""
Flow Cytometry Data Processor — FCS file import, gating, population statistics.

Handles standard Flow Cytometry Standard (FCS) files and provides
basic analytical tools relevant to biomaterials evaluation:
  - Viability gating (live/dead)
  - Surface marker analysis
  - Population statistics
  - Scatter plots and histograms

Public API:
    from bio_engine.flow_data_processor import (
        load_fcs,
        gate_polygon,
        gate_threshold,
        compute_population_stats,
        FlowData,
        GatingResult,
    )

    data = load_fcs("sample.fcs")
    gated = gate_threshold(data, channel="FSC-A", threshold=50000, keep="above")
    stats = compute_population_stats(gated)

FCS parsing uses a built-in reader (no fcsparser dependency required),
but will use fcsparser/flowio if available for better compatibility.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class FlowData:
    """Parsed flow cytometry data."""
    events:         pd.DataFrame        # rows = events, cols = channels
    channels:       List[str]           # channel names (e.g. FSC-A, SSC-A, FITC-A)
    markers:        Dict[str, str]      # channel -> marker name (e.g. FITC-A -> CD45)
    n_events:       int = 0
    metadata:       Dict[str, str] = field(default_factory=dict)
    filename:       str = ""
    compensated:    bool = False
    error:          Optional[str] = None


@dataclass
class GatingResult:
    """Result of a gating operation."""
    data:           FlowData            # gated data (events passing the gate)
    parent_events:  int                 # events in parent population
    gated_events:   int                 # events passing the gate
    pct:            float               # percentage gated
    gate_name:      str = ""
    gate_type:      str = ""            # "threshold" | "polygon" | "range"


@dataclass
class PopulationStats:
    """Statistics for a flow cytometry population."""
    n_events:       int
    channel_stats:  Dict[str, Dict[str, float]]   # channel -> {mean, median, cv, std, min, max}
    positive_pcts:  Dict[str, float] = field(default_factory=dict)  # marker -> % positive


# ── FCS file loading ─────────────────────────────────────────────────────────

def load_fcs(file_path: str) -> FlowData:
    """
    Load an FCS file (.fcs) and return structured FlowData.

    Tries external libraries first (fcsparser, flowio), falls back
    to built-in FCS 3.0/3.1 reader.
    """
    path = Path(file_path)
    if not path.exists():
        return FlowData(
            events=pd.DataFrame(), channels=[], markers={},
            error=f"File not found: {file_path}"
        )

    # Try fcsparser first
    try:
        import fcsparser
        meta, data = fcsparser.parse(str(path), reformat_meta=True)
        channels = list(data.columns)
        markers = {}
        for i, ch in enumerate(channels, 1):
            marker_key = f"$P{i}S"
            if marker_key in meta:
                markers[ch] = meta[marker_key]
        return FlowData(
            events=data,
            channels=channels,
            markers=markers,
            n_events=len(data),
            metadata={k: str(v) for k, v in meta.items() if isinstance(k, str)},
            filename=path.name,
        )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"fcsparser failed, trying built-in reader: {e}")

    # Try flowio
    try:
        import flowio
        fcs = flowio.FlowData(str(path))
        n_channels = int(fcs.channel_count)
        raw = np.reshape(fcs.events, (-1, n_channels))
        channels = []
        markers = {}
        for i in range(1, n_channels + 1):
            ch_name = fcs.channels.get(str(i), {}).get("PnN", f"Ch{i}")
            channels.append(ch_name)
            marker = fcs.channels.get(str(i), {}).get("PnS", "")
            if marker:
                markers[ch_name] = marker
        df = pd.DataFrame(raw, columns=channels)
        return FlowData(
            events=df,
            channels=channels,
            markers=markers,
            n_events=len(df),
            filename=path.name,
        )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"flowio failed, trying built-in reader: {e}")

    # Built-in FCS reader
    return _read_fcs_builtin(path)


def _read_fcs_builtin(path: Path) -> FlowData:
    """
    Minimal FCS 3.0/3.1 file reader. Handles most standard FCS files.
    Supports float (F) and double (D) data types in list mode.
    """
    try:
        with open(path, "rb") as fh:
            # Header segment (first 58 bytes)
            header = fh.read(58)
            if len(header) < 58:
                return FlowData(events=pd.DataFrame(), channels=[], markers={},
                                error="File too small for FCS format")

            version = header[:6].decode("ascii", errors="replace").strip()
            if not version.startswith("FCS"):
                return FlowData(events=pd.DataFrame(), channels=[], markers={},
                                error=f"Not an FCS file (version: {version})")

            # Parse header offsets
            text_start = int(header[10:18].decode().strip())
            text_end = int(header[18:26].decode().strip())
            data_start = int(header[26:34].decode().strip())
            data_end = int(header[34:42].decode().strip())

            # Read TEXT segment
            fh.seek(text_start)
            text_raw = fh.read(text_end - text_start + 1)
            text = text_raw.decode("ascii", errors="replace")

            # Parse key-value pairs
            delimiter = text[0]
            parts = text[1:].split(delimiter)
            meta = {}
            for i in range(0, len(parts) - 1, 2):
                key = parts[i].strip()
                val = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if key:
                    meta[key] = val

            n_params = int(meta.get("$PAR", "0"))
            n_events_total = int(meta.get("$TOT", "0"))
            datatype = meta.get("$DATATYPE", "F").upper()
            byteord = meta.get("$BYTEORD", "1,2,3,4")

            # Channel names and markers
            channels = []
            markers = {}
            for i in range(1, n_params + 1):
                ch = meta.get(f"$P{i}N", f"P{i}")
                channels.append(ch)
                marker = meta.get(f"$P{i}S", "")
                if marker:
                    markers[ch] = marker

            # Byte order
            if "4,3,2,1" in byteord:
                endian = ">"
            else:
                endian = "<"

            # Read DATA segment
            if data_start == 0:
                # Data offset might be in TEXT segment
                data_start = int(meta.get("$BEGINDATA", "0"))
                data_end = int(meta.get("$ENDDATA", "0"))

            if data_start == 0 or data_end == 0:
                return FlowData(events=pd.DataFrame(), channels=channels,
                                markers=markers, error="Cannot locate data segment")

            fh.seek(data_start)
            data_bytes = fh.read(data_end - data_start + 1)

            if datatype == "F":
                dtype = np.dtype(f"{endian}f4")
            elif datatype == "D":
                dtype = np.dtype(f"{endian}f8")
            elif datatype == "I":
                # Integer — need per-parameter bit widths
                # Simplified: assume 16-bit
                dtype = np.dtype(f"{endian}u2")
            else:
                return FlowData(events=pd.DataFrame(), channels=channels,
                                markers=markers,
                                error=f"Unsupported data type: {datatype}")

            raw = np.frombuffer(data_bytes, dtype=dtype)
            if n_params > 0:
                n_events = len(raw) // n_params
                raw = raw[:n_events * n_params].reshape(n_events, n_params)
            else:
                return FlowData(events=pd.DataFrame(), channels=channels,
                                markers=markers, error="No parameters defined")

            df = pd.DataFrame(raw, columns=channels[:n_params])

            return FlowData(
                events=df,
                channels=channels[:n_params],
                markers=markers,
                n_events=len(df),
                metadata=meta,
                filename=path.name,
            )

    except Exception as e:
        return FlowData(events=pd.DataFrame(), channels=[], markers={},
                        error=f"FCS read failed: {e}")


# ── Gating operations ────────────────────────────────────────────────────────

def gate_threshold(
    data: FlowData,
    channel: str,
    threshold: float,
    keep: str = "above",
    gate_name: str = "",
) -> GatingResult:
    """
    Simple threshold gate on a single channel.

    Args:
        data:      FlowData to gate
        channel:   channel name (e.g. "FSC-A", "FITC-A")
        threshold: cutoff value
        keep:      "above" or "below"
        gate_name: optional label for the gate

    Returns:
        GatingResult with gated FlowData.
    """
    if channel not in data.events.columns:
        return GatingResult(
            data=FlowData(events=pd.DataFrame(), channels=data.channels,
                          markers=data.markers, error=f"Channel {channel} not found"),
            parent_events=data.n_events, gated_events=0, pct=0.0,
            gate_name=gate_name, gate_type="threshold",
        )

    values = data.events[channel]
    if keep == "above":
        mask = values >= threshold
    else:
        mask = values < threshold

    gated_df = data.events[mask].reset_index(drop=True)
    n_gated = len(gated_df)
    pct = (n_gated / data.n_events * 100) if data.n_events > 0 else 0.0

    return GatingResult(
        data=FlowData(
            events=gated_df,
            channels=data.channels,
            markers=data.markers,
            n_events=n_gated,
            metadata=data.metadata,
            filename=data.filename,
        ),
        parent_events=data.n_events,
        gated_events=n_gated,
        pct=round(pct, 2),
        gate_name=gate_name or f"{channel} {'>' if keep == 'above' else '<'} {threshold}",
        gate_type="threshold",
    )


def gate_range(
    data: FlowData,
    channel: str,
    low: float,
    high: float,
    gate_name: str = "",
) -> GatingResult:
    """Gate events within a range on a single channel."""
    if channel not in data.events.columns:
        return GatingResult(
            data=FlowData(events=pd.DataFrame(), channels=data.channels,
                          markers=data.markers, error=f"Channel {channel} not found"),
            parent_events=data.n_events, gated_events=0, pct=0.0,
            gate_name=gate_name, gate_type="range",
        )

    values = data.events[channel]
    mask = (values >= low) & (values <= high)
    gated_df = data.events[mask].reset_index(drop=True)
    n_gated = len(gated_df)
    pct = (n_gated / data.n_events * 100) if data.n_events > 0 else 0.0

    return GatingResult(
        data=FlowData(
            events=gated_df, channels=data.channels, markers=data.markers,
            n_events=n_gated, metadata=data.metadata, filename=data.filename,
        ),
        parent_events=data.n_events, gated_events=n_gated,
        pct=round(pct, 2),
        gate_name=gate_name or f"{low} <= {channel} <= {high}",
        gate_type="range",
    )


def gate_polygon(
    data: FlowData,
    channel_x: str,
    channel_y: str,
    vertices: List[Tuple[float, float]],
    gate_name: str = "",
) -> GatingResult:
    """
    2D polygon gate.

    Args:
        data:       FlowData
        channel_x:  X-axis channel
        channel_y:  Y-axis channel
        vertices:   list of (x, y) polygon vertices (closed automatically)
        gate_name:  optional label

    Returns:
        GatingResult with events inside the polygon.
    """
    if channel_x not in data.events.columns or channel_y not in data.events.columns:
        return GatingResult(
            data=FlowData(events=pd.DataFrame(), channels=data.channels,
                          markers=data.markers, error="Channel(s) not found"),
            parent_events=data.n_events, gated_events=0, pct=0.0,
            gate_name=gate_name, gate_type="polygon",
        )

    x = data.events[channel_x].values
    y = data.events[channel_y].values
    mask = _point_in_polygon(x, y, vertices)

    gated_df = data.events[mask].reset_index(drop=True)
    n_gated = len(gated_df)
    pct = (n_gated / data.n_events * 100) if data.n_events > 0 else 0.0

    return GatingResult(
        data=FlowData(
            events=gated_df, channels=data.channels, markers=data.markers,
            n_events=n_gated, metadata=data.metadata, filename=data.filename,
        ),
        parent_events=data.n_events, gated_events=n_gated,
        pct=round(pct, 2),
        gate_name=gate_name or f"Polygon({channel_x},{channel_y})",
        gate_type="polygon",
    )


# ── Population statistics ────────────────────────────────────────────────────

def compute_population_stats(
    data: FlowData,
    positive_thresholds: Optional[Dict[str, float]] = None,
) -> PopulationStats:
    """
    Compute statistics for each channel in a flow population.

    Args:
        data:                FlowData (possibly gated)
        positive_thresholds: dict of channel -> threshold for % positive calculation

    Returns:
        PopulationStats with per-channel mean, median, CV, std, min, max.
    """
    if data.events.empty:
        return PopulationStats(n_events=0, channel_stats={})

    stats = {}
    positive_pcts = {}

    for ch in data.channels:
        if ch not in data.events.columns:
            continue
        vals = data.events[ch].values
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        cv = (std / mean * 100) if mean != 0 else 0.0

        stats[ch] = {
            "mean": round(mean, 2),
            "median": round(float(np.median(vals)), 2),
            "std": round(std, 2),
            "cv": round(cv, 2),
            "min": round(float(np.min(vals)), 2),
            "max": round(float(np.max(vals)), 2),
        }

        if positive_thresholds and ch in positive_thresholds:
            n_pos = np.sum(vals >= positive_thresholds[ch])
            pct_pos = (n_pos / len(vals) * 100) if len(vals) > 0 else 0.0
            positive_pcts[ch] = round(float(pct_pos), 2)

    return PopulationStats(
        n_events=data.n_events,
        channel_stats=stats,
        positive_pcts=positive_pcts,
    )


# ── Biomaterial-relevant panel templates ─────────────────────────────────────

PANEL_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "Viability": {
        "markers": ["Live/Dead", "Annexin V", "PI"],
        "description": "Basic viability assessment for cytotoxicity screening",
    },
    "MSC Immunophenotyping": {
        "markers": ["CD90", "CD105", "CD73", "CD45", "CD34", "CD14", "CD19", "HLA-DR"],
        "description": "ISCT minimal criteria for MSC identity (CD90+/CD105+/CD73+/CD45-/CD34-)",
    },
    "Integrin Panel": {
        "markers": ["CD49e (alpha5)", "CD49f (alpha6)", "CD49b (alpha2)", "CD51 (alphaV)",
                     "CD29 (beta1)", "CD61 (beta3)"],
        "description": "Cell-material adhesion receptors",
    },
    "Inflammation Panel": {
        "markers": ["CD68", "CD163", "CD206", "CD80", "CD86", "HLA-DR"],
        "description": "M1/M2 macrophage polarisation assessment",
    },
    "Cell Cycle": {
        "markers": ["PI (DNA)", "BrdU/EdU", "Ki-67"],
        "description": "Proliferation and cell cycle phase analysis",
    },
    "ROS Detection": {
        "markers": ["DCFH-DA", "CellROX", "MitoSOX"],
        "description": "Reactive oxygen species measurement",
    },
    "Phospho-flow": {
        "markers": ["pFAK (Y397)", "pYAP (S127)", "pSmad2/3", "pERK1/2", "pAKT"],
        "description": "Mechanosensing and signalling pathway activation",
    },
    "Endothelial": {
        "markers": ["CD31", "CD34", "VE-cadherin", "CD144", "VEGFR2"],
        "description": "Endothelial cell identification and angiogenesis assessment",
    },
}


# ── Demo data generator ──────────────────────────────────────────────────────

def make_demo_flow_data(
    n_events: int = 5000,
    seed: int = 42,
) -> FlowData:
    """Generate synthetic flow cytometry data for UI testing."""
    rng = np.random.default_rng(seed)

    # Scatter channels
    fsc = rng.lognormal(mean=11, sigma=0.4, size=n_events)
    ssc = rng.lognormal(mean=10, sigma=0.5, size=n_events)

    # Fluorescence channels — simulate two populations
    n_pos = int(n_events * 0.3)
    n_neg = n_events - n_pos

    fitc = np.concatenate([
        rng.lognormal(mean=4, sigma=0.5, size=n_neg),   # negative
        rng.lognormal(mean=8, sigma=0.3, size=n_pos),   # positive
    ])
    pe = np.concatenate([
        rng.lognormal(mean=5, sigma=0.4, size=n_neg),
        rng.lognormal(mean=9, sigma=0.4, size=n_pos),
    ])
    apc = rng.lognormal(mean=6, sigma=0.6, size=n_events)

    # Viability: ~90% live
    n_dead = int(n_events * 0.1)
    viability = np.concatenate([
        rng.lognormal(mean=3, sigma=0.3, size=n_events - n_dead),  # live (low)
        rng.lognormal(mean=8, sigma=0.2, size=n_dead),             # dead (high)
    ])

    # Shuffle all channels consistently
    idx = rng.permutation(n_events)
    df = pd.DataFrame({
        "FSC-A": fsc[idx],
        "SSC-A": ssc[idx],
        "FITC-A": fitc[idx],
        "PE-A": pe[idx],
        "APC-A": apc[idx],
        "Live/Dead": viability[idx],
    })

    return FlowData(
        events=df,
        channels=list(df.columns),
        markers={
            "FITC-A": "CD90",
            "PE-A": "CD105",
            "APC-A": "CD45",
            "Live/Dead": "Viability",
        },
        n_events=n_events,
        filename="demo_flow.fcs",
    )


# ── Internal helpers ─────────────────────────────────────────────────────────

def _point_in_polygon(
    x: np.ndarray, y: np.ndarray,
    vertices: List[Tuple[float, float]],
) -> np.ndarray:
    """Ray-casting algorithm for point-in-polygon test (vectorised)."""
    n_pts = len(x)
    n_verts = len(vertices)
    inside = np.zeros(n_pts, dtype=bool)

    vx = np.array([v[0] for v in vertices])
    vy = np.array([v[1] for v in vertices])

    j = n_verts - 1
    for i in range(n_verts):
        cond = ((vy[i] > y) != (vy[j] > y)) & \
               (x < (vx[j] - vx[i]) * (y - vy[i]) / (vy[j] - vy[i] + 1e-30) + vx[i])
        inside = inside ^ cond
        j = i

    return inside
