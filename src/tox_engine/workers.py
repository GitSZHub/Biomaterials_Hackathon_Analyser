"""
QThread Workers for Tox Engine

All toxicology API calls must run off the main Qt thread to prevent UI freeze.
Each worker class:
  - Takes the relevant client and parameters in __init__
  - Runs the blocking call in run()
  - Emits result_ready(result) on success
  - Emits error_occurred(message) on failure
  - Emits progress(int, str) for multi-step operations

Usage in a tab widget:
    worker = ADMETWorker(admet_client, smiles="CC(=O)Oc1ccccc1C(=O)O")
    worker.result_ready.connect(self.on_admet_result)
    worker.error_occurred.connect(self.on_tox_error)
    worker.start()
"""

from PyQt6.QtCore import QThread, pyqtSignal
import logging

logger = logging.getLogger(__name__)


class ADMETWorker(QThread):
    """Runs ADMETClient.predict_admet() off the UI thread."""
    result_ready = pyqtSignal(object)    # emits ADMETResult
    error_occurred = pyqtSignal(str)

    def __init__(self, admet_client, smiles: str, parent=None):
        super().__init__(parent)
        self._client = admet_client
        self._smiles = smiles

    def run(self):
        try:
            result = self._client.predict_admet(self._smiles)
            self.result_ready.emit(result)
        except Exception as e:
            logger.exception("ADMETWorker error")
            self.error_occurred.emit(str(e))


class CompToxWorker(QThread):
    """Runs CompToxClient.lookup_by_name() or screen_material_components()."""
    result_ready = pyqtSignal(object)    # emits ChemicalHazardProfile or list
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, str)      # (percent, message)

    def __init__(self, comptox_client, components: list, parent=None):
        super().__init__(parent)
        self._client = comptox_client
        self._components = components

    def run(self):
        try:
            results = []
            total = len(self._components)
            for i, comp in enumerate(self._components):
                self.progress.emit(int((i / total) * 100), f"Looking up: {comp}")
                profile = self._client.lookup_by_name(comp)
                results.append(profile)
            self.progress.emit(100, "Complete")
            self.result_ready.emit(results)
        except Exception as e:
            logger.exception("CompToxWorker error")
            self.error_occurred.emit(str(e))


class AOPWorker(QThread):
    """Maps a list of components to their Adverse Outcome Pathways."""
    result_ready = pyqtSignal(object)   # emits dict[str, AOPMappingResult]
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, aop_client, components: list, parent=None):
        super().__init__(parent)
        self._client = aop_client
        self._components = components

    def run(self):
        try:
            results = {}
            total = len(self._components)
            for i, comp in enumerate(self._components):
                self.progress.emit(int((i / total) * 100), f"Mapping AOPs: {comp}")
                results[comp] = self._client.map_chemical_to_aops(comp)
            self.progress.emit(100, "Complete")
            self.result_ready.emit(results)
        except Exception as e:
            logger.exception("AOPWorker error")
            self.error_occurred.emit(str(e))


class ISO10993Worker(QThread):
    """Runs a full ISO 10993 assessment off-thread."""
    result_ready = pyqtSignal(object)   # emits ISO10993Assessment
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, assessor, material_name: str, contact_type: str,
                 contact_duration: str, components: list, parent=None):
        super().__init__(parent)
        self._assessor = assessor
        self._material_name = material_name
        self._contact_type = contact_type
        self._contact_duration = contact_duration
        self._components = components

    def run(self):
        try:
            self.progress.emit(10, "Starting ISO 10993 assessment...")
            result = self._assessor.assess(
                material_name=self._material_name,
                contact_type=self._contact_type,
                contact_duration=self._contact_duration,
                components=self._components,
            )
            self.progress.emit(100, "Assessment complete")
            self.result_ready.emit(result)
        except Exception as e:
            logger.exception("ISO10993Worker error")
            self.error_occurred.emit(str(e))


class BiocCompatScorerWorker(QThread):
    """Runs full biocompatibility scoring off-thread."""
    result_ready = pyqtSignal(object)   # emits BiocCompatScore
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, scorer, material_name: str, components: list,
                 drug_smiles=None, parent=None):
        super().__init__(parent)
        self._scorer = scorer
        self._material_name = material_name
        self._components = components
        self._drug_smiles = drug_smiles or []

    def run(self):
        try:
            self.progress.emit(10, "Scoring biocompatibility...")
            result = self._scorer.score_material(
                material_name=self._material_name,
                components=self._components,
                drug_smiles=self._drug_smiles or None,
            )
            self.progress.emit(100, "Scoring complete")
            self.result_ready.emit(result)
        except Exception as e:
            logger.exception("BiocCompatScorerWorker error")
            self.error_occurred.emit(str(e))


class ServerHealthWorker(QThread):
    """Polls all ToxMCP server health status for the status bar."""
    status_ready = pyqtSignal(dict)    # emits dict[server_name, bool]

    def __init__(self, server_manager, parent=None):
        super().__init__(parent)
        self._manager = server_manager

    def run(self):
        status = self._manager.get_status()
        self.status_ready.emit(status)
