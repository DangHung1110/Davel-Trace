import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../application/auth_controller.dart';
import '../domain/models.dart';
import '../../../shared/widgets/surface_card.dart';

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
      appBar: AppBar(title: const Text('Bảo mật và dữ liệu')),
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
          Text(
            'Thiết bị đang đăng nhập',
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
              if (snapshot.data!.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Chưa thấy thiết bị đăng nhập.'),
                );
              }
              return SurfaceCard(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Column(
                  children: [
                    for (final item in snapshot.data!)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          item.current ? Icons.phone_android : Icons.devices,
                        ),
                        title: Text(item.deviceLabel),
                        subtitle: item.current
                            ? const Text('Thiết bị này')
                            : null,
                        trailing: item.current
                            ? null
                            : IconButton(
                                icon: const Icon(Icons.logout),
                                tooltip: 'Đăng xuất thiết bị này',
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
                                      ScaffoldMessenger.of(context)
                                          .showSnackBar(
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
                ),
              );
            },
          ),
          const SizedBox(height: 20),
          TextButton.icon(
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
          const SizedBox(height: 18),
          Text(
            'Dữ liệu cá nhân',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            onTap: widget.controller.busy ? null : () => _createExport(context),
            leading: const Icon(Icons.download_outlined),
            title: const Text('Xuất dữ liệu của tôi'),
          ),
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
    final password = await _confirmWithPassword(
      context,
      title: 'Xóa tài khoản?',
      action: 'Xóa tài khoản',
      explanation: 'Bạn sẽ đăng xuất ngay. Có thể khôi phục trong 30 ngày.',
    );
    if (password != null && context.mounted) {
      await widget.controller.deleteAccount(password);
      if (context.mounted && widget.controller.errorMessage == null) {
        Navigator.of(context).popUntil((route) => route.isFirst);
      }
    }
  }

  Future<String?> _confirmWithPassword(
    BuildContext context, {
    required String title,
    required String action,
    String? explanation,
  }) {
    var password = '';
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
        title: Text(title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (explanation != null) ...[
              Text(explanation),
              const SizedBox(height: 12),
            ],
            TextField(
              onChanged: (value) => password = value,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'Nhập mật khẩu để xác nhận',
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Nếu bạn dùng Google và chưa có mật khẩu Davel Trace, chọn Quên mật khẩu ở màn hình đăng nhập để đặt mật khẩu.',
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () {
              if (password.isNotEmpty) Navigator.pop(context, password);
            },
            child: Text(action),
          ),
        ],
      ),
    );
  }

  Future<void> _createExport(BuildContext context) async {
    final password = await _confirmWithPassword(
      context,
      title: 'Xuất dữ liệu tài khoản',
      action: 'Chuẩn bị dữ liệu',
    );
    if (password == null || !context.mounted) return;
    final result = await widget.controller.createExport(password);
    if (!context.mounted || result == null) return;
    final portableJson = const JsonEncoder.withIndent('  ')
        .convert(result['payload']);
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Bản xuất đã sẵn sàng'),
        content: const Text('Sao chép bản dữ liệu để lưu vào nơi bạn chọn.'),
        actions: [
          TextButton(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: portableJson));
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Sao chép dữ liệu'),
          ),
        ],
      ),
    );
  }
}
