// Live smoke test: real Flutter ApiClient -> real Python backend.
//
// This is the only test in the suite that needs a running BE. Start it from
// the backend worktree (repo root, so `data/snapshots/danang-v1` resolves):
//
//   SNAPSHOT_DIR=BE/data/snapshots/danang-v1 \
//     python -m uvicorn BE.app.main:app --host 127.0.0.1 --port 8000
//
// Then run:
//
//   flutter test test/live_api_smoke_test.dart
//   flutter test test/live_api_smoke_test.dart \
//     --dart-define=API_BASE_URL=http://127.0.0.1:8011/v1
//
// The default base URL is the same one `--dart-define=API_BASE_URL` overrides
// for the app (`ApiClient.defaultBaseUrl`), so this test also proves the
// dart-define wiring resolves to the URL the app would call.
import 'dart:convert';

import 'package:davel_trace/api/client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

/// Seed trip from the BE contract fixture (`BE/tests/contract/test_itinerary.py`).
TripRequest _seedTrip() => TripRequest(
  tripId: 'smoke-t1',
  userId: 'u1',
  city: 'da-nang',
  date: '2026-10-24',
  startTime: '07:00',
  endTime: '18:00',
  days: 1,
  travelers: 2,
  budget: 3000000,
  transport: const <String>['motorbike'],
  activities: const <String>['bien', 'an'],
);

void main() {
  const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000/v1',
  );

  late ApiClient api;

  setUp(() {
    // Long timeout: the BE runs CP-SAT for three profiles per request.
    api = ApiClient(
      baseUrl: baseUrl,
      timeout: const Duration(minutes: 2),
    );
  });

  tearDown(() => api.close());

  test(
    'live BE: GET /v1/health and POST /v1/itinerary return 200 with gate passed',
    () async {
      // 1. Health. At the base commit (origin/feat/fe-apiclient) ApiClient has
      //    no typed health() method, so hit the same resolved base URL with
      //    the same http package. This also asserts the dart-define base URL
      //    the client resolved is the one the app would call.
      final healthUri = Uri.parse('${api.baseUrl}/health');
      final http.Response healthResponse;
      try {
        healthResponse = await http
            .get(healthUri)
            .timeout(const Duration(seconds: 20));
      } on Exception catch (error) {
        fail('BE unreachable at $healthUri: $error');
      }

      expect(
        healthResponse.statusCode,
        200,
        reason: 'GET $healthUri -> ${healthResponse.statusCode}: '
            '${healthResponse.body}',
      );
      final health =
          jsonDecode(utf8.decode(healthResponse.bodyBytes))
              as Map<String, dynamic>;
      expect(health['status'], 'ok');
      expect(health['snapshot'], isA<String>());
      expect(health['snapshot'], isNotEmpty);

      // 2. Itinerary through the typed client. `_send` throws ApiException on
      //    any non-2xx, so reaching the assertions below means HTTP 200.
      final PlanList result;
      try {
        result = await api.createItinerary(trip: _seedTrip());
      } on ApiException catch (error) {
        fail(
          'POST ${api.baseUrl}/itinerary -> ${error.statusCode} '
          '${error.code}: ${error.message}',
        );
      }

      expect(result.selected, isNull);
      expect(result.plans, hasLength(3));
      expect(
        result.plans.map((plan) => plan.profile),
        <String>['savings', 'balanced', 'experience'],
      );

      for (final plan in result.plans) {
        expect(plan.itineraryId, isNotEmpty);
        expect(plan.tripId, 'smoke-t1');
        expect(plan.activities, isNotEmpty);

        // Hard gate: BE `scores.gate` must be true and the plan not excluded.
        expect(
          plan.scores['gate'],
          isTrue,
          reason: 'plan ${plan.profile} gate failed: ${plan.scores}',
        );
        expect(plan.scores['excluded'], isFalse);

        // Every constraint_status entry is 1 (pass) on a gated plan.
        expect(plan.constraintStatus, isNotEmpty);
        expect(
          plan.constraintStatus.values.every((value) => value == 1),
          isTrue,
          reason: 'plan ${plan.profile} constraint_status: '
              '${plan.constraintStatus}',
        );
      }
    },
    timeout: const Timeout(Duration(minutes: 4)),
  );
}
