import '../domain/models.dart';

abstract interface class AuthRepository {
  Future<void> register(String email, String password);
  Future<void> verify(String token);
  Future<AuthTokens> login(String email, String password);
  Future<AuthTokens> refresh(String refreshToken);
  Future<void> requestRecovery(String email);
  Future<void> requestDeletionCancel(String email);
  Future<void> confirmDeletionCancel(String token);
  Future<void> resetPassword(String token, String password);
  Future<String> developmentToken(String email, String purpose);
  Future<AccountSummary> me();
  Future<List<IdentitySession>> sessions();
  Future<void> logout();
  Future<void> revokeSession(String id);
  Future<Map<String, dynamic>> createExport(String password);
  Future<void> deleteAccount(String password);
  void setAccessToken(String? value);
  void setRefreshHandler(Future<String?> Function()? handler);
}
