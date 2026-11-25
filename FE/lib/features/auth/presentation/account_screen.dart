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
        const AppHeader(section: 'Tài khoản', compact: true),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SurfaceCard(
                key: const Key('account-identity'),
                color: AppColors.sand,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const CircleAvatar(
                      radius: 23,
                      backgroundColor: AppColors.surface,
                      child: Icon(
                        Icons.person_outline,
                        color: AppColors.primary,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            signedIn ? 'Email tài khoản' : 'Bạn đang xem thử',
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
                              'Đăng nhập để lưu chuyến đi và chi tiêu của bạn.',
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (!signedIn && controller != null) ...[
                FilledButton(
                  key: const Key('account-logout-button'),
                  onPressed: controller!.busy ? null : controller!.leaveDemo,
                  child: const Text('Đăng nhập'),
                ),
                const SizedBox(height: 16),
              ],
              SurfaceCard(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Column(
                  children: [
                    if (signedIn) ...[
                      _AccountLink(
                        key: const Key('account-security-button'),
                        icon: Icons.shield_outlined,
                        title: 'Bảo mật và dữ liệu',
                        subtitle: 'Thiết bị đăng nhập và quyền riêng tư',
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) =>
                                SecurityScreen(controller: controller!),
                          ),
                        ),
                      ),
                      const Divider(height: 1),
                    ],
                    _AccountLink(
                      key: const Key('travel-preferences-button'),
                      icon: Icons.tune_rounded,
                      title: 'Sở thích du lịch',
                      subtitle: 'Nhịp đi, thể lực và sở thích của bạn',
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => Scaffold(
                            appBar: AppBar(
                              title: const Text('Sở thích du lịch'),
                            ),
                            body: AnimatedBuilder(
                              animation: state,
                              builder: (_, _) => ProfileScreen(
                                state: state,
                                showHeader: false,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (signedIn && controller != null)
                TextButton.icon(
                  key: const Key('account-logout-button'),
                  onPressed: controller!.busy ? null : controller!.logout,
                  icon: const Icon(Icons.logout_rounded),
                  label: const Text('Đăng xuất'),
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
