import 'package:flutter/material.dart';

import '../application/auth_controller.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key, required this.controller});
  final AuthController controller;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  final confirm = TextEditingController();
  bool accepted = false;
  bool hidePassword = true;

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!accepted || widget.controller.busy || !form.currentState!.validate()) {
      return;
    }
    FocusScope.of(context).unfocus();
    await widget.controller.register(email.text.trim(), password.text);
    if (mounted &&
        widget.controller.status == AuthStatus.verificationRequired) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (_, _) => Scaffold(
      appBar: AppBar(title: const Text('Tạo tài khoản')),
      body: SafeArea(
        child: AutofillGroup(
          child: Form(
            key: form,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Dùng email để lưu và mở lại chuyến đi của bạn.'),
                  const SizedBox(height: 18),
                  TextFormField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(labelText: 'Email'),
                    validator: (value) =>
                        RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                            .hasMatch((value ?? '').trim())
                        ? null
                        : 'Nhập địa chỉ email hợp lệ.',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: password,
                    obscureText: hidePassword,
                    textInputAction: TextInputAction.next,
                    autofillHints: const [AutofillHints.newPassword],
                    decoration: InputDecoration(
                      labelText: 'Mật khẩu',
                      helperText: '10–128 ký tự, có chữ và số.',
                      helperMaxLines: 2,
                      suffixIcon: IconButton(
                        tooltip: hidePassword ? 'Hiện mật khẩu' : 'Ẩn mật khẩu',
                        onPressed: () =>
                            setState(() => hidePassword = !hidePassword),
                        icon: Icon(
                          hidePassword
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                      ),
                    ),
                    validator: (value) {
                      final length = (value ?? '').runes.length;
                      return length < 10 || length > 128
                          ? 'Mật khẩu cần từ 10 đến 128 ký tự.'
                          : null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: confirm,
                    obscureText: hidePassword,
                    textInputAction: TextInputAction.done,
                    onFieldSubmitted: (_) => _submit(),
                    decoration: const InputDecoration(
                      labelText: 'Nhập lại mật khẩu',
                    ),
                    validator: (value) => value != password.text
                        ? 'Hai mật khẩu chưa khớp.'
                        : null,
                  ),
                  CheckboxListTile(
                    value: accepted,
                    contentPadding: EdgeInsets.zero,
                    controlAffinity: ListTileControlAffinity.leading,
                    onChanged: widget.controller.busy
                        ? null
                        : (value) => setState(() => accepted = value ?? false),
                    title: const Text(
                      'Tôi đồng ý với điều khoản sử dụng Davel Trace cho bản demo học tập.',
                    ),
                  ),
                  if (widget.controller.errorMessage != null)
                    Text(
                      widget.controller.errorMessage!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: !accepted || widget.controller.busy
                        ? null
                        : _submit,
                    child: Text(
                      widget.controller.busy
                          ? 'Đang tạo tài khoản…'
                          : 'Tạo tài khoản',
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
