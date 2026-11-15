# Google OAuth and SMTP local setup

Active branch: `task/012-planning-llm-integration`. Preserve existing ignored
`BE/.env`; do not overwrite DB/Gemini settings with `.env.example`.

## Gmail SMTP

```dotenv
IDENTITY_DEV_OUTBOX_ENABLED=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_SSL=false
SMTP_USERNAME=YOUR_SENDER@gmail.com
SMTP_PASSWORD=YOUR_GOOGLE_APP_PASSWORD
SMTP_FROM_EMAIL=YOUR_SENDER@gmail.com
SMTP_FROM_NAME=Davel Trace
SMTP_TIMEOUT_SECONDS=10
```

Enable Google two-step verification and create an app password at
https://myaccount.google.com/apppasswords. Secrets stay in backend env only.
`sent` means SMTP acceptance, not guaranteed inbox arrival; check Spam too.
Failed actions cannot be redeemed; resend issues a new code. No dev-inbox
fallback occurs in SMTP mode. An exceptional DB commit failure after SMTP
acceptance requires a resend, since SMTP and DB are not one transaction.

## Google client

Choose a **Web application** in Google Auth Platform. Add both JavaScript origins
(no path/trailing slash): `http://localhost:5501`, `http://127.0.0.1:5501`.
Set the authorized redirect URI to:

```text
http://localhost:8000/v1/auth/google/callback
```

In Audience add your Gmail to Test users while in Testing. Use a standard
interactive client; AI-agent designation is for separate agent workflows and
is not needed here. This app requests only `openid email profile`.

```dotenv
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_REDIRECT_URI=http://localhost:8000/v1/auth/google/callback
GOOGLE_TIMEOUT_SECONDS=10
```

Flutter receives the authorization origin from `/v1/auth/capabilities` and opens
the popup on the callback host. Ordinary API calls can use 127.0.0.1; do not change
the popup to that host when the callback uses localhost (different cookie scopes).
Production requires HTTPS and explicit allowed frontend origins.

## Run

From repo root, use a Python installation with the requirements installed:

```powershell
python -m pip install -r BE/requirements.txt
docker compose --env-file BE/.env up -d postgres
python -m alembic -c BE/alembic.ini upgrade head
python -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
Pop-Location
```

Only one frontend server should own 5501. The current agent session instead serves
the verified release build using the repository byte-range server. To reproduce:

```powershell
Push-Location FE
& '..\.flutter-sdk\bin\flutter.bat' build web --release --no-pub --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
Push-Location build/web
python ../../../server.py --port 5501
Pop-Location
Pop-Location
```

## Test mobile UI

1. Open http://127.0.0.1:5501 and hard reload after rebuilding.
2. Accept the terms, click **Tiếp tục bằng Google**, allow the popup, and complete
   Google consent yourself. Popup closes and account email appears on success.
   Reload to exercise refresh-token session restoration.
3. Existing password accounts with the same email are not silently linked. Use
   password login; explicit linking is outside this increment.
4. Select **Quên mật khẩu?**, enter an active account email, copy the emailed code
   and choose a new password (10–128 characters, letters and digits). Old sessions
   and the previous password stop working. Google-created accounts can set their
   first Davel password through this flow for password-confirmed account actions.
5. Registering with a password requires email verification. Use resend when needed.
   SMTP mode hides dev-inbox buttons even if the app remains in broader demo mode.

Capabilities reports configuration, not live provider health. Readiness checks
the local DB/schema; neither proves real Google consent has completed.

## Cross-origin popup regression

The Windows Flutter browser-test host in the installed SDK returns 404 for its
local CanvasKit resources. A small Dart/DOM probe instead imports the production
popup predicate directly, without a rendering engine. It creates a sandboxed,
opaque-origin iframe and verifies accepted source plus rejected origin/source.

From `FE`, with the release server on port 5501:

```powershell
& '..\.flutter-sdk\bin\dart.bat' compile js tool/google_popup_probe.dart -o build/web/google_popup_probe.js
Copy-Item tool/google_popup_probe.html build/web/google_popup_probe.html
```

Open http://127.0.0.1:5501/google_popup_probe.html. Expected result: `passed: true`
and all four checks true. This is a browser regression, not a Google account login.
No shared Flutter SDK files were modified to work around the runner problem.

The local `.pub-cache-local` junction is ignored. It reuses the user's Pub cache
under a path without spaces; no dependency versions or lockfile were changed.

## References

- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/openid-connect/openid-connect
- https://developers.google.com/workspace/gmail/imap/imap-smtp
- https://support.google.com/accounts/answer/185833
- https://support.google.com/cloud/answer/15549257
