import 'package:flutter/foundation.dart';

import '../../../core/auth/auth_session_store.dart';
import '../../../core/auth/secure_auth_session_store.dart';
import '../../../core/errors/api_exception.dart';
import '../data/auth_repository.dart';
import '../data/http_auth_repository.dart';
import '../domain/models.dart';

enum AuthStatus {
  initializing,
  signedOut,
  verificationRequired,
  authenticated,
  demo,
}

class AuthController extends ChangeNotifier {
  AuthController({AuthRepository? repository, AuthSessionStore? sessionStore})
    : repository = repository ?? HttpAuthRepository(),
      sessionStore = sessionStore ?? const SecureAuthSessionStore();

  final AuthRepository repository;
  final AuthSessionStore sessionStore;
  AuthStatus status = AuthStatus.initializing;
  AccountSummary? account;
  String? pendingEmail;
  String? message;
  String? errorMessage;
  bool busy = false;

  Future<void> initialize() async {
    repository.setRefreshHandler(_refreshAfterUnauthorized);
    final token = await sessionStore.readRefreshToken();
    if (token == null) {
      status = AuthStatus.signedOut;
      notifyListeners();
      return;
    }
    try {
      await _accept(await repository.refresh(token));
    } catch (_) {
      await sessionStore.clear();
      repository.setAccessToken(null);
      status = AuthStatus.signedOut;
      notifyListeners();
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    busy = true;
    errorMessage = null;
    message = null;
    notifyListeners();
    try {
      await action();
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Có lỗi không mong muốn. Hãy thử lại.';
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> _accept(AuthTokens tokens) async {
    repository.setAccessToken(tokens.accessToken);
    await sessionStore.writeRefreshToken(tokens.refreshToken);
    account = tokens.account;
    status = AuthStatus.authenticated;
  }

  Future<String?> _refreshAfterUnauthorized() async {
    final refreshToken = await sessionStore.readRefreshToken();
    if (refreshToken == null) return null;
    try {
      final tokens = await repository.refresh(refreshToken);
      await _accept(tokens);
      return tokens.accessToken;
    } catch (_) {
      await sessionStore.clear();
      repository.setAccessToken(null);
      account = null;
      status = AuthStatus.signedOut;
      notifyListeners();
      return null;
    }
  }

  Future<void> register(String email, String password) => _run(() async {
    await repository.register(email, password);
    pendingEmail = email.trim().toLowerCase();
    status = AuthStatus.verificationRequired;
    message = 'Tài khoản đã tạo. Hãy xác thực email để đăng nhập.';
  });

  Future<void> verify(String token) => _run(() async {
    await repository.verify(token);
    status = AuthStatus.signedOut;
    message = 'Xác thực thành công. Bạn có thể đăng nhập.';
  });

  Future<String?> loadDevelopmentToken(String purpose) async {
    final email = pendingEmail;
    if (email == null) return null;
    try {
      return await repository.developmentToken(email, purpose);
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Không lấy được mã demo.';
      notifyListeners();
      return null;
    }
  }

  Future<void> login(String email, String password) => _run(() async {
    await _accept(await repository.login(email, password));
  });

  Future<void> requestRecovery(String email) => _run(() async {
    pendingEmail = email.trim().toLowerCase();
    await repository.requestRecovery(email);
    message = 'Nếu tài khoản hợp lệ, hướng dẫn khôi phục đã được tạo.';
  });

  Future<void> resetPassword(String token, String password) => _run(() async {
    await repository.resetPassword(token, password);
    status = AuthStatus.signedOut;
    message = 'Đổi mật khẩu thành công. Hãy đăng nhập lại.';
  });

  Future<void> requestDeletionCancel(String email) => _run(() async {
    pendingEmail = email.trim().toLowerCase();
    await repository.requestDeletionCancel(email);
    message = 'Nếu tài khoản đang chờ xóa, mã khôi phục đã được tạo.';
  });

  Future<void> confirmDeletionCancel(String token) => _run(() async {
    await repository.confirmDeletionCancel(token);
    status = AuthStatus.signedOut;
    message = 'Đã khôi phục tài khoản. Hãy đăng nhập lại.';
  });

  void continueDemo() {
    status = AuthStatus.demo;
    errorMessage = null;
    message = 'Dữ liệu demo trên thiết bị — chưa lưu vào tài khoản.';
    notifyListeners();
  }

  Future<void> logout() => _run(() async {
    try {
      await repository.logout();
    } finally {
      await sessionStore.clear();
      repository.setAccessToken(null);
      account = null;
      status = AuthStatus.signedOut;
    }
  });

  Future<Map<String, dynamic>?> createExport(String password) async {
    Map<String, dynamic>? result;
    await _run(() async => result = await repository.createExport(password));
    return result;
  }

  Future<void> deleteAccount(String password) => _run(() async {
    await repository.deleteAccount(password);
    await sessionStore.clear();
    repository.setAccessToken(null);
    account = null;
    status = AuthStatus.signedOut;
    message = 'Tài khoản đang chờ xóa trong 30 ngày. Các phiên đã bị thu hồi.';
  });
}
