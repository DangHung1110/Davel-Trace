import '../../../core/networking/api_client.dart';
import '../domain/models.dart';
import 'auth_repository.dart';

class HttpAuthRepository implements AuthRepository {
  HttpAuthRepository({ApiClient? client}) : _client = client ?? ApiClient();
  final ApiClient _client;

  @override
  void setAccessToken(String? value) => _client.accessToken = value;

  @override
  void setRefreshHandler(Future<String?> Function()? handler) =>
      _client.onUnauthorized = handler;

  @override
  Future<void> register(String email, String password) async {
    await _client.post(
      '/v1/auth/register',
      body: {'email': email, 'password': password, 'terms_accepted': true},
    );
  }

  @override
  Future<void> verify(String token) async =>
      _client.post('/v1/auth/verification/confirm', body: {'token': token});

  @override
  Future<AuthTokens> login(String email, String password) async =>
      AuthTokens.fromJson(
        await _client.post(
          '/v1/auth/login',
          body: {
            'email': email,
            'password': password,
            'device_label': 'Davel Trace Web',
            'client_kind': 'web',
          },
        ) as Map<String, dynamic>,
      );

  @override
  Future<AuthTokens> refresh(String refreshToken) async => AuthTokens.fromJson(
    await _client.post(
      '/v1/auth/refresh',
      body: {'refresh_token': refreshToken},
    ) as Map<String, dynamic>,
  );

  @override
  Future<void> requestRecovery(String email) async =>
      _client.post('/v1/auth/recovery/request', body: {'email': email});

  @override
  Future<void> requestDeletionCancel(String email) async =>
      _client.post('/v1/auth/deletion-cancel/request', body: {'email': email});

  @override
  Future<void> confirmDeletionCancel(String token) async =>
      _client.post('/v1/auth/deletion-cancel/confirm', body: {'token': token});

  @override
  Future<void> resetPassword(String token, String password) async =>
      _client.post(
        '/v1/auth/recovery/confirm',
        body: {'token': token, 'new_password': password},
      );

  @override
  Future<String> developmentToken(String email, String purpose) async {
    final json = await _client.get(
      '/v1/dev/identity/outbox',
      query: {'email': email, 'purpose': purpose},
    ) as Map<String, dynamic>;
    return json['token'] as String;
  }

  @override
  Future<AccountSummary> me() async => AccountSummary.fromJson(
    await _client.get('/v1/account/me') as Map<String, dynamic>,
  );

  @override
  Future<List<IdentitySession>> sessions() async {
    final json =
        await _client.get('/v1/account/sessions') as Map<String, dynamic>;
    return (json['items'] as List<dynamic>)
        .map((item) => IdentitySession.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> logout() async => _client.post('/v1/account/logout');

  @override
  Future<void> revokeSession(String id) async =>
      _client.delete('/v1/account/sessions/$id');

  @override
  Future<Map<String, dynamic>> createExport(String password) async =>
      await _client.post(
        '/v1/account/exports',
        body: {'current_password': password, 'confirmation': 'XUẤT DỮ LIỆU'},
      ) as Map<String, dynamic>;

  @override
  Future<void> deleteAccount(String password) async => _client.post(
    '/v1/account/deletion',
    body: {'current_password': password, 'confirmation': 'XÓA TÀI KHOẢN'},
  );
}
