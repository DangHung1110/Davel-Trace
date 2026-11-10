import 'package:davel_trace/core/offline/offline.dart';

class MemoryOfflinePersistence implements OfflinePersistence {
  final Map<String, String> values = {};

  @override
  Future<void> delete(String accountId) async => values.remove(accountId);

  @override
  Future<String?> read(String accountId) async => values[accountId];

  @override
  Future<void> write(String accountId, String value) async {
    values[accountId] = value;
  }
}
