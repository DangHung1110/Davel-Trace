import 'package:flutter/material.dart';

import '../application/auth_controller.dart';
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
      AuthStatus.authenticated => authenticatedChild ?? child,
    },
  );
}
