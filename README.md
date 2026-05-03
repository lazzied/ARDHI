# ARDHI WCS Backend

FastAPI backend for ARDHI crop, soil, suitability, yield, calendar, and soil-report workflows.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

The local SQLite databases are expected at the repository root:

- `ardhi.db`
- `hwsd.db`
- `ecocrop.db`

## Run

```powershell
.\venv\Scripts\uvicorn.exe api.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Test

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

## API Shape

`api/main.py` creates the FastAPI app and database lifespan. Routes live in `api/routes.py`; orchestration lives in `api/services.py`; request models live in `api/models.py`.

## Frontend Integration

The API is documented in FastAPI Swagger at `http://127.0.0.1:8000/docs`.

Most data-bearing responses now include a top-level `units` block. The response `data` keeps its original shape, and `units` describes the meaning of numeric or categorical fields for the frontend.

### Selection Metadata

Use `GET /metadata/selections` first. It returns:

- `user_input.input_level`
- `user_input.water_supply`
- `user_input.irrigation_type`
- `crop_needs.ph_level`
- `crop_needs.texture_class`
- `fao_decision_questions`

These values are backend-owned and should be used directly for frontend dropdowns and question answer choices.

### User Session Flow

1. Generate a `user_id` in the frontend.
2. Call `POST /onboarding`.
3. If needed, call `POST /lab-report`.
4. Call `POST /submit-input` with base user input.
   - set `needs_report = true` when the user selected the report-based workflow
5. Call `POST /soil/fao-decision` with:
   - `user_id`
   - `coord`
   - current `answers`

`/soil/fao-decision` behaves in two modes:

- returns `status = "question"` with the next relevant question and valid options
- returns `status = "complete"` with `selected_fao_90`

When the decision completes, the backend stores the resolved `fao_90_class` in the user session so downstream models can use it automatically.

### External Report Service

When the user selects the report-based workflow:

1. frontend sends `needs_report = true`
2. the external report/OCR service sends the parsed report payload to `POST /lab-report`
3. the backend saves that payload to:

`engines/soil_properties_builder/report_augmentation/input/rapport_values.json`

The backend also stores the normalized report payload and saved path in the user session. If `/report/your-augmented-soil-properties` is called without an inline `report`, the backend reuses the saved report file automatically.

If later you want this backend to fetch the report directly from the external service, use the service-layer helpers in `api/services.py`:

- `prepare_external_report_contract(url, auth, request_contract)`
- `fetch_external_report_payload(contract, request_overrides=None)`
- `fetch_and_persist_external_lab_report(user_id, contract, request_overrides=None)`

Example shape:

```python
from api.services import (
    fetch_and_persist_external_lab_report,
    prepare_external_report_contract,
)

contract = prepare_external_report_contract(
    url="https://other-service/report",
    auth=("username", "password"),
    request_contract={
        "method": "POST",
        "headers": {"Authorization": "Bearer ..."},
        "json_payload": {"user_id": "u1"},
        "report_key": "report",
        "timeout_seconds": 30,
    },
)

result = fetch_and_persist_external_lab_report("u1", contract)
```

That call will:

1. call the external service
2. parse the JSON response
3. extract the nested report payload if `report_key` is provided
4. save it to `rapport_values.json`
5. store the report path in session

### Important Notes

- `coord` is user-provided.
- `user_id` is frontend-generated.
- `smu_id` is resolved by the backend from `coord`.
- `fao_90_class` is resolved by the backend from the FAO decision flow and should not be manually set by the frontend in normal usage.

### Economics API

Use `POST /economics/suitability` to run the PyAEZ-based economic suitability calculation.

Request body:

```json
{
  "crop_name": "rice",
  "crop_cost": 25.0,
  "crop_yield": 2.0,
  "farm_price": 343.0
}
```

Response includes:

- `gross_revenue`
- `net_revenue`
- `units`
- echoed input values
