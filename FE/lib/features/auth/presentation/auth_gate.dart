import 'package:flutter/material.dart';

import '../application/auth_controller.dart';
import 'security_screen.dart';
import 'sign_in_screen.dart';
import 'verify_screen.dart';

class AuthGate extends StatelessWidget {
  const AuthGate({
    super.key,
    required this.controller,
    required this.child,
    this.authenticatedChild,
  });
  final AuthController controller;
  final Widget child;
  final Widget? authenticatedChild;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => switch (controller.status) {
      AuthStatus.initializing => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      AuthStatus.signedOut => SignInScreen(controller: controller),
      AuthStatus.verificationRequired => VerifyScreen(controller: controller),
      AuthStatus.demo => child,
      AuthStatus.authenticated => Scaffold(
        body: Column(
          children: [
            Material(
              color: Theme.of(context).colorScheme.primaryContainer,
              child: SafeArea(
                bottom: false,
                child: ListTile(
                  dense: true,
                  leading: const Icon(Icons.verified_user_outlined),
                  title: Text(controller.account?.email ?? 'Tài khoản'),
                  subtitle: const Text(
                    'Đã đăng nhập · hồ sơ và chuyến đi được lưu trên tài khoản',
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.manage_accounts_outlined),
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => SecurityScreen(controller: controller),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            Expanded(child: authenticatedChild ?? child),
          ],
        ),
      ),
    },
  );
}
