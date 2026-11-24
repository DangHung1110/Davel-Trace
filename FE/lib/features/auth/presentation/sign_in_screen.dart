import 'package:flutter/material.dart';

import '../../../shared/widgets/field_cover.dart';
import '../application/auth_controller.dart';
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
  bool obscure = true;
  bool googleTermsAccepted = false;

  void _openRecovery({bool cancelDeletion = false}) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RecoveryScreen(
          controller: widget.controller,
          cancelDeletion: cancelDeletion,
        ),
      ),
    );
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
              TextField(
                controller: email,
                keyboardType: TextInputType.emailAddress,
                textInputAction: TextInputAction.next,
                autofillHints: const [AutofillHints.email],
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.mail_outline),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: password,
                obscureText: obscure,
                autofillHints: const [AutofillHints.password],
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
                onPressed: widget.controller.busy
                    ? null
                    : () => widget.controller.login(email.text, password.text),
                child: Text(
                  widget.controller.busy ? 'Đang xử lý…' : 'Đăng nhập',
                ),
              ),
              const SizedBox(height: 8),
              if (widget.controller.googleAvailable) ...[
                CheckboxListTile(
                  value: googleTermsAccepted,
                  onChanged: widget.controller.busy
                      ? null
                      : (value) => setState(
                          () => googleTermsAccepted = value ?? false,
                        ),
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  title: const Text(
                    'Tôi đồng ý điều khoản sử dụng khi tiếp tục bằng Google.',
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: widget.controller.busy || !googleTermsAccepted
                      ? null
                      : widget.controller.loginWithGoogle,
                  icon: const Icon(Icons.login),
                  label: const Text('Tiếp tục bằng Google'),
                ),
              ],
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
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: () => _openRecovery(cancelDeletion: true),
                  child: const Text(
                    'Khôi phục tài khoản đang chờ xóa',
                    textAlign: TextAlign.start,
                  ),
                ),
              ),
              const Divider(height: 32),
              OutlinedButton.icon(
                onPressed: widget.controller.continueDemo,
                icon: const Icon(Icons.science_outlined),
                label: const Text('Tiếp tục với dữ liệu demo'),
              ),
              const SizedBox(height: 8),
              const Text(
                'Dữ liệu demo chỉ lưu trên thiết bị này.',
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
