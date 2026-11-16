abstract interface class AuthSessionStore {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String value);
  Future<void> clear();
}

class MemoryAuthSessionStore implements AuthSessionStore {
  String? _value;

  @override
  Future<void> clear() async => _value = null;

  @override
  Future<String?> readRefreshToken() async => _value;

  @override
  Future<void> writeRefreshToken(String value) async => _value = value;
}
