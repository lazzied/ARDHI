from dataclasses import dataclass


@dataclass
class LayerDicts:
    yxx: dict #  - RES05-SX2:     share of VS+S+MS land (0-10000, 10km) → regional overview
    
YIELD_LAYERS = {
    "YXX": "RES05-YXX",       # regional ceiling, 10km
}   