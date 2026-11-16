import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'auth_session_store.dart';

class SecureAuthSessionStore implements AuthSessionStore {
  const SecureAuthSessionStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'davel_trace_refresh_token';
  final FlutterSecureStorage _storage;

  @override
  Future<void> clear() => _storage.delete(key: _key);

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _key);

  @override
  Future<void> writeRefreshToken(String value) =>
      _storage.write(key: _key, value: value);
}
