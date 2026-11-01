import 'package:flutter/material.dart';

import '../application/auth_controller.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.controller});
  final AuthController controller;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final confirm = TextEditingController();
  bool accepted = false;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Tạo tài khoản')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          TextField(
            controller: email,
            decoration: const InputDecoration(labelText: 'Email'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: password,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'Mật khẩu (ít nhất 10 ký tự, có chữ và số)',
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: confirm,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Nhập lại mật khẩu'),
          ),
          CheckboxListTile(
            value: accepted,
            contentPadding: EdgeInsets.zero,
            onChanged: (value) => setState(() => accepted = value ?? false),
            title: const Text(
              'Tôi đồng ý điều khoản sử dụng cho bản demo học tập.',
            ),
          ),
          if (widget.controller.errorMessage != null)
            Text(
              widget.controller.errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: !accepted || widget.controller.busy
                ? null
                : () async {
                    if (password.text != confirm.text) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Mật khẩu nhập lại chưa khớp.'),
                        ),
                      );
                      return;
                    }
                    await widget.controller.register(email.text, password.text);
                    if (context.mounted &&
                        widget.controller.status ==
                            AuthStatus.verificationRequired) {
                      Navigator.pop(context);
                    }
                  },
            child: const Text('Đăng ký'),
          ),
        ],
      ),
    ),
  );
}
