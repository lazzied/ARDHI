from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class AugmentedLayer:
    layer:    str
    values:   Dict[str, Any]
    smu_id:   int = 0


@dataclass
class AugmentedLayersGroup:
    layers : List[AugmentedLayer]