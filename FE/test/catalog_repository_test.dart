import 'dart:convert';

import 'package:davel_trace/core/networking/api_client.dart';
import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('catalog search keeps provenance and verified state', () async {
    Uri? requested;
    final repository = HttpManagementRepository(
      ApiClient(
        baseUrl: 'http://example.test',
        client: MockClient((request) async {
          requested = request.url;
          return http.Response.bytes(
            utf8.encode(
              jsonEncode({
                'items': [
                  {
                    'poi_id': 'bridge-1',
                    'name': 'Cầu Rồng',
                    'type': 'landmark',
                    'lat': 16.0611,
                    'lon': 108.2274,
                    'verified': false,
                    'source': 'curated-snapshot',
                    'snapshot_version': 'danang-v1',
                    'price_state': 'unknown',
                  },
                ],
              }),
            ),
            200,
          );
        }),
      ),
    );

    final results = await repository.searchPois('cầu rồng');

    expect(requested?.path, '/v1/pois');
    expect(requested?.queryParameters['q'], 'cầu rồng');
    expect(results.single.id, 'bridge-1');
    expect(results.single.verified, isFalse);
    expect(results.single.snapshotVersion, 'danang-v1');
    expect(results.single.priceState, 'unknown');
  });

  test('details endpoint preserves explicit unknown evidence states', () async {
    final repository = HttpManagementRepository(
      ApiClient(
        baseUrl: 'http://example.test',
        client: MockClient((request) async {
          expect(request.url.path, '/v1/pois/bridge%2Fone');
          return http.Response.bytes(
            utf8.encode(
              jsonEncode({
                'poi_id': 'bridge/one',
                'name': 'Cầu Rồng',
                'type': 'landmark',
                'lat': 16.0611,
                'lon': 108.2274,
                'verified': true,
                'source': 'snapshot',
                'fetched_at': '2026-10-01T00:00:00Z',
                'snapshot_version': 'danang-v1',
                'opening_hours': [],
                'opening_hours_state': 'unknown',
                'price_state': 'unknown',
              }),
            ),
            200,
          );
        }),
      ),
    );

    final detail = await repository.getPoiDetails('bridge/one');

    expect(detail.verified, isTrue);
    expect(detail.openingHoursState, 'unknown');
    expect(detail.openingHours, isEmpty);
    expect(detail.priceState, 'unknown');
  });

  test('route preview retains road quality and GeoJSON coordinates', () async {
    final repository = HttpManagementRepository(
      ApiClient(
        baseUrl: 'http://example.test',
        client: MockClient((request) async {
          expect(request.method, 'POST');
          expect(request.url.path, '/v1/routes/preview');
          expect(jsonDecode(request.body), {
            'trip_id': 'trip-1',
            'activity_ids': ['activity-a', 'activity-b'],
            'mode': 'driving',
          });
          return http.Response.bytes(
            utf8.encode(
              jsonEncode({
                'quality': 'road_route',
                'source': 'osrm',
                'is_real_route': true,
                'geometry': {
                  'type': 'LineString',
                  'coordinates': [
                    [108.0, 16.0],
                    [108.1, 16.1],
                  ],
                },
                'distance_m': 1200,
                'duration_s': 300,
                'warning': null,
              }),
            ),
            200,
          );
        }),
      ),
    );

    final preview = await repository.previewRoute('trip-1', [
      'activity-a',
      'activity-b',
    ]);

    expect(preview.quality, 'road_route');
    expect(preview.isRealRoute, isTrue);
    expect(preview.geometry, [
      [108.0, 16.0],
      [108.1, 16.1],
    ]);
  });
}
