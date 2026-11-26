import 'dart:async';

import 'package:flutter/material.dart';

import '../application/auth_controller.dart';

class GoogleContinueButton extends StatelessWidget {
  const GoogleContinueButton({
    super.key,
    required this.controller,
    this.onAuthenticated,
  });

  final AuthController controller;
  final VoidCallback? onAuthenticated;

  Future<void> _login(BuildContext context) async {
    await controller.loginWithGoogle();
    if (context.mounted && controller.status == AuthStatus.authenticated) {
      onAuthenticated?.call();
    }
  }

  void _showConsent(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        scrollable: true,
        title: const Text('Tiếp tục bằng Google'),
        content: const Text(
          'Bằng cách tiếp tục, bạn đồng ý với điều khoản sử dụng Davel Trace. '
          'Nếu đây là lần đầu, app sẽ tạo tài khoản bằng email Google của bạn.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Quay lại'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              // Start within the click so the browser allows the popup.
              unawaited(_login(context));
            },
            child: const Text('Đồng ý và tiếp tục'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!controller.googleAvailable) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(
          'Google tạm thời chưa khả dụng. Bạn có thể dùng email.',
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
        ),
      );
    }
    return OutlinedButton.icon(
      onPressed: controller.busy ? null : () => _showConsent(context),
      icon: const Icon(Icons.account_circle_outlined),
      label: const Text('Tiếp tục bằng Google'),
    );
  }
}
