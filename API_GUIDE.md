## API Guide

This file is for someone who is still getting comfortable with backend work and wants to understand both:

1. how an API is usually structured in general
2. how the API in this WCS project is structured in particular

It is intentionally written in a slower, more human way than code comments.

## Part 1: The Big Picture

### What an API is

At a very abstract level, an API is a controlled way for one program to ask another program to do something.

In this project:

- the frontend asks the backend for data
- sometimes another service sends a report payload to the backend
- the backend reads databases, raster files, and engine code
- the backend returns a JSON response

So the backend is the middle layer between:

- users and UI on one side
- data, calculation logic, and files on the other side

### What happens when an API request comes in

A normal request lifecycle looks like this:

1. a client sends an HTTP request
2. the backend matches it to a route
3. the request body is validated
4. the route calls application logic
5. the application logic may call:
   - repositories
   - services
   - engines
   - file readers
   - session storage
6. a response object is built
7. JSON is returned

That is the general pattern this project follows.

### Why APIs are often split into layers

If everything is written in one giant file, the code becomes hard to change safely.

So backend code is often separated into roles:

- routes:
  receive requests and return responses
- models:
  define what request/response shapes look like
- services:
  orchestrate business logic
- repositories:
  fetch data from databases
- engines:
  do the actual scientific or domain calculations
- utilities:
  read files, parse things, format things

That separation is exactly what this project now uses.

### Techniques used in this API

This backend uses a few important backend techniques that are worth understanding as a beginner.

#### 1. Schema validation

Before the backend starts work, FastAPI and Pydantic validate input data.

That means:

- required fields must exist
- enums must match allowed values
- wrong types are rejected early

This helps catch bad frontend requests before the deeper logic runs.

#### 2. Dependency injection

Routes do not directly open database connections themselves.

Instead, the route asks for `repos: Repositories = Depends(get_repositories)`.

That means:

- the app controls repository setup centrally
- routes stay simple
- tests can replace real repositories with fake ones

This is a very useful backend pattern.

#### 3. Lifespan-managed resources

The app opens database connections during startup and closes them during shutdown.

That avoids:

- opening a new connection in every route manually
- forgetting to close connections
- inconsistent setup between endpoints

#### 4. Service layer orchestration

The route does not calculate crop recommendations directly.

Instead:

- route receives request
- service function coordinates the work
- service calls repositories and engines
- route returns the result

This keeps the route readable and the business logic reusable.

#### 5. Session state

Some workflows are multi-step.

For example:

- user submits input
- backend resolves `smu_id`
- backend asks FAO questions
- user answers later
- final FAO class must still be remembered

That means the backend needs session state, not just stateless one-off requests.

This project stores that state in a small SQLite-backed session store.

#### 6. Thin HTTP layer

A healthy API route should mostly:

- accept input
- validate input
- call a service
- return output

It should not be the place where all the domain logic is written.

This project tries to keep that boundary clean.

## Part 2: How This API Is Organized

The API layer lives in the `api/` folder.

### `api/main.py`

This is the application entrypoint.

Its main jobs are:

- create the FastAPI app
- wire startup and shutdown behavior
- register the routes
- install top-level error handlers

#### `lifespan(app)`

This function runs during app startup and shutdown.

On startup it:

- opens the ARDHI database connection
- opens the HWSD database connection
- opens the EcoCrop database connection
- wraps them in repository objects
- stores them on `app.state.repositories`

On shutdown it:

- closes the three database connections

Why this matters:

- every request can reuse the repositories
- setup is centralized
- tests can bypass this with a no-op lifespan

#### `noop_lifespan(app)`

This is used mostly for tests.

It does nothing, which is useful when a test wants to inject fake repositories and not touch real database files.

#### `create_app(repositories=None, lifespan_enabled=True)`

This is the app factory.

It:

- creates the FastAPI instance
- optionally enables the real lifespan
- includes the router
- optionally injects repositories directly
- defines custom exception handlers

Why an app factory is good:

- easier testing
- easier reuse
- cleaner startup behavior

#### Exception handlers

Two important exception handlers are registered:

- `ValueError` -> HTTP 400
- `FileNotFoundError` -> HTTP 404

This means service-layer exceptions can stay Pythonic while still producing a reasonable API response.

### `api/routes.py`

This file defines the HTTP endpoints.

Think of it as the public menu of the backend.

Each route should answer:

- which method?
- which URL?
- what request model?
- what response model?
- which service function does it call?

#### `success(data=None, **extra)`

This is a small response helper.

It standardizes most responses into:

```json
{
  "status": "success",
  "data": ...,
  "units": ...,
  "output_path": ...
}
```

That consistency makes frontend work easier.

#### Route groups

The routes fall into a few families.

##### 1. Health and metadata

- `GET /`
- `GET /metadata/selections`

`/metadata/selections` is especially useful because it gives the frontend all the backend-owned dropdown values and FAO question definitions.

##### 2. Session and onboarding

- `POST /onboarding`
- `POST /lab-report`
- `POST /submit-input`

These routes start and populate the user workflow state.

##### 3. FAO soil decision

- `POST /soil/fao-decision`

This is the dynamic decision flow that uses:

- `coord`
- resolved `smu_id`
- FAO90 candidates
- user answers

It either returns the next question or the final FAO class.

##### 4. Crop outputs

- `GET /global/crop-recommendations/{user_id}`
- `GET /report/crop-recommendations/{user_id}`
- `POST /economics/suitability`
- `POST /calendar`
- `GET /crops-info`
- `POST /crops-needs`

##### 5. Soil outputs

- `POST /global/soil-constraint-factor`
- `POST /report/soil-constraint-factor/{crop_name}`
- `POST /your-hwsd-soil-properties`
- `POST /report/your-augmented-soil-properties`

### `api/models.py`

This file contains the request and response schemas.

These are not engine models. These are API contract models.

That distinction matters.

#### Why this file exists

It gives the backend one place to define:

- what the frontend must send
- what fields are optional
- what enums are valid
- what documentation should appear in Swagger

#### Important models

##### `OnboardingChoice`

Used when the frontend starts a workflow and wants to record whether a report already exists.

##### `LabReport`

Used when report data is sent into the backend.

##### `UserInput`

This is the main request model in the system.

It includes:

- `user_id`
- `coord`
- `input_level`
- `water_supply`
- `irrigation_type`
- `answers`
- `needs_report`
- `lab_report_exists`
- optional `smu_id`
- optional `fao_90_class`

Two important ideas here:

1. some values are user-facing inputs
2. some values are resolved by backend logic later

So the same model carries both direct user input and enriched context.

##### `FaoDecisionRequest`

Used specifically for the FAO question flow.

Includes:

- `user_id`
- `coord`
- `answers`

##### `EconomicSuitabilityRequest`

Used by the economics endpoint.

Simple, direct, no database dependency.

##### `ApiResponse`

This is the common outer response shell.

It includes:

- `status`
- `data`
- `units`
- `output_path`

This is useful because the frontend can expect a stable top-level response shape across the backend.

### `api/dependencies.py`

This file is small but important.

It defines:

#### `Repositories`

A dataclass that bundles:

- `ardhi`
- `hwsd`
- `ecocrop`

This prevents route signatures from becoming messy.

#### `get_repositories(request)`

This pulls `app.state.repositories` from the running FastAPI app.

If they are missing, it raises HTTP 503.

Why this matters:

- routes do not need to know how repositories were created
- app startup owns repository initialization
- tests can inject fake repositories

### `api/session.py`

This file manages user workflow state.

The project originally had in-memory session behavior, but now it uses SQLite persistence.

#### `SessionStore`

This class acts like a tiny persistent dictionary.

Its main methods are:

- `_connect()`
- `_init_db()`
- `get(user_id, default=None)`
- `__setitem__(user_id, payload)`
- `setdefault(...)`
- `clear()`

#### Storage strategy

The session payload is:

- stored by `user_id`
- serialized with `pickle`
- persisted in `api_sessions.db`

This is simple, local, and enough for current workflow persistence.

It is not a full enterprise session system, but it is much better than losing everything on restart.

## Part 3: The Service Layer in This Project

The service layer lives in `api/services.py`.

If routes are the public menu, services are the kitchen.

This file is the most important API file to understand after `routes.py`.

### What service functions usually do here

A service function may:

- read session state
- resolve derived values like `smu_id`
- call database repositories
- call engine classes
- merge results into API-friendly shapes
- persist new state

This file is where “workflow thinking” lives.

### Service function categories

#### 1. Response metadata helpers

These functions define `units` blocks and selection metadata.

Examples:

- `selection_catalog_units()`
- `fao_decision_units()`
- `crop_recommendation_units()`
- `soil_property_units()`

These are not scientific engines. They are API contract helpers.

#### 2. Selection and metadata builders

##### `build_selection_catalog()`

Builds frontend-selectable values for:

- input levels
- water supply
- irrigation type
- pH level
- texture class
- FAO question bank

This is a nice example of backend ownership over UI choices.

#### 3. Session and report persistence helpers

##### `_normalize_report_payload(report_payload)`

Accepts either:

- a JSON string
- a dict
- a list

and normalizes it into Python data.

##### `persist_lab_report(user_id, report_payload)`

This:

- normalizes the incoming report
- saves it to `rapport_values.json`
- stores report data in the session

This is where the external report service effectively hands off its result to the backend.

#### 4. External report-service integration helpers

##### `ExternalReportRequestContract`

This dataclass describes how to call an external service:

- URL
- method
- headers
- auth
- JSON payload
- query params
- timeout
- optional nested response key

##### `prepare_external_report_contract(...)`

Convenience constructor for building the contract.

##### `fetch_external_report_payload(...)`

Calls the external service via `requests`, validates the JSON response, and optionally extracts a nested report payload.

##### `fetch_and_persist_external_lab_report(...)`

Combines fetching and saving into one workflow.

#### 5. Session lookup helpers

##### `get_session_or_404(user_id)`

Fetches a user session or fails with 404.

This is a common pattern because many routes depend on prior workflow steps having already happened.

#### 6. Coordinate and FAO helpers

##### `resolve_smu_id(coord)`

Uses raster logic to turn coordinates into an SMU identifier.

##### `get_fao_candidates_for_coord(coord, repos)`

Uses the `smu_id` to query HWSD and fetch all candidate FAO90 classes.

##### `_top_fao_class(candidates)`

Gets the highest-priority FAO class when a single default is needed.

##### `resolve_user_input_context(data, repos)`

This is one of the most important workflow helpers.

It enriches `UserInput` by:

- resolving `smu_id`
- resolving a default `fao_90_class` if needed

So the backend can carry smarter context than the raw frontend sent.

#### 7. State-persistence workflow helpers

##### `store_user_input(data, repos)`

Takes `UserInput`, enriches it, and stores it in session.

##### `_store_fao_decision_state(...)`

Stores:

- coord
- smu_id
- candidate FAO classes
- answers
- final FAO class if known

This is what allows the FAO multi-step workflow to continue across requests.

#### 8. Business-output builders

These are the main service functions behind endpoints.

##### `build_global_crop_recommendations(...)`

Uses:

- `CropSuitability`
- `CropYield`

and returns raw per-crop score lists for the global workflow.

Important detail:

the frontend now handles ranking. The backend returns raw crop records.

##### `build_report_crop_recommendations(...)`

Uses:

- `ReportCropYield`
- `ReportCropSuitability`

and returns raw per-crop score lists for the report workflow.

##### `build_calendar(...)`

Builds planting and harvest timing records.

##### `build_global_soil_quality(...)`

Builds global soil quality factor outputs.

##### `build_report_soil_quality(...)`

Builds report-based soil quality factor outputs.

##### `build_crops_info(...)`

Returns EcoCrop crop reference information.

##### `build_economic_suitability(...)`

Wraps the economics engine and turns it into a JSON-ready payload.

##### `build_crops_needs(...)`

Returns crop ecological needs after combining:

- user input context
- pH class
- texture class
- EcoCrop data
- edaphic augmentation

##### `build_hwsd_soil_report(...)`

Uses HWSD only.

##### `build_augmented_soil_report(...)`

Uses report data plus HWSD.

If no inline report is passed, it falls back to the report path saved in the session.

##### `build_fao_decision(...)`

This is the dynamic FAO workflow service.

It:

1. resolves `smu_id`
2. fetches FAO candidates
3. handles the “only one candidate” shortcut
4. runs dynamic question logic when more than one candidate exists
5. persists final `fao_90_class` when complete

This function is one of the best examples of service-layer orchestration in the project.

## Part 4: How the API Talks to the Rest of the Project

The API layer does not do the scientific work by itself.

It delegates to:

- repositories in `ardhi/db/`
- raster helpers in `raster/`
- engines in `engines/`

### Flow example: FAO decision

Frontend sends:

- `user_id`
- `coord`
- current answers

Route:

- `POST /soil/fao-decision`

Service:

- `build_fao_decision(...)`

Repository:

- `repos.hwsd.get_fao_90_candidates(...)`

Utility:

- `get_smu_id_value(...)`

Engine:

- `classify_soil_dynamic(...)`

Session:

- save `fao_90_class`

Response:

- next question or final FAO class

That is a complete backend workflow in miniature.

### Flow example: report-based soil properties

Frontend or external service sends report data:

- `/lab-report`

Service:

- `persist_lab_report(...)`

File saved:

- `rapport_values.json`

Later route:

- `/report/your-augmented-soil-properties`

Service:

- `build_augmented_soil_report(...)`

Engine:

- report augmentation + HWSD property generator

Response:

- JSON soil properties
- workbook output path

## Part 5: Why This Architecture Is Reasonable

This API is not overdesigned, but it uses a sensible structure for this kind of project.

### Good decisions in the current architecture

#### Thin routes

Routes stay readable and mostly declarative.

#### Explicit models

The request contracts are visible and documented.

#### Service layer

Workflow logic is centralized instead of scattered across routes.

#### Repository layer

Database logic stays separated from engine logic.

#### Session persistence

Multi-step workflows are supported properly.

#### Testability

The app factory plus dependency injection make tests much easier.

## Part 6: Practical Advice for Working in This API

### If you want to add a new endpoint

Usually the steps are:

1. define or update a request model in `api/models.py`
2. add a service function in `api/services.py`
3. add the route in `api/routes.py`
4. add units metadata if needed
5. add tests

### If you want to change business behavior

Start in `api/services.py`, then follow the engine calls.

Do not put real business logic directly into the route unless it is truly tiny.

### If you want to change database behavior

Start in `ardhi/db/`.

Try to keep:

- queries in repositories
- interpretation in services or engines

### If you want to debug a broken request

Best reading order:

1. route in `api/routes.py`
2. service in `api/services.py`
3. repository or engine called by that service
4. related request model in `api/models.py`

### If you want to understand why session data is missing

Check:

- was `/submit-input` called?
- was `/onboarding` called?
- did `/soil/fao-decision` persist the final class?
- was `/lab-report` called and saved?

Most multi-step problems in this backend are session-sequencing problems.

## Part 7: Endpoint Summary for This Project

Here is the human summary of the current API.

### Metadata

- `GET /`
  - health check

- `GET /metadata/selections`
  - all backend-owned dropdown/select values
  - FAO question bank

### Session setup

- `POST /onboarding`
  - start session state

- `POST /submit-input`
  - store main user input
  - resolve `smu_id`
  - seed context

- `POST /lab-report`
  - save external or frontend-provided report payload

### FAO workflow

- `POST /soil/fao-decision`
  - advance or complete the dynamic FAO question flow

### Crop and soil outputs

- `GET /global/crop-recommendations/{user_id}`
- `GET /report/crop-recommendations/{user_id}`
- `POST /global/soil-constraint-factor`
- `POST /report/soil-constraint-factor/{crop_name}`
- `POST /calendar`
- `GET /crops-info`
- `POST /crops-needs`
- `POST /economics/suitability`
- `POST /your-hwsd-soil-properties`
- `POST /report/your-augmented-soil-properties`

## Part 8: Final Mental Model

If you want one simple picture in your head, use this:

### The API layer in this project does three jobs

1. validate and receive requests
2. coordinate workflows across engines, repositories, and session state
3. return JSON in a frontend-friendly shape

That is the job.

The API layer is not:

- the scientific engine itself
- the raw database layer
- the preprocessing tooling

It is the translator and coordinator between those worlds.

If you keep that boundary clear in your head, this project becomes much easier to reason about.
