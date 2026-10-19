import 'dart:convert';

import 'package:davel_trace/api/client.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Minimal test-only widget: no app UI is touched by the API client test.
class _ExpenseProbe extends StatefulWidget {
  const _ExpenseProbe({required this.client});

  final ApiClient client;

  @override
  State<_ExpenseProbe> createState() => _ExpenseProbeState();
}

class _ExpenseProbeState extends State<_ExpenseProbe> {
  String _status = 'idle';

  Future<void> _submit() async {
    final entry = await widget.client.addExpense(
      tripId: 't1',
      label: 'Mì Quảng',
      amount: 120000,
      kind: 'food',
    );
    if (!mounted) return;
    setState(() {
      _status = '${entry.label}|${entry.amount}|${entry.kind}';
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Column(
          children: <Widget>[
            Text(_status),
            ElevatedButton(
              key: const Key('probe-submit'),
              onPressed: _submit,
              child: const Text('submit'),
            ),
          ],
        ),
      ),
    );
  }
}

void main() {
  testWidgets('ApiClient posts an expense and maps the typed response', (
    tester,
  ) async {
    http.Request? captured;
    final mock = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode(<String, Object?>{
          'trip_id': 't1',
          'label': 'Mì Quảng',
          'amount': 120000,
          'kind': 'food',
          'at': '2026-10-20T08:00:00',
        }),
        201,
        headers: <String, String>{'content-type': 'application/json'},
      );
    });
    final client = ApiClient(httpClient: mock, baseUrl: 'http://be.test/v1/');

    await tester.pumpWidget(_ExpenseProbe(client: client));
    await tester.tap(find.byKey(const Key('probe-submit')));
    await tester.pumpAndSettle();

    expect(captured, isNotNull);
    expect(captured!.method, 'POST');
    expect(captured!.url.toString(), 'http://be.test/v1/expenses');
    expect(captured!.headers['content-type'], 'application/json');
    expect(jsonDecode(captured!.body), <String, Object?>{
      'trip_id': 't1',
      'label': 'Mì Quảng',
      'amount': 120000,
      'kind': 'food',
    });
    expect(find.text('Mì Quảng|120000|food'), findsOneWidget);

    client.close();
  });

  test('parse decodes a flat TripRequest with its metadata lists', () async {
    final client = ApiClient(
      baseUrl: 'http://be.test/v1',
      httpClient: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://be.test/v1/parse');
        expect(jsonDecode(request.body), <String, Object?>{
          'text': 'cuối tuần đi Đà Nẵng 2 người 3 triệu thích biển',
          'user_id': 'u1',
        });
        return http.Response(
          jsonEncode(<String, Object?>{
            'trip_id': 't1',
            'user_id': 'u1',
            'city': 'da-nang',
            'start_time': '07:00',
            'end_time': '18:00',
            'days': 2,
            'travelers': 2,
            'budget': 3000000,
            'transport': <String>['motorbike'],
            'must_visit': <String>['be-man'],
            'avoid': <String>[],
            'activities': <String>['food'],
            'food_prefs': <String>['seafood'],
            'order_prefs': <List<String>>[],
            'assumptions': <String>['gio mac dinh 07:00-18:00'],
            'soft_prefs': <String>['thich bien'],
            'hard_constraints': <String>['budget 3 trieu'],
            'uncertainties': <String>[],
          }),
          200,
        );
      }),
    );

    final result = await client.parse(
      'cuối tuần đi Đà Nẵng 2 người 3 triệu thích biển',
      userId: 'u1',
    );

    expect(result.requiresClarification, isFalse);
    expect(result.trip, isNotNull);
    expect(result.trip!.city, 'da-nang');
    expect(result.trip!.days, 2);
    expect(result.trip!.mustVisit, <String>['be-man']);
    expect(result.assumptions, <String>['gio mac dinh 07:00-18:00']);
    expect(result.softPrefs, <String>['thich bien']);

    client.close();
  });

  test('itinerary keeps typed activity explanation evidence', () async {
    final client = ApiClient(
      baseUrl: 'http://be.test/v1',
      httpClient: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.toString(), 'http://be.test/v1/itinerary');
        return http.Response(
          jsonEncode(<String, Object?>{
            'selected': null,
            'plans': <Object?>[
              <String, Object?>{
                'itinerary_id': 'it-1',
                'trip_id': 't1',
                'activities': <Object?>[
                  <String, Object?>{
                    'poi_id': 'p1',
                    'start': '08:00',
                    'end': '09:00',
                    'explanation': <String, Object?>{
                      'claim': 'chon p1',
                      'evidence': <String>['seed:p1'],
                      'inference': '',
                      'source': 'rank',
                    },
                  },
                ],
                'scores': <String, Object?>{'profit': 0.9},
              },
            ],
          }),
          200,
        );
      }),
    );

    final result = await client.createItinerary(
      trip: TripRequest(),
      profiles: const <String>['balanced'],
    );

    expect(result.plans.single.activities.single.explanation?.claim, 'chon p1');
    expect(
      result.plans.single.activities.single.explanation?.evidence,
      <String>['seed:p1'],
    );

    client.close();
  });

  test('non-2xx envelope becomes a typed ApiException', () async {
    final client = ApiClient(
      baseUrl: 'http://be.test/v1',
      httpClient: MockClient((request) async {
        expect(request.method, 'GET');
        expect(
          request.url.toString(),
          'http://be.test/v1/itinerary/missing-id',
        );
        return http.Response(
          jsonEncode(<String, Object?>{
            'error': 'UNKNOWN_ITINERARY',
            'message': 'khong co plan missing-id',
          }),
          404,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }),
    );

    await expectLater(
      client.getItinerary('missing-id'),
      throwsA(
        isA<ApiException>()
            .having((error) => error.statusCode, 'statusCode', 404)
            .having((error) => error.code, 'code', 'UNKNOWN_ITINERARY')
            .having(
              (error) => error.message,
              'message',
              'khong co plan missing-id',
            ),
      ),
    );

    client.close();
  });
}
