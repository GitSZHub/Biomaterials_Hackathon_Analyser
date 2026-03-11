"""
Experimental Engine
===================
Cell/organism model knowledge bases, DBTL cycle tracker,
and experimental roadmap designer.
"""

from .cell_models_db import (
    CellModel,
    ALL_CELL_MODELS,
    get_models_for_tissue as get_cell_models_for_tissue,
    get_iso10993_models as get_iso10993_cell_models,
    get_model as get_cell_model,
    search_models as search_cell_models,
    list_tissues as list_cell_tissues,
)
from .organism_models_db import (
    OrganismModel,
    ALL_ORGANISM_MODELS,
    get_models_for_tissue as get_organism_models_for_tissue,
    get_iso10993_models as get_iso10993_organism_models,
    get_small_animal_models,
    get_large_animal_models,
    get_alternatives,
    get_model as get_organism_model,
)
from .experimental_designer import ExperimentalDesigner, ExperimentalRoadmap, RoadmapStage
from .dbtl_tracker import DBTLTracker, DBTLCycle
from .assay_recommender import (
    recommend_assays, AssayRecommendation, AssayStack,
    ASSAY_DATABASE, get_assays_for_question, get_assays_by_category, get_assays_by_tier,
)
from .microscopy_advisor import (
    recommend_technique, MicroscopyRecommendation, MicroscopyReport,
    TECHNIQUE_DATABASE, IMAGE_DATABASES, get_techniques_for_question, get_sample_prep,
)
from .proteomics_client import (
    ProteomicsClient, PPIEdge, PPINetwork,
    recommend_workflow, ProtWorkflowRec, PRIDEDataset,
    classify_corona, get_integrin_ligands,
    PROTEOMICS_TYPES, CORONA_PROTEINS, MATRISOME_CATEGORIES, INTEGRIN_LIGANDS,
)
from .flow_cytometry_advisor import (
    recommend_panel, design_panel, PanelRecommendation, PanelDesign, MarkerSpec,
    TECHNIQUE_VARIANTS, FLUOROCHROME_DB, APPLICATION_KB, FLOW_REPOSITORIES,
    get_panels_for_question,
)
from .protocol_client import (
    search_protocols, get_protocol_by_id, get_protocols_for_assay,
    list_local_protocols, Protocol, ProtocolSearchResult,
)

__all__ = [
    "CellModel", "ALL_CELL_MODELS",
    "get_cell_models_for_tissue", "get_iso10993_cell_models",
    "get_cell_model", "search_cell_models", "list_cell_tissues",
    "OrganismModel", "ALL_ORGANISM_MODELS",
    "get_organism_models_for_tissue", "get_iso10993_organism_models",
    "get_small_animal_models", "get_large_animal_models",
    "get_alternatives", "get_organism_model",
    "ExperimentalDesigner", "ExperimentalRoadmap", "RoadmapStage",
    "DBTLTracker", "DBTLCycle",
    # Assay Recommender
    "recommend_assays", "AssayRecommendation", "AssayStack",
    "ASSAY_DATABASE", "get_assays_for_question", "get_assays_by_category", "get_assays_by_tier",
    # Microscopy Advisor
    "recommend_technique", "MicroscopyRecommendation", "MicroscopyReport",
    "TECHNIQUE_DATABASE", "IMAGE_DATABASES", "get_techniques_for_question", "get_sample_prep",
    # Proteomics Client
    "ProteomicsClient", "PPIEdge", "PPINetwork",
    "recommend_workflow", "ProtWorkflowRec", "PRIDEDataset",
    "classify_corona", "get_integrin_ligands",
    "PROTEOMICS_TYPES", "CORONA_PROTEINS", "MATRISOME_CATEGORIES", "INTEGRIN_LIGANDS",
    # Flow Cytometry Advisor
    "recommend_panel", "design_panel", "PanelRecommendation", "PanelDesign", "MarkerSpec",
    "TECHNIQUE_VARIANTS", "FLUOROCHROME_DB", "APPLICATION_KB", "FLOW_REPOSITORIES",
    "get_panels_for_question",
    # Protocol Client
    "search_protocols", "get_protocol_by_id", "get_protocols_for_assay",
    "list_local_protocols", "Protocol", "ProtocolSearchResult",
]
