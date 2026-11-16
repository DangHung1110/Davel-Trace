# Quickstart: Stable Planning Roadmap MVP

Run commands from the repository root in PowerShell.

## 1. Backend dependencies

```powershell
python -m pip install -r BE/requirements.txt
```

No external database is required. The first accepted selection creates `BE/data/accepted_plans.db`. In DBeaver choose **SQLite**, browse to that file, and open tables `acceptance_records` and `shadow_observations`.

Optional custom path:

```powershell
$env:ACCEPTANCE_DB_PATH = 'D:\data\davel-trace-accepted.db'
```

## 2. Start backend

```powershell
python -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

Expected health: `http://127.0.0.1:8000/v1/health` returns `status=ok`.

## 3. Install Flutter packages

The repository uses the prepared local Flutter SDK junction and the declared `FE/pubspec.yaml` packages:

```powershell
& '.\.flutter-sdk\bin\flutter.bat' pub get --directory FE
```

## 4. Run the phone-frame demo on the laptop

```powershell
& '.\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Flutter opens Chrome. On a desktop viewport the app is centered in the 390×844 phone frame. If the backend is down, the same command still opens seeded demo state with an explicit offline label.

Git Bash equivalent:

```bash
./.flutter-sdk/bin/flutter.bat run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Do not use PowerShell syntax such as `$env:...` or `&` inside Git Bash.

## 5. Planner harness and root map

```powershell
python server.py
```

- Root map: `http://127.0.0.1:5500/`
- Planner harness: `http://127.0.0.1:5500/FE/test_harness.html`
- Onboarding catalog: `http://127.0.0.1:5500/FE/onboard.html`

Use `server.py`; `python -m http.server` does not support the byte-range behavior required by PMTiles.

## 6. Validation

```powershell
python -m pytest BE/tests -q
& '.\.flutter-sdk\bin\flutter.bat' analyze FE
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' test
& '..\.flutter-sdk\bin\flutter.bat' build web --release --dart-define=API_BASE_URL=http://127.0.0.1:8000
Pop-Location
```

Expected outcomes:

- every returned alternative has `gate.passed=true`;
- diverse mode targets five alternatives and explains any shortage;
- selecting with one idempotency key twice returns one acceptance ID;
- readiness remains disabled below roadmap evidence thresholds;
- the mobile demo can move among itinerary, map, expenses, and profile in live or seeded mode;
- root map still loads and its A/B search, route, and vehicle play/pause smoke flow is available.
