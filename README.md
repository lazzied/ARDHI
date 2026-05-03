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
5. Call `POST /soil/fao-decision` with:
   - `user_id`
   - `coord`
   - current `answers`

`/soil/fao-decision` behaves in two modes:

- returns `status = "question"` with the next relevant question and valid options
- returns `status = "complete"` with `selected_fao_90`

When the decision completes, the backend stores the resolved `fao_90_class` in the user session so downstream models can use it automatically.

### Important Notes

- `coord` is user-provided.
- `user_id` is frontend-generated.
- `smu_id` is resolved by the backend from `coord`.
- `fao_90_class` is resolved by the backend from the FAO decision flow and should not be manually set by the frontend in normal usage.
