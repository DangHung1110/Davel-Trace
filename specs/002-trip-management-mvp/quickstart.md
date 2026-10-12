# Quickstart: Trip Management MVP

## Prerequisites

- Python 3.11
- Flutter SDK available through the project's configured Flutter launcher
- Chrome for laptop/mobile-viewport testing
- Optional: DBeaver with SQLite support

## 1. Backend setup and code-first migration

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r BE\requirements.txt
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
```

Start the management API:

```powershell
.\.venv\Scripts\python.exe BE\run.py
```

Expected API: `http://127.0.0.1:8000/v1/health`.

## 2. PMTiles byte-range server

In another terminal from repository root:

```powershell
python server.py
```

Expected map prototype: `http://127.0.0.1:5500`. Do not use `python -m http.server` because PMTiles needs byte-range responses.

## 3. Flutter app

```powershell
Set-Location FE
flutter pub get
flutter run -d chrome --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

Use Chrome responsive mode or resize the window to a phone-sized viewport.

## 4. End-to-end validation

1. Create a profile and make it active.
2. Create a one-day Da Nang trip with a 3,000,000 VND budget.
3. Add three activities from the POI catalog or custom coordinates, edit one and reorder them.
4. Open the map and request a route; confirm source/warning truthfulness.
5. Add expenses totaling 2,500,000 VND and confirm the 80% alert and 500,000 VND remaining.
6. Edit one expense, delete another and confirm totals recalculate.
7. Restart API and Flutter app; confirm all management data remains.
8. Run the existing map/search A-B/route/play-pause prototype smoke flow.

## 5. Inspect with DBeaver

1. Choose **New Database Connection → SQLite**.
2. Select the absolute file `BE/data/davel_trace.db` in this worktree.
3. Open tables `user_profiles`, `trips`, `itineraries`, `activities`, `expenses`, `route_segments`, `device_state` and `alembic_version`.
4. Do not edit schema manually. Change SQLAlchemy models and generate/review a new Alembic revision instead.

## 6. Automated validation

```powershell
.\.venv\Scripts\python.exe -m pytest BE\tests -q
.\.venv\Scripts\python.exe -m alembic -c BE\alembic.ini upgrade head
Set-Location FE
flutter analyze
flutter test
flutter build web --dart-define=DAVEL_API_BASE_URL=http://127.0.0.1:8000
```

Pass criteria: all tests/analyzers succeed, migrations initialize a blank database, no severe browser console errors, and the manual end-to-end flow matches the contract.
