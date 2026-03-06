"""
Drug Delivery Engine
====================
PubChem + ChEMBL compound search, PK modelling (Level 1-3), and
release-profile fitting for biomaterial drug-delivery applications.

Public API:
    from drug_engine.pubchem_client  import PubChemClient
    from drug_engine.chembl_client   import ChEMBLClient
    from drug_engine.pk_models       import (PKLevel1, PKLevel2, PKLevel3,
                                             fit_higuchi, simulate_release)
"""
from .pubchem_client import PubChemClient
from .chembl_client  import ChEMBLClient
from .pk_models      import PKLevel1, PKLevel2, PKLevel3, simulate_release

__all__ = [
    "PubChemClient", "ChEMBLClient",
    "PKLevel1", "PKLevel2", "PKLevel3", "simulate_release",
]
