import 'package:flutter/material.dart';

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
            padding: const EdgeInsets.fromLTRB(24, 40, 24, 24),
            children: [
              const Icon(Icons.explore_rounded, size: 52),
              const SizedBox(height: 16),
              Text(
                'Davel Trace',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineMedium
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              const Text(
                'Quản lý chuyến đi Đà Nẵng gọn gàng, rõ ràng.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 28),
              TextField(
                controller: email,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.mail_outline),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: password,
                obscureText: obscure,
                decoration: InputDecoration(
                  labelText: 'Mật khẩu',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
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
              TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        RegisterScreen(controller: widget.controller),
                  ),
                ),
                child: const Text('Tạo tài khoản'),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        RecoveryScreen(controller: widget.controller),
                  ),
                ),
                child: const Text('Quên mật khẩu?'),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => RecoveryScreen(
                      controller: widget.controller,
                      cancelDeletion: true,
                    ),
                  ),
                ),
                child: const Text('Khôi phục tài khoản đang chờ xóa'),
              ),
              const Divider(height: 32),
              OutlinedButton.icon(
                onPressed: widget.controller.continueDemo,
                icon: const Icon(Icons.science_outlined),
                label: const Text('Tiếp tục với dữ liệu demo'),
              ),
              const SizedBox(height: 8),
              const Text(
                'Dữ liệu demo chỉ nằm trên thiết bị và không giả là dữ liệu tài khoản.',
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
