import 'package:flutter/material.dart';

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
    appBar: AppBar(title: const Text('Xác nhận email')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          if (widget.controller.pendingEmail case final address?)
            Text(address, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(
            widget.controller.message ??
                'Kiểm tra email ${widget.controller.pendingEmail ?? 'của bạn'} để lấy mã xác thực.',
          ),
          const SizedBox(height: 16),
          TextField(
            controller: token,
            autofillHints: const [AutofillHints.oneTimeCode],
            decoration: const InputDecoration(labelText: 'Mã xác thực'),
          ),
          if (widget.controller.developmentInboxEnabled) ...[
            const SizedBox(height: 12),
            TextButton(
              onPressed: () async {
                final value = await widget.controller.loadDevelopmentToken(
                  'verify_email',
                );
                if (mounted && value != null) token.text = value;
              },
              child: const Text('Dùng mã thử'),
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
