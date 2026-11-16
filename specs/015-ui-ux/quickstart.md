# Review the mobile journeys

Start FastAPI/PostgreSQL using the existing BE quickstart, then from FE:

```powershell
& '..\.flutter-sdk\bin\flutter.bat' pub get
& '..\.flutter-sdk\bin\flutter.bat' run -d chrome --web-port 5501 --web-hostname 127.0.0.1 --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=APP_MODE=demo
```

For the already running release preview, open http://127.0.0.1:5501 and Ctrl+F5.
Keep real credentials in ignored BE/.env; no new environment values are needed.

1. Sign in normally. Open Account: verify the email belongs to the login identity,
   security is labeled, and Sign out is visible without opening a hidden menu.
2. Open Trips. Select a trip: dates, daily activities and Add activity are visible
   before any generated alternatives. Back/Trips returns to the collection.
3. Open Plan. Review the separate generation/optional Gemini tools. Account-wide
   travel defaults explicitly describe the saved snapshot boundary for existing trips.
4. With disposable test data, generate/review/accept a plan. Check that returning to
   the daily itinerary immediately displays the saved version. Switch trips and confirm
   alternatives and the selected trip agree. A failed/late request must not leak plans.
5. Edit a 7-day trip with nondefault hours: save without changing them, reopen and check
   that dates, budget, transport and hours remain identical. Validate 21 travelers and
   an end time earlier than start; both must produce a useful field error.
6. Expenses identifies the selected trip and its actual storage/sync status. Change trip
   returns to the trip collection. Deleting an expense requires confirmation.
7. Map keeps existing GPS follow/recenter and route playback. Playback says simulation;
   no hardcoded weather, microphone or nonfunctional 3D control is presented as a feature.
8. Try 320px/390px width, 200% system text and a short viewport. Scroll all pages and
   open the keyboard: the trip save button must remain above the keyboard.
9. Sign out from Account and from Security. Protected subpages close and sign-in returns.

## Automated checks and visual captures

```powershell
& '..\.flutter-sdk\bin\flutter.bat' analyze --no-pub
& '..\.flutter-sdk\bin\flutter.bat' test --no-pub
& '..\.flutter-sdk\bin\flutter.bat' test test/ui_ux_test.dart --no-pub --dart-define=CAPTURE_UI=true --update-goldens
node --test tool/map_location_bridge.test.cjs
```

Optional captures are written to ignored `FE/build/ui-review/`. They use rendered
production widgets and bundled fonts with fake account data; regular test runs do not
depend on generated image files or golden comparisons. Do not update screenshots as a
substitute for inspecting them. Browser review also covers the actual release build.
