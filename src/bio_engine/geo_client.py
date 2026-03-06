"""
GEO Client — Gene Expression Omnibus dataset search and metadata retrieval.

Uses NCBI E-utilities (same API as PubMed, db=gds for GEO DataSets).
No API key required for basic use; NCBI_API_KEY in config raises rate limit
from 3 to 10 requests/second.

Public API:
    client = GEOClient()
    datasets = client.search("GelMA hydrogel RPE retina")
    detail   = client.get_dataset_detail("GSE123456")
    series   = client.get_series_list(datasets)   # list of GSE IDs

Caches metadata to SQLite via data_manager.crud.upsert_geo_dataset().
Full data download (HDF5) is out of scope for day-one hackathon build
but the download_series() stub is present for post-hackathon completion.
"""

from __future__ import annotations

import gzip
import logging
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BASE     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_SEARCH   = _BASE + "esearch.fcgi"
_SUMMARY  = _BASE + "esummary.fcgi"
_FETCH    = _BASE + "efetch.fcgi"

_RATE_DELAY = 0.34   # seconds — NCBI limit: 3 req/s without key
_GEO_FTP    = "https://ftp.ncbi.nlm.nih.gov/geo/series"
_DEFAULT_CACHE = Path(__file__).parent.parent.parent / "cache" / "geo"


class GEOClient:
    """
    Search GEO DataSets and retrieve metadata via NCBI E-utilities.

    Usage:
        client   = GEOClient()
        datasets = client.search("GelMA scaffold RPE", max_results=20)
        for ds in datasets:
            print(ds["gse_id"], ds["title"])
    """

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None,
                 cache_dir: Optional[str] = None):
        self._last = 0.0
        self._key  = api_key  or self._load_key()
        self._email= email    or self._load_email()
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Public search ─────────────────────────────────────────────────────────

    def search(self, query: str,
               max_results: int = 30,
               organism: str = "",
               experiment_type: str = "",
               year_from: Optional[int] = None) -> List[Dict]:
        """
        Search GEO DataSets, return list of metadata dicts.

        Args:
            query:           free-text search (biomaterial + tissue + assay)
            max_results:     cap on returned datasets
            organism:        filter e.g. "Homo sapiens", "Mus musculus"
            experiment_type: filter e.g. "Expression profiling by high throughput sequencing"
            year_from:       restrict to datasets published from this year

        Returns:
            List of dicts with keys: gse_id, title, organism, tissue,
            experiment_type, sample_count, summary, pubmed_ids
        """
        full_query = query
        if organism:
            full_query += f' AND "{organism}"[Organism]'
        if experiment_type:
            full_query += f' AND "{experiment_type}"[DataSet Type]'
        if year_from:
            full_query += f' AND {year_from}:3000[PDAT]'

        logger.info(f"GEO search: {full_query!r}")
        uids = self._esearch(full_query, max_results)
        if not uids:
            return []

        return self._esummary(uids)

    def get_dataset_detail(self, gse_id: str) -> Dict:
        """
        Fetch full metadata for one GEO Series by accession (e.g. 'GSE123456').
        Returns the same dict structure as search(), or empty dict on failure.
        """
        # Convert GSE accession to numeric GDS uid via search
        uids = self._esearch(f"{gse_id}[Accession]", max_results=1)
        if not uids:
            return {}
        results = self._esummary(uids)
        return results[0] if results else {}

    def get_series_list(self, datasets: List[Dict]) -> List[str]:
        """Extract GSE IDs from a search result list."""
        return [d["gse_id"] for d in datasets if d.get("gse_id")]

    def cache_metadata(self, datasets: List[Dict]) -> None:
        """Persist dataset metadata to local SQLite DB."""
        try:
            from data_manager.crud import upsert_geo_dataset
            for ds in datasets:
                upsert_geo_dataset(
                    gse_id         = ds["gse_id"],
                    title          = ds.get("title", ""),
                    organism       = ds.get("organism", ""),
                    tissue         = ds.get("tissue", ""),
                    experiment_type= ds.get("experiment_type", ""),
                    culture_condition = ds.get("culture_condition"),
                )
        except Exception as e:
            logger.warning(f"Failed to cache GEO metadata: {e}")

    def download_series(self, gse_id: str, out_dir: Optional[str] = None,
                        progress_callback=None) -> Optional[str]:
        """
        Download Series Matrix file (.txt.gz) for a GSE accession.
        Uses cached file if already downloaded.
        progress_callback(bytes_done, bytes_total) is called during download.
        Returns local file path, or None on failure.
        """
        gse_id = gse_id.strip().upper()
        cache = Path(out_dir) if out_dir else self.cache_dir
        cache.mkdir(parents=True, exist_ok=True)
        local_path = cache / f"{gse_id}_series_matrix.txt.gz"

        if local_path.exists():
            logger.info(f"Using cached series matrix: {local_path}")
            return str(local_path)

        prefix = self._geo_prefix(gse_id)
        url = f"{_GEO_FTP}/{prefix}/{gse_id}/matrix/{gse_id}_series_matrix.txt.gz"
        logger.info(f"Downloading series matrix: {url}")

        try:
            return self._download_file(url, local_path, progress_callback)
        except Exception as e:
            # Some datasets have multiple matrix files; try the -1 suffix
            url2 = url.replace("_series_matrix.txt.gz", "_series_matrix-1.txt.gz")
            logger.warning(f"Primary URL failed ({e}), trying {url2}")
            try:
                return self._download_file(url2, local_path, progress_callback)
            except Exception as e2:
                logger.error(f"Series matrix download failed for {gse_id}: {e2}")
                return None

    def is_downloaded(self, gse_id: str) -> bool:
        """Return True if the series matrix is already in the cache."""
        path = self.cache_dir / f"{gse_id.upper()}_series_matrix.txt.gz"
        return path.exists()

    def get_local_path(self, gse_id: str) -> Optional[str]:
        """Return cached file path or None."""
        path = self.cache_dir / f"{gse_id.upper()}_series_matrix.txt.gz"
        return str(path) if path.exists() else None

    # ── Download helper ───────────────────────────────────────────────────────

    def _download_file(self, url: str, dest: Path,
                       progress_callback=None) -> str:
        """Stream download url → dest; call progress_callback(done, total) if given."""
        resp = requests.get(url, stream=True, timeout=120,
                            headers={"User-Agent": "BioHackathonAnalyser/1.0"})
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
                    done += len(chunk)
                    if progress_callback:
                        progress_callback(done, total)
        return str(dest)

    @staticmethod
    def _geo_prefix(gse_id: str) -> str:
        """GSE12345 → GSE12nnn (NCBI FTP directory naming convention)."""
        num = gse_id[3:]   # strip "GSE"
        if len(num) <= 3:
            return "GSEnnn"
        return "GSE" + num[:-3] + "nnn"

    # ── E-utilities internals ─────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self._last
        if elapsed < _RATE_DELAY:
            time.sleep(_RATE_DELAY - elapsed)
        self._last = time.time()

    def _params(self, extra: dict) -> dict:
        p = {"retmode": "xml", "db": "gds"}
        if self._key:
            p["api_key"] = self._key
        if self._email:
            p["email"] = self._email
        p.update(extra)
        return p

    def _esearch(self, query: str, max_results: int) -> List[str]:
        """Return list of GDS UIDs matching query."""
        self._rate_limit()
        try:
            resp = requests.get(_SEARCH, params=self._params({
                "term":   query,
                "retmax": max_results,
                "sort":   "relevance",
            }), timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            id_list = root.find("IdList")
            if id_list is None:
                return []
            return [el.text for el in id_list.findall("Id") if el.text]
        except Exception as e:
            logger.error(f"GEO esearch failed: {e}")
            return []

    def _esummary(self, uids: List[str]) -> List[Dict]:
        """Fetch summary records for a list of GDS UIDs."""
        self._rate_limit()
        try:
            resp = requests.get(_SUMMARY, params=self._params({
                "id": ",".join(uids),
            }), timeout=30)
            resp.raise_for_status()
            return self._parse_esummary(resp.text)
        except Exception as e:
            logger.error(f"GEO esummary failed: {e}")
            return []

    def _parse_esummary(self, xml_text: str) -> List[Dict]:
        """Parse DocSumSet XML from GEO esummary."""
        datasets = []
        try:
            root = ET.fromstring(xml_text)
            for doc in root.findall(".//DocSum"):
                ds = self._extract_docsum(doc)
                if ds:
                    datasets.append(ds)
        except ET.ParseError as e:
            logger.error(f"XML parse error in GEO esummary: {e}")
        return datasets

    def _extract_docsum(self, doc) -> Optional[Dict]:
        """Extract fields from one GEO DocSum element."""
        def _item(name: str) -> str:
            el = doc.find(f".//Item[@Name='{name}']")
            return el.text.strip() if el is not None and el.text else ""

        gse = _item("Accession")
        if not gse.startswith("GSE"):
            return None   # skip non-series records (GPL, GDS subtypes)

        # Sample count
        n_samples = 0
        n_el = doc.find(".//Item[@Name='n_samples']")
        if n_el is not None and n_el.text:
            try:
                n_samples = int(n_el.text)
            except ValueError:
                pass

        # PubMed IDs linked to this dataset
        pubmed_ids = []
        for pm in doc.findall(".//Item[@Name='PubMedIds']/Item"):
            if pm.text:
                pubmed_ids.append(pm.text.strip())

        # Infer tissue from title + summary (rough heuristic)
        title   = _item("title")
        summary = _item("summary")
        tissue  = self._infer_tissue(title + " " + summary)

        return {
            "gse_id":          gse,
            "title":           title,
            "organism":        _item("taxon"),
            "tissue":          tissue,
            "experiment_type": _item("gdsType"),
            "sample_count":    n_samples,
            "summary":         summary[:500] if summary else "",
            "pubmed_ids":      pubmed_ids,
            "culture_condition": self._infer_culture(title + " " + summary),
        }

    # ── Heuristic tissue/culture inference ───────────────────────────────────

    _TISSUE_KEYWORDS = {
        "retina": ["retina", "RPE", "retinal pigment", "photoreceptor", "macular"],
        "cartilage": ["cartilage", "chondrocyte", "chondrogenic", "articular"],
        "bone": ["bone", "osteoblast", "osteogenic", "calvarial", "MSC"],
        "cardiovascular": ["cardiac", "cardiomyocyte", "heart", "myocardium", "vascular"],
        "neural": ["neural", "neuron", "spinal cord", "brain", "cortical", "astrocyte"],
        "skin": ["skin", "keratinocyte", "fibroblast", "wound healing", "dermal"],
        "liver": ["hepat", "liver", "HepG2", "hepatocyte"],
        "kidney": ["kidney", "renal", "tubular"],
        "pancreas": ["pancrea", "islet", "beta cell", "insulin"],
        "intestine": ["intestin", "colon", "enteroid", "organoid gut"],
        "lung": ["lung", "pulmonary", "alveolar", "airway"],
    }

    _CULTURE_KEYWORDS = {
        "perfused": ["microfluidic", "organ-on-chip", "perfusion", "flow chamber"],
        "spinner": ["spinner", "orbital shaker", "rotating wall"],
        "static":  ["static", "2D", "monolayer"],
    }

    def _infer_tissue(self, text: str) -> str:
        text_lower = text.lower()
        for tissue, keywords in self._TISSUE_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                return tissue
        return ""

    def _infer_culture(self, text: str) -> str:
        text_lower = text.lower()
        for condition, keywords in self._CULTURE_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                return condition
        return "static"

    # ── Config helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _load_key() -> Optional[str]:
        import os
        val = os.getenv("NCBI_API_KEY")
        if val:
            return val
        try:
            from utils.config import config
            return config.ncbi_api_key or None
        except Exception:
            return None

    @staticmethod
    def _load_email() -> Optional[str]:
        import os
        val = os.getenv("NCBI_EMAIL")
        if val:
            return val
        try:
            from utils.config import config
            return config.ncbi_email or None
        except Exception:
            return None
