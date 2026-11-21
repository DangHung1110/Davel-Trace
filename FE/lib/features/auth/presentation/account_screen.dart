import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../profile/presentation/profile_screen.dart';
import '../application/auth_controller.dart';
import 'security_screen.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key, required this.state, this.controller});
  final AppState state;
  final AuthController? controller;

  @override
  Widget build(BuildContext context) {
    final account = controller?.account;
    final signedIn =
        controller?.status == AuthStatus.authenticated && account != null;
    return Column(
      children: [
        const AppHeader(section: 'Davel Trace'),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                'Tài khoản',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 20),
              SurfaceCard(
                key: const Key('account-identity'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const CircleAvatar(
                      radius: 26,
                      backgroundColor: AppColors.sand,
                      child: Icon(
                        Icons.person_outline,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      signedIn
                          ? 'Tài khoản đã đăng nhập'
                          : 'Bạn đang dùng bản demo',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    if (signedIn)
                      SelectableText(
                        account.email,
                        key: const Key('account-email'),
                      )
                    else
                      const Text(
                        'Đăng nhập để lưu chuyến đi và chi tiêu vào tài khoản.',
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              if (signedIn) ...[
                _AccountLink(
                  key: const Key('account-security-button'),
                  icon: Icons.shield_outlined,
                  title: 'Bảo mật và dữ liệu',
                  subtitle: 'Thiết bị đăng nhập, xuất dữ liệu, xóa tài khoản',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => SecurityScreen(controller: controller!),
                    ),
                  ),
                ),
                const Divider(height: 24),
              ],
              _AccountLink(
                key: const Key('travel-preferences-button'),
                icon: Icons.tune_rounded,
                title: 'Sở thích du lịch',
                subtitle: 'Tùy chọn gợi ý cho chuyến đi mới',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => Scaffold(
                      appBar: AppBar(title: const Text('Sở thích du lịch')),
                      body: AnimatedBuilder(
                        animation: state,
                        builder: (_, _) =>
                            ProfileScreen(state: state, showHeader: false),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 28),
              if (controller != null)
                OutlinedButton.icon(
                  key: const Key('account-logout-button'),
                  onPressed: controller!.busy
                      ? null
                      : signedIn
                      ? controller!.logout
                      : controller!.leaveDemo,
                  icon: Icon(
                    signedIn ? Icons.logout_rounded : Icons.login_rounded,
                  ),
                  label: Text(
                    signedIn ? 'Đăng xuất' : 'Đăng nhập / Tạo tài khoản',
                  ),
                ),
              const SizedBox(height: 16),
              const Text(
                'Davel Trace · Đồng hành cùng chuyến đi Đà Nẵng',
                style: TextStyle(fontSize: 12, color: AppColors.muted),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _AccountLink extends StatelessWidget {
  const _AccountLink({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: EdgeInsets.zero,
    leading: Icon(icon, color: AppColors.primary),
    title: Text(title),
    subtitle: Text(subtitle),
    trailing: const Icon(Icons.chevron_right_rounded),
    onTap: onTap,
  );
}
