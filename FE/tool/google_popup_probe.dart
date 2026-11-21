// Browser regression probe for the production popup predicate, without Flutter's
// CanvasKit-dependent browser test host. Compile/run instructions: spec 013.
import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

import 'package:davel_trace/features/auth/data/google_sign_in_web.dart';

Future<void> main() async {
  final frame = web.HTMLIFrameElement();
  frame.setAttribute('sandbox', 'allow-scripts');
  final received = Completer<web.MessageEvent>();
  final listener = ((web.MessageEvent event) {
    final data = event.data.dartify();
    if (data is Map &&
        data['type'] == 'davel.google' &&
        !received.isCompleted) {
      received.complete(event);
    }
  }).toJS;
  web.window.addEventListener('message', listener);
  frame.srcdoc = '<script>parent.postMessage({type:"davel.google",handoff:"test-only"},"*");</script>'
      .toJS;
  web.document.body!.append(frame);
  try {
    final event = await received.future.timeout(const Duration(seconds: 10));
    final checks = {
      'opaque_cross_origin_frame': event.origin == 'null',
      'correct_source_accepted': isGooglePopupMessage(
        event,
        frame.contentWindow,
        'null',
      ),
      'wrong_origin_rejected': !isGooglePopupMessage(
        event,
        frame.contentWindow,
        'https://other.example',
      ),
      'wrong_source_rejected': !isGooglePopupMessage(event, web.window, 'null'),
    };
    web.document.body!.textContent = jsonEncode({
      'passed': checks.values.every((v) => v),
      'checks': checks,
    });
  } catch (error) {
    web.document.body!.textContent = jsonEncode({
      'passed': false,
      'error_type': error.runtimeType.toString(),
    });
  } finally {
    web.window.removeEventListener('message', listener);
    frame.remove();
  }
}
