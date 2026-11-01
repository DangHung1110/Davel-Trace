import 'dart:convert';

import 'package:davel_trace/core/errors/api_exception.dart';
import 'package:davel_trace/core/networking/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('sends a correlation ID and maps a flat backend error', () async {
    String? sentCorrelation;
    final client = MockClient((request) async {
      sentCorrelation = request.headers['X-Correlation-ID'];
      return http.Response.bytes(
        utf8.encode(
          jsonEncode({
            'error': 'DATABASE_UNAVAILABLE',
            'message': 'Dữ liệu tạm thời không khả dụng.',
          }),
        ),
        503,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'X-Correlation-ID': 'server-correlation-1234',
        },
      );
    });
    final api = ApiClient(client: client, baseUrl: 'http://example.test');

    ApiException? failure;
    try {
      await api.get('/v1/ready');
    } on ApiException catch (error) {
      failure = error;
    }

    expect(sentCorrelation, startsWith('mobile-'));
    expect(failure?.code, 'DATABASE_UNAVAILABLE');
    expect(failure?.category, ApiFailureCategory.dependency);
    expect(failure?.correlationId, 'server-correlation-1234');
  });

  test('keeps nested error compatibility and classifies validation', () async {
    final client = MockClient(
      (_) async => http.Response.bytes(
        utf8.encode(
          jsonEncode({
            'error': {'code': 'VALIDATION_ERROR', 'message': 'Thiếu dữ liệu.'},
          }),
        ),
        422,
        headers: {'Content-Type': 'application/json; charset=utf-8'},
      ),
    );
    final api = ApiClient(client: client, baseUrl: 'http://example.test');

    await expectLater(
      api.post('/v1/trips', body: const {}),
      throwsA(
        isA<ApiException>()
            .having((error) => error.code, 'code', 'VALIDATION_ERROR')
            .having(
              (error) => error.category,
              'category',
              ApiFailureCategory.validation,
            ),
      ),
    );
  });
}
