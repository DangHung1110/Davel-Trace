import 'package:davel_trace/core/auth/auth_session_store.dart';
import 'package:davel_trace/features/auth/application/auth_controller.dart';
import 'package:davel_trace/features/auth/data/auth_repository.dart';
import 'package:davel_trace/features/auth/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  String? access;
  String? registeredEmail;
  String? deletionCancelEmail;
  String? deletionCancelToken;
  String? exportPassword;
  final account = const AccountSummary(
    id: 'account-1',
    email: 'demo@example.com',
    status: 'active',
    roles: ['traveler'],
  );

  @override
  Future<String> developmentToken(String email, String purpose) async =>
      'dev-token';
  @override
  Future<AuthTokens> login(String email, String password) async => AuthTokens(
    account: account,
    accessToken: 'access',
    refreshToken: 'refresh',
  );
  @override
  Future<AccountSummary> me() async => account;
  @override
  Future<AuthTokens> refresh(String refreshToken) async => AuthTokens(
    account: account,
    accessToken: 'access-2',
    refreshToken: 'refresh-2',
  );
  @override
  Future<void> register(String email, String password) async =>
      registeredEmail = email;
  @override
  Future<void> requestRecovery(String email) async {}
  @override
  Future<void> requestDeletionCancel(String email) async =>
      deletionCancelEmail = email;
  @override
  Future<void> confirmDeletionCancel(String token) async =>
      deletionCancelToken = token;
  @override
  Future<void> resetPassword(String token, String password) async {}
  @override
  Future<void> revokeSession(String id) async {}
  @override
  Future<List<IdentitySession>> sessions() async => const [];
  @override
  void setAccessToken(String? value) => access = value;
  @override
  void setRefreshHandler(Future<String?> Function()? handler) {}
  @override
  Future<void> verify(String token) async {}
  @override
  Future<void> logout() async {}
  @override
  Future<Map<String, dynamic>> createExport(String password) async {
    exportPassword = password;
    return {
      'checksum': List.filled(64, 'a').join(),
      'payload': {
        'account': {'email': account.email},
      },
    };
  }

  @override
  Future<void> deleteAccount(String password) async {}
}

void main() {
  test('starts signed out then registers and verifies', () async {
    final repository = FakeAuthRepository();
    final controller = AuthController(
      repository: repository,
      sessionStore: MemoryAuthSessionStore(),
    );
    await controller.initialize();
    expect(controller.status, AuthStatus.signedOut);
    await controller.register('demo@example.com', 'TravelDemo123');
    expect(controller.status, AuthStatus.verificationRequired);
    expect(controller.pendingEmail, 'demo@example.com');
    await controller.verify('dev-token');
    expect(controller.status, AuthStatus.signedOut);
  });

  test('login stores refresh and startup rotates it', () async {
    final repository = FakeAuthRepository();
    final store = MemoryAuthSessionStore();
    final controller = AuthController(
      repository: repository,
      sessionStore: store,
    );
    await controller.initialize();
    await controller.login('demo@example.com', 'TravelDemo123');
    expect(controller.status, AuthStatus.authenticated);
    expect(repository.access, 'access');
    expect(await store.readRefreshToken(), 'refresh');

    final restarted = AuthController(
      repository: repository,
      sessionStore: store,
    );
    await restarted.initialize();
    expect(restarted.status, AuthStatus.authenticated);
    expect(await store.readRefreshToken(), 'refresh-2');
  });

  test('demo mode stays explicitly separate', () async {
    final controller = AuthController(
      repository: FakeAuthRepository(),
      sessionStore: MemoryAuthSessionStore(),
    );
    await controller.initialize();
    controller.continueDemo();
    expect(controller.status, AuthStatus.demo);
    expect(controller.message, contains('demo'));
  });

  test('account deletion clears credentials and returns to sign in', () async {
    final repository = FakeAuthRepository();
    final store = MemoryAuthSessionStore();
    final controller = AuthController(
      repository: repository,
      sessionStore: store,
    );
    await controller.initialize();
    await controller.login('demo@example.com', 'TravelDemo123');
    await controller.deleteAccount('TravelDemo123');
    expect(controller.status, AuthStatus.signedOut);
    expect(await store.readRefreshToken(), isNull);
    expect(repository.access, isNull);
  });

  test(
    'signed-out lifecycle recovery and export keep explicit inputs',
    () async {
      final repository = FakeAuthRepository();
      final controller = AuthController(
        repository: repository,
        sessionStore: MemoryAuthSessionStore(),
      );
      await controller.initialize();
      await controller.requestDeletionCancel('demo@example.com');
      await controller.confirmDeletionCancel('cancel-token');
      expect(repository.deletionCancelEmail, 'demo@example.com');
      expect(repository.deletionCancelToken, 'cancel-token');

      final exported = await controller.createExport('TravelDemo123');
      expect(repository.exportPassword, 'TravelDemo123');
      expect(exported?['payload'], isA<Map<String, dynamic>>());
    },
  );
}
