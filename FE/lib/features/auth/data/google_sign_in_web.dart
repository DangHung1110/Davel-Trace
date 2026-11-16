import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

import '../../../core/config/api_config.dart';
import '../../../core/errors/api_exception.dart';
import '../../../core/networking/api_client.dart';
import '../domain/models.dart';

const supportsGoogleSignIn = true;

bool isGooglePopupMessage(
  web.MessageEvent event,
  web.Window? popup,
  String origin,
) =>
    popup != null &&
    event.origin == origin &&
    event.source.strictEquals(popup).toDart;

Future<AuthTokens> signInWithGoogle({String? authorizationOrigin}) async {
  // Begin on the callback host, even if ordinary API calls use 127.0.0.1.
  // Otherwise a localhost callback cannot receive a 127.0.0.1 state cookie.
  final apiOrigin = Uri.parse(authorizationOrigin ?? ApiConfig.baseUrl).origin;
  final start = Uri.parse('$apiOrigin/v1/auth/google/start').replace(
    queryParameters: {
      'origin': web.window.location.origin,
      'terms_accepted': 'true',
    },
  );
  final result = Completer<String>();
  web.Window? popup;
  final listener = ((web.MessageEvent event) {
    if (!isGooglePopupMessage(event, popup, apiOrigin) || result.isCompleted) {
      return;
    }
    final data = event.data.dartify();
    if (data is! Map || data['type'] != 'davel.google') return;
    if (data['handoff'] is String) {
      result.complete(data['handoff'] as String);
    } else if (data['error'] is String) {
      result.completeError(
        ApiException(
          data['error'] as String,
          data['message'] as String? ?? 'Không đăng nhập được Google.',
        ),
      );
    }
  }).toJS;
  web.window.addEventListener('message', listener);
  Timer? closed;
  try {
    // Open synchronously from the click handler so browser popup rules allow it.
    popup = web.window.open(
      start.toString(),
      '_blank',
      'popup,width=520,height=700',
    );
    if (popup == null) {
      throw ApiException(
        'POPUP_BLOCKED',
        'Hãy cho phép cửa sổ bật lên để đăng nhập Google.',
      );
    }
    closed = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (popup!.closed && !result.isCompleted) {
        result.completeError(
          ApiException('GOOGLE_CANCELLED', 'Cửa sổ đăng nhập Google đã đóng.'),
        );
      }
    });
    final handoff = await result.future.timeout(
      const Duration(minutes: 5),
      onTimeout: () => throw ApiException(
        'GOOGLE_TIMEOUT',
        'Đăng nhập Google đã hết thời gian. Hãy thử lại.',
      ),
    );
    final payload = await ApiClient().post(
      '/v1/auth/google/exchange',
      body: {'handoff': handoff},
    ) as Map<String, dynamic>;
    return AuthTokens.fromJson(payload);
  } finally {
    closed?.cancel();
    web.window.removeEventListener('message', listener);
    popup?.close();
  }
}
