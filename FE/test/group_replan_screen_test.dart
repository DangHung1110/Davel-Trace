import 'dart:convert';

import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/core/networking/api_client.dart';
import 'package:davel_trace/features/groups/presentation/group_replan_screen.dart';
import 'package:davel_trace/features/map/domain/location_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _Location implements MapLocationProvider {
  int reads = 0;

  @override
  Future<MapLocationResult> currentLocation() async {
    reads++;
    return const MapLocationResult(
      MapLocationStatus.located,
      location: MapLocation(latitude: 16.067, longitude: 108.220),
    );
  }

  @override
  Stream<MapLocationResult> watchLocation() => throw UnimplementedError();
}

class _State extends AppState {
  _State() : super(FakeManagementRepository(seeded: true));

  Map<String, Object?>? chosen;

  @override
  Future<void> requestReplan({
    String? sourceVersionId,
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
    String? currentPoiId,
    String? remainingFrom,
    bool includeCurrentStop = false,
  }) async {
    chosen = {
      'version': sourceVersionId,
      'completed': completedActivityIds,
      'poi': currentPoiId,
      'from': remainingFrom,
    };
  }
}

void main() {
  testWidgets(
    'group replan uses a local fix and sends only the confirmed place',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(390, 844));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      SharedPreferences.setMockInitialValues({});
      final state = _State();
      await state.initialize();
      addTearDown(state.dispose);
      final trip = state.activeTrip!;
      final location = _Location();
      final api = ApiClient(
        baseUrl: 'http://example.test',
        client: MockClient((request) async {
          expect(request.url.query, isEmpty);
          final body = switch (request.url.path) {
            '/v1/trip-groups/trip-1' => {'pinned_meeting': null},
            '/v1/trip-groups/trip-1/plans' => {
              'active': {
                'id': 'source-version',
                'activities': [
                  {'id': 'stop-1', 'name': 'Bảo tàng Chăm'},
                ],
              },
            },
            '/v1/pois/location-index' => {
              'items': [
                {
                  'poi_id': 'dragon-bridge',
                  'name': 'Cầu Rồng',
                  'lat': 16.0674,
                  'lon': 108.2204,
                },
                {
                  'poi_id': 'far',
                  'name': 'Xa trung tâm',
                  'lat': 17,
                  'lon': 109,
                },
              ],
            },
            _ => throw StateError('Unexpected request ${request.url.path}'),
          };
          return http.Response.bytes(utf8.encode(jsonEncode(body)), 200);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.of(context).push<void>(
                  MaterialPageRoute(
                    builder: (_) => GroupReplanScreen(
                      state: state,
                      api: api,
                      trip: trip,
                      location: location,
                    ),
                  ),
                ),
                child: const Text('Mở'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Mở'));
      await tester.pumpAndSettle();
      expect(location.reads, 0);
      await tester.tap(find.byKey(const Key('group-replan-near-me')));
      await tester.pumpAndSettle();
      expect(find.text('Xa trung tâm'), findsNothing);
      expect(state.chosen, isNull);
      await tester.tap(find.text('Cầu Rồng'));
      await tester.pumpAndSettle();
      final progress = find.byTooltip('Đổi trạng thái điểm dừng');
      await tester.ensureVisible(progress);
      await tester.tap(progress);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Đã ghé'));
      await tester.pumpAndSettle();
      final submit = find.byKey(const Key('group-replan-submit'));
      await tester.scrollUntilVisible(
        submit,
        180,
        scrollable: find
            .descendant(
              of: find.byType(ListView),
              matching: find.byType(Scrollable),
            )
            .first,
      );
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(location.reads, 1);
      expect(state.chosen, containsPair('poi', 'dragon-bridge'));
      expect(state.chosen, containsPair('version', 'source-version'));
      expect(state.chosen, containsPair('completed', ['stop-1']));
      expect(state.chosen!['from'], endsWith('+07:00'));
      expect(find.text('Mở'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
