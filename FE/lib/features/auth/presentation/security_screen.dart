import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../application/auth_controller.dart';
import '../domain/models.dart';

class SecurityScreen extends StatefulWidget {
  const SecurityScreen({super.key, required this.controller});
  final AuthController controller;

  @override
  State<SecurityScreen> createState() => _SecurityScreenState();
}

class _SecurityScreenState extends State<SecurityScreen> {
  late Future<List<IdentitySession>> sessions;

  @override
  void initState() {
    super.initState();
    sessions = widget.controller.repository.sessions();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) => Scaffold(
      appBar: AppBar(title: const Text('Tài khoản & bảo mật')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (widget.controller.errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(
                widget.controller.errorMessage!,
                key: const Key('security-action-error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(
              widget.controller.account?.email ?? '',
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: const Text('Thông tin tài khoản đăng nhập'),
          ),
          const Divider(),
          Text(
            'Phiên đăng nhập',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          FutureBuilder<List<IdentitySession>>(
            future: sessions,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Không tải được thiết bị đăng nhập.'),
                    TextButton(
                      onPressed: () => setState(
                        () =>
                            sessions = widget.controller.repository.sessions(),
                      ),
                      child: const Text('Thử lại'),
                    ),
                  ],
                );
              }
              if (!snapshot.hasData) {
                return const Center(child: CircularProgressIndicator());
              }
              return Column(
                children: [
                  for (final item in snapshot.data!)
                    ListTile(
                      leading: Icon(
                        item.current ? Icons.phone_android : Icons.devices,
                      ),
                      title: Text(item.deviceLabel),
                      subtitle: Text(
                        item.current ? 'Thiết bị hiện tại' : 'Đang hoạt động',
                      ),
                      trailing: item.current
                          ? null
                          : IconButton(
                              icon: const Icon(Icons.logout),
                              onPressed: () async {
                                try {
                                  await widget.controller.repository
                                      .revokeSession(item.id);
                                  if (mounted) {
                                    setState(
                                      () => sessions = widget
                                          .controller
                                          .repository
                                          .sessions(),
                                    );
                                  }
                                } catch (_) {
                                  if (context.mounted) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text(
                                          'Không thể đăng xuất thiết bị này. Hãy thử lại.',
                                        ),
                                      ),
                                    );
                                  }
                                }
                              },
                            ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            key: const Key('security-logout-button'),
            onPressed: widget.controller.busy
                ? null
                : () async {
                    await widget.controller.logout();
                    if (context.mounted) {
                      Navigator.of(context).popUntil((route) => route.isFirst);
                    }
                  },
            icon: const Icon(Icons.logout),
            label: const Text('Đăng xuất'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: widget.controller.busy
                ? null
                : () => _createExport(context),
            icon: const Icon(Icons.download_outlined),
            label: const Text('Tạo bản xuất dữ liệu'),
          ),
          const SizedBox(height: 12),
          TextButton.icon(
            style: TextButton.styleFrom(
              foregroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: widget.controller.busy
                ? null
                : () => _confirmDeletion(context),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Yêu cầu xóa tài khoản'),
          ),
        ],
      ),
    ),
  );

  Future<void> _confirmDeletion(BuildContext context) async {
    final password = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Xóa tài khoản?'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Bạn sẽ đăng xuất ngay. Có thể khôi phục trong 30 ngày.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: password,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Nhập mật khẩu để xác nhận',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xóa tài khoản'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await widget.controller.deleteAccount(password.text);
      if (context.mounted && widget.controller.errorMessage == null) {
        Navigator.pop(context);
      }
    }
    password.dispose();
  }

  Future<void> _createExport(BuildContext context) async {
    final password = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Xuất dữ liệu tài khoản'),
        content: TextField(
          controller: password,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Nhập mật khẩu để xác nhận',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Tạo bản xuất'),
          ),
        ],
      ),
    );
    if (confirmed != true) {
      password.dispose();
      return;
    }
    final result = await widget.controller.createExport(password.text);
    password.dispose();
    if (!context.mounted || result == null) return;
    final portableJson = const JsonEncoder.withIndent('  ')
        .convert(result['payload']);
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Bản xuất đã sẵn sàng'),
        content: SizedBox(
          width: 420,
          child: SingleChildScrollView(child: SelectableText(portableJson)),
        ),
        actions: [
          TextButton(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: portableJson));
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Sao chép JSON'),
          ),
        ],
      ),
    );
  }
}
