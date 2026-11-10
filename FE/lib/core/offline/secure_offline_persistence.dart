import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'offline_persistence.dart';

class SecureOfflinePersistence implements OfflinePersistence {
  const SecureOfflinePersistence({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _prefix = 'davel_trace_offline_v1_';
  final FlutterSecureStorage _storage;

  String _key(String accountId) => '$_prefix$accountId';

  @override
  Future<void> delete(String accountId) =>
      _storage.delete(key: _key(accountId));

  @override
  Future<String?> read(String accountId) => _storage.read(key: _key(accountId));

  @override
  Future<void> write(String accountId, String value) =>
      _storage.write(key: _key(accountId), value: value);
}
