import 'package:flutter/material.dart';

import '../../../shared/widgets/section_intro.dart';

import '../application/auth_controller.dart';

class VerifyScreen extends StatefulWidget {
  const VerifyScreen({super.key, required this.controller});
  final AuthController controller;

  @override
  State<VerifyScreen> createState() => _VerifyScreenState();
}

class _VerifyScreenState extends State<VerifyScreen> {
  final token = TextEditingController();

  @override
  void dispose() {
    token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Xác thực email')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const SectionIntro(
            icon: Icons.mark_email_read_outlined,
            title: 'Kiểm tra hộp thư',
            description: 'Nhập mã xác thực email để tiếp tục. Bạn có thể gửi lại mã nếu chưa nhận được.',
          ),
          Text(
            widget.controller.message ??
                'Kiểm tra email ${widget.controller.pendingEmail ?? 'của bạn'} để lấy mã xác thực.',
          ),
          const SizedBox(height: 16),
          TextField(
            controller: token,
            decoration: const InputDecoration(labelText: 'Mã xác thực'),
          ),
          if (widget.controller.developmentInboxEnabled) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () async {
                final value = await widget.controller.loadDevelopmentToken(
                  'verify_email',
                );
                if (value != null) token.text = value;
              },
              icon: const Icon(Icons.developer_mode),
              label: const Text('Lấy mã từ hộp thư phát triển'),
            ),
            const Text(
              'Chỉ có trong chế độ demo/test.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12),
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
                : () => widget.controller.verify(token.text),
            child: const Text('Xác thực'),
          ),
          TextButton(
            onPressed: widget.controller.busy
                ? null
                : () async {
                    await widget.controller.resendVerification();
                    if (mounted) setState(() {});
                  },
            child: const Text('Gửi lại mã xác thực'),
          ),
        ],
      ),
    ),
  );
}
