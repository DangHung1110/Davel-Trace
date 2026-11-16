abstract interface class OfflinePersistence {
  Future<String?> read(String accountId);
  Future<void> write(String accountId, String value);
  Future<void> delete(String accountId);
}
