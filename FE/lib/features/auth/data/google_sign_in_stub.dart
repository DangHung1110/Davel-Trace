import '../../../core/errors/api_exception.dart';
import '../domain/models.dart';

const supportsGoogleSignIn = false;

Future<AuthTokens> signInWithGoogle({String? authorizationOrigin}) async =>
    throw ApiException(
      'GOOGLE_WEB_ONLY',
      'Đăng nhập Google hiện hỗ trợ bản web. Hãy dùng email và mật khẩu trên thiết bị này.',
    );
