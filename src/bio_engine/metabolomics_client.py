"""
Metabolomics Client — MetaboLights + Metabolomics Workbench dataset search.

Two public metabolomics repositories with REST APIs:
  1. MetaboLights (EMBL-EBI)  — https://www.ebi.ac.uk/metabolights/ws/
  2. Metabolomics Workbench (NIH) — https://www.metabolomicsworkbench.org/rest/

Both are free, no API key required.

Public API:
    client = MetabolomicsClient()
    results = client.search("hydrogel scaffold", source="both")
    detail  = client.get_study_detail("MTBLS1234")
    path    = client.download_study("MTBLS1234")

Caches metadata to SQLite via data_manager.crud.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── API endpoints ────────────────────────────────────────────────────────────

_MTBLS_BASE = "https://www.ebi.ac.uk/metabolights/ws"
_MW_BASE    = "https://www.metabolomicsworkbench.org/rest"

_DEFAULT_CACHE = Path(__file__).parent.parent.parent / "cache" / "metabolomics"
_RATE_DELAY = 0.5  # seconds between requests


class MetabolomicsClient:
    """
    Search and retrieve metabolomics datasets from MetaboLights and
    Metabolomics Workbench.

    Usage:
        client  = MetabolomicsClient()
        results = client.search("biomaterial scaffold osteoblast")
        for ds in results:
            print(ds["accession"], ds["title"], ds["platform"])
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._last = 0.0
        self.cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Public search ────────────────────────────────────────────────────────

    def search(self, query: str, source: str = "both",
               organism: str = "", max_results: int = 30) -> List[Dict]:
        """
        Search metabolomics repositories.

        Args:
            query:       free-text search terms
            source:      "metabolights" | "workbench" | "both"
            organism:    filter e.g. "Homo sapiens"
            max_results: cap on returned datasets per source

        Returns:
            List of dicts: accession, title, organism, tissue, platform,
            source, description, submission_date
        """
        results = []

        if source in ("metabolights", "both"):
            try:
                results.extend(self._search_metabolights(query, organism, max_results))
            except Exception as e:
                logger.warning(f"MetaboLights search failed: {e}")

        if source in ("workbench", "both"):
            try:
                results.extend(self._search_workbench(query, organism, max_results))
            except Exception as e:
                logger.warning(f"Metabolomics Workbench search failed: {e}")

        return results[:max_results]

    def get_study_detail(self, accession: str) -> Dict:
        """
        Fetch full metadata for one study by accession.
        Auto-detects source from accession prefix (MTBLS vs ST).
        """
        accession = accession.strip().upper()
        if accession.startswith("MTBLS"):
            return self._get_metabolights_detail(accession)
        elif accession.startswith("ST"):
            return self._get_workbench_detail(accession)
        else:
            logger.warning(f"Unknown accession format: {accession}")
            return {}

    def download_study(self, accession: str,
                       progress_callback=None) -> Optional[str]:
        """
        Download study data files to cache.
        Returns local directory path, or None on failure.
        """
        accession = accession.strip().upper()
        study_dir = self.cache_dir / accession
        study_dir.mkdir(parents=True, exist_ok=True)

        # Check if already cached (has at least one data file)
        existing = list(study_dir.glob("*"))
        if existing:
            logger.info(f"Using cached study: {study_dir}")
            return str(study_dir)

        if accession.startswith("MTBLS"):
            return self._download_metabolights(accession, study_dir, progress_callback)
        elif accession.startswith("ST"):
            return self._download_workbench(accession, study_dir, progress_callback)
        return None

    def list_cached_studies(self) -> List[str]:
        """Return accession IDs of locally cached studies."""
        if not self.cache_dir.exists():
            return []
        return [d.name for d in self.cache_dir.iterdir()
                if d.is_dir() and (d.name.startswith("MTBLS") or d.name.startswith("ST"))]

    def cache_metadata(self, datasets: List[Dict]) -> None:
        """Persist dataset metadata to local SQLite DB."""
        try:
            from data_manager.crud import upsert_metabolomics_dataset
            for ds in datasets:
                upsert_metabolomics_dataset(
                    source=ds.get("source", ""),
                    accession=ds.get("accession", ""),
                    title=ds.get("title", ""),
                    organism=ds.get("organism", ""),
                    tissue=ds.get("tissue", ""),
                    platform=ds.get("platform", ""),
                    culture_condition=ds.get("culture_condition", ""),
                )
        except Exception as e:
            logger.warning(f"Failed to cache metabolomics metadata: {e}")

    # ── MetaboLights ─────────────────────────────────────────────────────────

    def _search_metabolights(self, query: str, organism: str,
                             max_results: int) -> List[Dict]:
        """Search MetaboLights studies via REST API."""
        self._rate_limit()

        # MetaboLights search endpoint
        url = f"{_MTBLS_BASE}/studies"
        try:
            resp = requests.get(url, timeout=30, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"MetaboLights API error: {e}")
            return []

        # The /studies endpoint returns a list of study IDs
        # We need to filter by query terms
        study_ids = data if isinstance(data, list) else data.get("content", [])
        if not study_ids:
            return []

        query_lower = query.lower().split()
        organism_lower = organism.lower() if organism else ""

        results = []
        for study_id in study_ids[:max_results * 3]:  # overfetch then filter
            if len(results) >= max_results:
                break

            detail = self._get_metabolights_detail(study_id)
            if not detail:
                continue

            # Filter by query terms (check title + description)
            text = (detail.get("title", "") + " " + detail.get("description", "")).lower()
            if query_lower and not any(q in text for q in query_lower):
                continue

            # Filter by organism
            if organism_lower and organism_lower not in detail.get("organism", "").lower():
                continue

            results.append(detail)

        return results

    def _get_metabolights_detail(self, accession: str) -> Dict:
        """Fetch detail for one MetaboLights study."""
        self._rate_limit()
        url = f"{_MTBLS_BASE}/studies/{accession}"
        try:
            resp = requests.get(url, timeout=20, headers=self._headers())
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"MetaboLights detail failed for {accession}: {e}")
            return {}

        # Parse response
        study = data if not isinstance(data, dict) or "content" not in data else data
        title = study.get("title", "") or study.get("studyIdentifier", accession)
        description = study.get("description", "")

        # Extract organism from study organisms
        organisms = study.get("organism", [])
        if isinstance(organisms, list):
            org_str = ", ".join(
                o.get("organismName", "") if isinstance(o, dict) else str(o)
                for o in organisms
            )
        else:
            org_str = str(organisms)

        # Infer platform from assays
        platform = ""
        assays = study.get("assays", [])
        if isinstance(assays, list):
            techs = set()
            for a in assays:
                tech = ""
                if isinstance(a, dict):
                    tech = a.get("technology", "") or a.get("measurementTechnology", "")
                if tech:
                    techs.add(tech)
            platform = ", ".join(techs) if techs else ""

        tissue = self._infer_tissue(title + " " + description)

        return {
            "accession":       accession,
            "title":           title,
            "organism":        org_str,
            "tissue":          tissue,
            "platform":        platform or self._infer_platform(title + " " + description),
            "source":          "MetaboLights",
            "description":     description[:500],
            "submission_date": study.get("submissionDate", ""),
            "culture_condition": self._infer_culture(title + " " + description),
        }

    def _download_metabolights(self, accession: str, dest_dir: Path,
                               progress_callback=None) -> Optional[str]:
        """Download MetaboLights study files."""
        self._rate_limit()
        # List files in study
        url = f"{_MTBLS_BASE}/studies/{accession}/files"
        try:
            resp = requests.get(url, timeout=30, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"MetaboLights file listing failed: {e}")
            return None

        # Download data files (prioritise maf files = metabolite assignment)
        files = data if isinstance(data, list) else data.get("study", [])
        downloaded = 0
        for f in files:
            fname = f.get("file", "") if isinstance(f, dict) else str(f)
            if not fname:
                continue
            # Prioritise metabolite assignment files and sample metadata
            if any(ext in fname.lower() for ext in [".tsv", ".csv", ".txt", ".maf", ".mzml"]):
                file_url = f"{_MTBLS_BASE}/studies/{accession}/files/{fname}"
                local_path = dest_dir / Path(fname).name
                try:
                    self._download_file(file_url, local_path, progress_callback)
                    downloaded += 1
                    if downloaded >= 5:  # cap downloads
                        break
                except Exception as e:
                    logger.warning(f"Failed to download {fname}: {e}")

        if downloaded > 0:
            logger.info(f"Downloaded {downloaded} files for {accession}")
            return str(dest_dir)

        # Save metadata as fallback
        meta_path = dest_dir / "metadata.json"
        detail = self._get_metabolights_detail(accession)
        if detail:
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(detail, fh, indent=2)
            return str(dest_dir)

        return None

    # ── Metabolomics Workbench ───────────────────────────────────────────────

    def _search_workbench(self, query: str, organism: str,
                          max_results: int) -> List[Dict]:
        """
        Search Metabolomics Workbench via REST API.
        API docs: https://www.metabolomicsworkbench.org/tools/MWRestAPIv1.0.pdf
        """
        self._rate_limit()

        # Search by study title/summary
        # MW REST: /rest/study/study_title/{title}/summary
        url = f"{_MW_BASE}/study/study_title/{requests.utils.quote(query)}/summary"
        try:
            resp = requests.get(url, timeout=30, headers=self._headers())
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Metabolomics Workbench search failed: {e}")
            return []

        # Parse results
        studies = []
        if isinstance(data, dict):
            # Single result comes as dict, multiple as dict of dicts
            if "study_id" in data:
                studies = [data]
            else:
                studies = list(data.values()) if data else []
        elif isinstance(data, list):
            studies = data

        results = []
        organism_lower = organism.lower() if organism else ""

        for s in studies[:max_results]:
            if not isinstance(s, dict):
                continue
            org = s.get("subject_species", "") or s.get("species", "")
            if organism_lower and organism_lower not in org.lower():
                continue

            title = s.get("study_title", "") or s.get("title", "")
            summary = s.get("study_summary", "") or s.get("summary", "")
            study_id = s.get("study_id", "")

            results.append({
                "accession":       study_id,
                "title":           title,
                "organism":        org,
                "tissue":          self._infer_tissue(title + " " + summary),
                "platform":        s.get("analysis_type", "") or self._infer_platform(title + " " + summary),
                "source":          "Metabolomics Workbench",
                "description":     summary[:500],
                "submission_date": s.get("study_submission_date", ""),
                "culture_condition": self._infer_culture(title + " " + summary),
            })

        return results

    def _get_workbench_detail(self, accession: str) -> Dict:
        """Fetch detail for one Metabolomics Workbench study."""
        self._rate_limit()
        url = f"{_MW_BASE}/study/study_id/{accession}/summary"
        try:
            resp = requests.get(url, timeout=20, headers=self._headers())
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"MW detail failed for {accession}: {e}")
            return {}

        if not isinstance(data, dict):
            return {}

        # May be nested
        s = data
        if "1" in data:
            s = data["1"]
        elif accession in data:
            s = data[accession]

        title = s.get("study_title", "") or s.get("title", "")
        summary = s.get("study_summary", "") or s.get("summary", "")

        return {
            "accession":       accession,
            "title":           title,
            "organism":        s.get("subject_species", ""),
            "tissue":          self._infer_tissue(title + " " + summary),
            "platform":        s.get("analysis_type", "") or self._infer_platform(title + " " + summary),
            "source":          "Metabolomics Workbench",
            "description":     summary[:500],
            "submission_date": s.get("study_submission_date", ""),
            "institute":       s.get("institute", ""),
            "culture_condition": self._infer_culture(title + " " + summary),
        }

    def _download_workbench(self, accession: str, dest_dir: Path,
                            progress_callback=None) -> Optional[str]:
        """Download Metabolomics Workbench study data."""
        self._rate_limit()

        # Get metabolite data via REST
        # /rest/study/study_id/{id}/metabolites
        url = f"{_MW_BASE}/study/study_id/{accession}/metabolites"
        try:
            resp = requests.get(url, timeout=30, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

            # Save metabolite data
            out_path = dest_dir / f"{accession}_metabolites.json"
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

            if progress_callback:
                progress_callback(1, 2)

        except Exception as e:
            logger.warning(f"MW metabolite download failed for {accession}: {e}")

        # Get analysis results
        url2 = f"{_MW_BASE}/study/study_id/{accession}/analysis"
        try:
            resp2 = requests.get(url2, timeout=30, headers=self._headers())
            resp2.raise_for_status()
            data2 = resp2.json()

            out_path2 = dest_dir / f"{accession}_analysis.json"
            with open(out_path2, "w", encoding="utf-8") as fh:
                json.dump(data2, fh, indent=2)

            if progress_callback:
                progress_callback(2, 2)

        except Exception as e:
            logger.warning(f"MW analysis download failed for {accession}: {e}")

        # Save metadata
        detail = self._get_workbench_detail(accession)
        if detail:
            meta_path = dest_dir / "metadata.json"
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(detail, fh, indent=2)

        if list(dest_dir.glob("*")):
            return str(dest_dir)
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self._last
        if elapsed < _RATE_DELAY:
            time.sleep(_RATE_DELAY - elapsed)
        self._last = time.time()

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "User-Agent": "BioHackathonAnalyser/1.0",
            "Accept": "application/json",
        }

    def _download_file(self, url: str, dest: Path,
                       progress_callback=None) -> str:
        resp = requests.get(url, stream=True, timeout=120,
                            headers=self._headers())
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

    # ── Tissue / platform / culture inference ────────────────────────────────
    # Same pattern as GEOClient for consistency.

    _TISSUE_KEYWORDS = {
        "retina": ["retina", "RPE", "retinal pigment", "macular"],
        "cartilage": ["cartilage", "chondrocyte", "chondrogenic", "articular"],
        "bone": ["bone", "osteoblast", "osteogenic", "calvarial"],
        "cardiovascular": ["cardiac", "cardiomyocyte", "heart", "vascular"],
        "neural": ["neural", "neuron", "brain", "cortical"],
        "skin": ["skin", "keratinocyte", "fibroblast", "wound", "dermal"],
        "liver": ["hepat", "liver", "HepG2"],
        "kidney": ["kidney", "renal"],
        "pancreas": ["pancrea", "islet", "beta cell"],
        "intestine": ["intestin", "colon", "gut"],
        "lung": ["lung", "pulmonary", "alveolar"],
        "muscle": ["muscle", "skeletal muscle", "myocyte", "sarco"],
        "adipose": ["adipose", "adipocyte", "fat tissue"],
        "blood": ["plasma", "serum", "blood", "erythrocyte"],
        "urine": ["urine", "urinary"],
    }

    _PLATFORM_KEYWORDS = {
        "LC-MS":  ["lc-ms", "liquid chromatography", "orbitrap", "q-tof",
                    "hilic", "rp-lc", "uhplc", "hplc-ms"],
        "GC-MS":  ["gc-ms", "gas chromatography"],
        "NMR":    ["nmr", "nuclear magnetic resonance", "bruker"],
        "CE-MS":  ["ce-ms", "capillary electrophoresis"],
        "MALDI":  ["maldi", "matrix-assisted"],
        "HPLC-UV":["hplc-uv", "hplc-dad", "uv detection"],
    }

    _CULTURE_KEYWORDS = {
        "perfused": ["microfluidic", "organ-on-chip", "perfusion", "flow chamber"],
        "spinner": ["spinner", "orbital shaker", "rotating wall"],
        "3D": ["3d culture", "3d scaffold", "hydrogel", "organoid"],
        "static": ["static", "2D", "monolayer"],
    }

    def _infer_tissue(self, text: str) -> str:
        text_lower = text.lower()
        for tissue, kws in self._TISSUE_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in kws):
                return tissue
        return ""

    def _infer_platform(self, text: str) -> str:
        text_lower = text.lower()
        for platform, kws in self._PLATFORM_KEYWORDS.items():
            if any(kw in text_lower for kw in kws):
                return platform
        return ""

    def _infer_culture(self, text: str) -> str:
        text_lower = text.lower()
        for condition, kws in self._CULTURE_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in kws):
                return condition
        return "static"
