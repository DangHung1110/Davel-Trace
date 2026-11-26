import 'dart:async';

import 'package:flutter/material.dart';

import '../../../shared/widgets/field_cover.dart';
import '../application/auth_controller.dart';
import 'google_continue_button.dart';
import 'recovery_screen.dart';
import 'register_screen.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.controller});
  final AuthController controller;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final _form = GlobalKey<FormState>();
  bool obscure = true;

  void _openRecovery() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RecoveryScreen(controller: widget.controller),
      ),
    );
  }

  void _login() {
    if (widget.controller.busy || !_form.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    unawaited(widget.controller.login(email.text.trim(), password.text));
  }

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
            children: [
              const FieldCover(
                compact: true,
                title: 'Davel Trace',
                description: 'Lập lịch và khám phá Đà Nẵng.',
              ),
              const SizedBox(height: 20),
              AutofillGroup(
                child: Form(
                  key: _form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      TextFormField(
                        controller: email,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.next,
                        autofillHints: const [AutofillHints.email],
                        validator: (value) => (value ?? '').trim().isEmpty
                            ? 'Nhập email của bạn.'
                            : null,
                        decoration: const InputDecoration(
                          labelText: 'Email',
                          prefixIcon: Icon(Icons.mail_outline),
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: password,
                        obscureText: obscure,
                        autofillHints: const [AutofillHints.password],
                        textInputAction: TextInputAction.done,
                        onFieldSubmitted: (_) => _login(),
                        validator: (value) => (value ?? '').isEmpty
                            ? 'Nhập mật khẩu của bạn.'
                            : null,
                        decoration: InputDecoration(
                          labelText: 'Mật khẩu',
                          prefixIcon: const Icon(Icons.lock_outline),
                          suffixIcon: IconButton(
                            tooltip: obscure ? 'Hiện mật khẩu' : 'Ẩn mật khẩu',
                            onPressed: () => setState(() => obscure = !obscure),
                            icon: Icon(
                              obscure
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (widget.controller.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  widget.controller.errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              if (widget.controller.message != null) ...[
                const SizedBox(height: 12),
                Text(widget.controller.message!),
              ],
              const SizedBox(height: 20),
              FilledButton(
                onPressed: widget.controller.busy ? null : _login,
                child: Text(
                  widget.controller.busy ? 'Đang xử lý…' : 'Đăng nhập',
                ),
              ),
              const SizedBox(height: 8),
              if (widget.controller.googlePlatformAvailable)
                GoogleContinueButton(controller: widget.controller),
              OverflowBar(
                alignment: MainAxisAlignment.spaceBetween,
                overflowAlignment: OverflowBarAlignment.start,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) =>
                            RegisterScreen(controller: widget.controller),
                      ),
                    ),
                    child: const Text('Tạo tài khoản'),
                  ),
                  TextButton(
                    onPressed: _openRecovery,
                    child: const Text('Quên mật khẩu?'),
                  ),
                ],
              ),
              const Divider(height: 32),
              TextButton(
                onPressed: widget.controller.continueDemo,
                child: const Text('Xem thử chuyến đi mẫu'),
              ),
              const SizedBox(height: 8),
              const Text(
                'Thay đổi khi xem thử chỉ lưu trên thiết bị này.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
