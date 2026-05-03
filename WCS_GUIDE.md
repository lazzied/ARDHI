## WCS Guide

This repository grew in layers. Some folders are the live backend, some are engines that do the real domain work, and some are older preprocessing or data-prep areas that are useful for rebuilding assets but are not part of the normal API request path.

If you are new here, the easiest way to think about it is:

- `api/` is the public surface.
- `engines/` is where the actual crop, soil, report, and FAO logic lives.
- `ardhi/` is the database access layer.
- `raster/` is the low-level TIFF reader layer.
- `data_scripts/` is mostly support tooling and preprocessing, not day-to-day runtime code.

## Runtime Folders

### `api/`

This is the FastAPI application.

- `main.py` creates the app and wires startup and shutdown.
- `routes.py` defines the HTTP endpoints.
- `services.py` is the orchestration layer. It calls engines, updates session state, resolves `smu_id`, persists reports, and shapes API responses.
- `models.py` contains request and response schemas for the API.
- `dependencies.py` exposes shared repository objects to routes.
- `session.py` stores user workflow state in a small SQLite-backed session store.

If someone asks “where does the backend behavior start?”, this folder is the answer.

### `engines/`

This is the domain layer. Most of the real project logic lives here.

#### `engines/global_engines/`

This folder holds the “global” workflow, meaning the path that works from coordinate, raster layers, and database lookups without requiring a lab report.

Important files:

- `suitability_service/` computes per-crop suitability values.
- `yield_service/` computes per-crop yield values.
- `planting_harvesting.py` builds crop calendar outputs.
- `economics_engine.py` wraps the PyAEZ economic suitability calculation.
- `sq.py` computes soil-quality factor outputs.
- `crop_info_fetcher/` exposes EcoCrop crop info and crop-needs data.
- `models.py` and `constants.py` define shared global-engine structures and lookup tables.

The frontend now receives raw per-crop records from the crop recommendation endpoints and does the ranking itself.

#### `engines/OCR_processing/`

This is the report-based path. It is the part of the codebase that works with lab report values and PyAEZ soil-constraint logic.

Important files:

- `models.py` contains shared enums and data structures used by both the global and report workflows.
- `yield_service/yield_calc.py` is the heart of the report-based yield calculation path.
- `yield_service/yield_rank.py` builds report-based yield records per crop.
- `suitability_service/suitability_rank.py` currently acts as a very thin adapter over report yield data.
- `update_db.py` is more of a utility script than a live backend dependency.

#### `engines/soil_properties_builder/`

This folder builds soil-property outputs.

- `hwsd2_prop/` builds soil-property layers directly from HWSD.
- `report_augmentation/` merges report values with HWSD-derived values.
- `output/` writes CSV and Excel exports.

This is where `rapport_values.json` matters. The report workflow saves the external report payload to the expected input path and reuses it later.

#### `engines/soil_FAO_decision.py` and `engines/soil_FAO_constants.py`

These files implement the FAO soil decision flow.

The current runtime flow is:

1. coord
2. resolve `smu_id`
3. fetch FAO90 candidates from HWSD
4. ask only the relevant question(s)
5. persist the chosen FAO class back into session

That chosen FAO class is then reused by downstream models.

### `ardhi/`

This is the database access layer.

- `config.py` defines important filesystem and database paths.
- `db/connections.py` creates SQLite connections.
- `db/ardhi.py` handles the main ARDHI database queries, mostly TIFF path lookups and edaphic file lookups.
- `db/hwsd.py` handles HWSD soil-unit and soil-layer queries.
- `db/ecocrop.py` handles crop information and ecology lookups from EcoCrop.

This folder is intentionally thin. It should answer questions like “where do I fetch this record?” and not “how do I interpret it?”.

### `raster/`

This folder is small and important.

- `tiff_operations.py` is the low-level raster reader used across the backend.

If a feature depends on reading a value from a raster at a coordinate, it probably touches this layer.

## Support and Preprocessing Folders

### `data_scripts/`

This folder is mostly for data fetching, cleanup, transformation, and one-off generation tasks. It matters, but not in the same way the API folders matter.

#### `data_scripts/gaez_scripts/`

These scripts are mostly preprocessing and asset-generation helpers for GAEZ-derived raster layers and metadata.

They are useful when rebuilding source artifacts, auditing derived outputs, or debugging layer generation. They are not the normal request-time path for the API.

#### `data_scripts/hwsd_scripts/`

These are helper scripts and metadata for HWSD source preparation and filtering.

Again: useful for rebuilding and maintenance, not part of the common API call path.

#### `data_scripts/edaphic_crop_reqs/`

These scripts appear to be older or more specialized preprocessing tools for building edaphic crop-requirement tables from appendix-style source material.

This is exactly the kind of folder I would describe as “support tooling”: important historically, useful if source data needs to be regenerated, but not central to everyday backend runtime.

## Data and Reference Folders

### `gaez_data/`

Raw or generated GAEZ-related data assets.

### `hwsd_data/`

Raw or generated HWSD-related data assets.

### `dimension_json/`

Reference JSON assets used during data preparation or metadata mapping.

### `edaphic_crop_requirements_xlsx/`

Spreadsheet-based reference material used by the edaphic preprocessing scripts.

These folders are better thought of as project assets than application code.

## Tests

### `tests/`

This is the active automated test folder.

- `test_api_workflows.py` checks API-level behavior and session/report integration.
- `test_core_contracts.py` checks lower-level data transformation and repository contracts.

The test suite is still compact, but it now covers the key backend workflows that are easiest to break accidentally.

## Model Files

There are several different kinds of “models” in this repo.

- `api/models.py` contains API request and response schemas.
- `engines/OCR_processing/models.py` contains domain enums and shared engine-side models.
- `engines/global_engines/models.py` contains a few generic output dataclasses.
- `engines/global_engines/*/models.py` contain service-specific scoring models.
- `data_scripts/edaphic_crop_reqs/models.py` is preprocessing-specific and not part of the public backend contract.

So when someone says “the models,” it helps to ask which layer they mean.

## API Summary

The most important active API groups are:

- metadata and selectable values
- onboarding and session setup
- FAO decision flow
- crop recommendations
- soil quality
- crop calendar
- crop information and crop needs
- economics
- HWSD soil properties
- report-augmented soil properties
- lab report persistence

Swagger docs still live at:

`http://127.0.0.1:8000/docs`

## Practical Reading Order

If you want to understand the repo without getting lost:

1. `README.md`
2. `api/routes.py`
3. `api/services.py`
4. `engines/soil_FAO_decision.py`
5. `engines/global_engines/`
6. `engines/OCR_processing/`
7. `engines/soil_properties_builder/`
8. `ardhi/db/`

Then look at `data_scripts/` only when you care about how source assets were originally built.

## What Feels Stale

The folders that feel the most like historical support tooling rather than active product code are:

- `data_scripts/edaphic_crop_reqs/`
- parts of `data_scripts/gaez_scripts/tests/`
- utility-style scripts under `engines/global_engines/*debug*`
- utility-style scripts under `engines/OCR_processing/update_db.py`

That does not mean they are useless. It just means they are not where most product changes should begin.

## Final Mental Model

This project is really three systems living together:

1. a FastAPI backend
2. a soil/crop decision engine layer
3. a set of old but valuable data-preparation tools

When people get confused in this repo, it is usually because those three layers blur together. Keeping them separate in your head makes the code much easier to work with.
