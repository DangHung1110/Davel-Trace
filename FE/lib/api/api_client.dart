import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'api_exception.dart';

class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  final http.Client _client;
  final String _baseUrl;

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
    late http.Response response;
    try {
      final headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
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
    } catch (_) {
      throw const ApiException(
        'NETWORK_ERROR',
        'Không kết nối được API. Hãy chạy backend tại http://127.0.0.1:8000.',
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
      final error = payload is Map<String, dynamic>
          ? payload['error'] as Map<String, dynamic>?
          : null;
      throw ApiException(
        error?['code'] as String? ?? 'HTTP_${response.statusCode}',
        error?['message'] as String? ?? 'Yêu cầu không thành công.',
        statusCode: response.statusCode,
      );
    }
    return payload;
  }
}
