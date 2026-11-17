import 'package:flutter/material.dart';

import '../../../shared/widgets/section_intro.dart';

import '../application/auth_controller.dart';

class RecoveryScreen extends StatefulWidget {
  const RecoveryScreen({
    super.key,
    required this.controller,
    this.cancelDeletion = false,
  });
  final AuthController controller;
  final bool cancelDeletion;

  @override
  State<RecoveryScreen> createState() => _RecoveryScreenState();
}

class _RecoveryScreenState extends State<RecoveryScreen> {
  final email = TextEditingController();
  final token = TextEditingController();
  final password = TextEditingController();
  bool requested = false;

  @override
  void dispose() {
    email.dispose();
    token.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.cancelDeletion ? 'Khôi phục tài khoản' : 'Khôi phục mật khẩu',
      ),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          SectionIntro(
            icon: Icons.lock_reset_outlined,
            title: widget.cancelDeletion
                ? 'Chào mừng bạn trở lại'
                : 'Lấy lại quyền truy cập',
            description: widget.cancelDeletion
                ? 'Dùng email tài khoản để yêu cầu mã khôi phục trong thời gian cho phép.'
                : 'Nhập email tài khoản để nhận hướng dẫn và mã đặt lại mật khẩu.',
          ),
          TextField(
            controller: email,
            enabled: !requested,
            decoration: const InputDecoration(labelText: 'Email'),
          ),
          if (requested) ...[
            const SizedBox(height: 12),
            Text(
              widget.controller.message ??
                  'Hãy kiểm tra email để lấy mã khôi phục.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: token,
              decoration: const InputDecoration(labelText: 'Mã khôi phục'),
            ),
            const SizedBox(height: 12),
            if (!widget.cancelDeletion)
              TextField(
                controller: password,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Mật khẩu mới'),
              ),
            if (widget.controller.developmentInboxEnabled)
              OutlinedButton(
                onPressed: () async {
                  final value = await widget.controller.loadDevelopmentToken(
                    widget.cancelDeletion
                        ? 'cancel_deletion'
                        : 'recover_password',
                  );
                  if (value != null) {
                    token.text = value;
                  }
                },
                child: const Text('Lấy mã demo'),
              ),
          ],
          if (widget.controller.errorMessage != null)
            Text(
              widget.controller.errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: widget.controller.busy
                ? null
                : () async {
                    if (!requested) {
                      if (widget.cancelDeletion) {
                        await widget.controller.requestDeletionCancel(
                          email.text,
                        );
                      } else {
                        await widget.controller.requestRecovery(email.text);
                      }
                      if (widget.controller.errorMessage == null) {
                        setState(() => requested = true);
                      }
                    } else {
                      if (widget.cancelDeletion) {
                        await widget.controller.confirmDeletionCancel(
                          token.text,
                        );
                      } else {
                        await widget.controller.resetPassword(
                          token.text,
                          password.text,
                        );
                      }
                      if (context.mounted &&
                          widget.controller.errorMessage == null) {
                        Navigator.pop(context);
                      }
                    }
                  },
            child: Text(
              requested
                  ? (widget.cancelDeletion
                        ? 'Khôi phục tài khoản'
                        : 'Đổi mật khẩu')
                  : 'Gửi yêu cầu',
            ),
          ),
        ],
      ),
    ),
  );
}
