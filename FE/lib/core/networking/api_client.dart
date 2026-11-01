import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../errors/api_exception.dart';
import '../observability/correlation_id.dart';

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  final http.Client _client;
  final String _baseUrl;

  String? _header(Map<String, String> headers, String name) {
    final wanted = name.toLowerCase();
    for (final entry in headers.entries) {
      if (entry.key.toLowerCase() == wanted) return entry.value;
    }
    return null;
  }

  Future<dynamic> get(String path, {Map<String, String>? query}) =>
      _send('GET', path, query: query);

  Future<dynamic> post(String path, {Object? body}) =>
      _send('POST', path, body: body);

  Future<dynamic> patch(String path, {Object? body}) =>
      _send('PATCH', path, body: body);

  Future<dynamic> put(String path, {Object? body}) =>
      _send('PUT', path, body: body);

  Future<dynamic> delete(String path, {Map<String, String>? query}) =>
      _send('DELETE', path, query: query);

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
  }) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    final correlationId = CorrelationId.create();
    late http.Response response;
    try {
      final headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Correlation-ID': correlationId,
      };
      response = switch (method) {
        'GET' => await _client.get(uri, headers: headers),
        'POST' => await _client.post(
          uri,
          headers: headers,
          body: jsonEncode(body),
        ),
        'PATCH' => await _client.patch(
          uri,
          headers: headers,
          body: jsonEncode(body),
        ),
        'PUT' => await _client.put(
          uri,
          headers: headers,
          body: jsonEncode(body),
        ),
        'DELETE' => await _client.delete(uri, headers: headers),
        _ => throw StateError('Unsupported method $method'),
      };
    } on http.ClientException {
      throw ApiException(
        'NETWORK_ERROR',
        'Không kết nối được API. Hãy chạy backend tại http://127.0.0.1:8000.',
        correlationId: correlationId,
      );
    }

    if (response.statusCode == 204) return null;
    dynamic payload;
    try {
      payload = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      payload = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final map = payload is Map<String, dynamic> ? payload : null;
      final nested = map?['error'] is Map<String, dynamic>
          ? map!['error'] as Map<String, dynamic>
          : null;
      final flatCode = map?['error'] is String ? map!['error'] as String : null;
      throw ApiException(
        nested?['code'] as String? ?? flatCode ?? 'HTTP_${response.statusCode}',
        nested?['message'] as String? ??
            map?['message'] as String? ??
            'Yêu cầu không thành công.',
        statusCode: response.statusCode,
        correlationId:
            _header(response.headers, 'X-Correlation-ID') ??
            map?['correlation_id'] as String? ??
            correlationId,
      );
    }
    return payload;
  }
}
