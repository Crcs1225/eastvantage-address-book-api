# Address Book API

A Python 3.12 / FastAPI solution for the Eastvantage Python Developer assignment.
Addresses are validated, persisted in SQLite, and searchable by distance from a
latitude/longitude pair. Swagger UI is the application interface; no GUI or
external services are required.

## Run on Windows (PowerShell)

Open PowerShell and use your project folder's path:

```powershell
Set-Location -LiteralPath 'C:\path\to\eastvantage-address-book-api'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Replace the `Set-Location` path with your cloned or extracted project's path.
Python 3.12 is required and dependency installation needs internet access.
No environment activation or PowerShell execution-policy changes are needed.

Open **http://127.0.0.1:8000/docs**, expand an endpoint, and click **Try it out**.
The OpenAPI schema is at http://127.0.0.1:8000/openapi.json.
Stop the server with `Ctrl+C`.

The database and its parent directory are created automatically at
`data/addresses.db`, relative to the project, and survive server restarts.
To choose another file, set the environment variable before starting the server:

```powershell
$env:ADDRESS_BOOK_DB = Join-Path $PWD 'data\custom.db'
```

Relative custom paths are resolved from the process's current directory. Use a
file path, not a SQLite URL or `:memory:` database. Remove the override with
`Remove-Item Env:ADDRESS_BOOK_DB`.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/addresses` | Create an address; `201` with the saved object |
| GET | `/addresses?limit=100&offset=0` | List in ID order; `200` with an array |
| GET | `/addresses/nearby?latitude=14.5995&longitude=120.9842&radius_km=5` | Nearby addresses, nearest first; `200` with an array |
| GET | `/addresses/{id}` | Retrieve one address; `200` |
| PUT | `/addresses/{id}` | Replace the complete address; `200` |
| DELETE | `/addresses/{id}` | Delete an address; `204` with no response body |

Create and replacement bodies:

```json
{
  "address": "123 Main Street, Manila",
  "label": "Home",
  "latitude": 14.5995,
  "longitude": 120.9842
}
```

Responses include an integer `id`. Nearby results additionally include
`distance_km`. No matches return `[]`. Search ties are ordered by ID.

- `address` is required, trimmed, must contain 1–1000 characters, and cannot
  contain NUL characters.
- `label` is optional, trimmed, and limited to 200 characters; omitted or `null`
  means no label. Omitting it in a PUT clears the previous label.
- Latitude must be finite and between −90 and 90; longitude between −180 and 180.
- Search requires latitude, longitude, and a finite, nonnegative `radius_km`.
- Pagination accepts a limit of 1–1000 and a nonnegative offset; the default limit
  is 100. IDs and offsets must fit a signed 64-bit SQLite integer.
- Invalid input, missing required fields, and unknown body fields return `422`.
  Missing records return `404`. Database operation failures return a generic
  `500`; diagnostic logs omit address contents.
- PUT is a full replacement, so address text and both coordinates are required.

## Example workflow (second PowerShell window)

Keep the server running, then execute:

```powershell
$base = 'http://127.0.0.1:8000'
$body = @{
    address = '123 Main Street, Manila'
    label = 'Home'
    latitude = 14.5995
    longitude = 120.9842
} | ConvertTo-Json

$saved = Invoke-RestMethod -Method Post -Uri "$base/addresses" -ContentType 'application/json' -Body $body
$addressId = $saved.id
Invoke-RestMethod -Uri "$base/addresses/$addressId"
Invoke-RestMethod -Uri "$base/addresses?limit=10&offset=0"
Invoke-RestMethod -Uri "$base/addresses/nearby?latitude=14.5995&longitude=120.9842&radius_km=5"

$replacement = @{
    address = '456 New Street, Manila'
    latitude = 14.60
    longitude = 120.98
} | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "$base/addresses/$addressId" -ContentType 'application/json' -Body $replacement
Invoke-RestMethod -Method Delete -Uri "$base/addresses/$addressId"
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use separate temporary SQLite files; they do not modify your application
database. They cover CRUD, pagination, restart persistence, validation, SQL text
as data, distance filtering/order, zero radius, inclusive boundaries, the
international date line, and Swagger/OpenAPI routes.

## Design and limitations

- `app/main.py`: application factory, HTTP routes, error handling, lifecycle,
  and operation logging.
- `app/models.py`: Pydantic request and response validation.
- `app/database.py`: parameterized SQLite queries, transactions, and connections
  closed after each operation. Synchronous routes keep database work off the
  event loop, and each connection is created and used in the same worker thread.
- `app/distance.py`: Haversine distance using a mean Earth radius of 6371.0088 km.

Distance is great-circle distance on a sphere, not road travel distance. Boundary
comparisons allow one micrometre of floating-point tolerance. Coordinates are
provided by the caller; no geocoding or real-world address verification occurs.
Nearby searches scan all records, which keeps this assignment small and easy to
run. Large datasets would benefit from spatial indexing and a spatial database.
Authentication, deployment, and a browser GUI are outside the assignment scope.
The server binds only to localhost in the documented commands.

The repository is ready to share as source. Exclude `.venv`, generated caches,
and database files when packaging it.

References: [FastAPI database guidance](https://fastapi.tiangolo.com/tutorial/sql-databases/),
[FastAPI lifespan testing](https://fastapi.tiangolo.com/advanced/testing-events/),
and [Python 3.12 sqlite3](https://docs.python.org/3.12/library/sqlite3.html).
