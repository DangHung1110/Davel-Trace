import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

class AppHeader extends StatelessWidget {
  const AppHeader({
    super.key,
    this.trailing,
    this.compact = false,
    this.section = 'Lịch trình',
  });

  final Widget? trailing;
  final bool compact;
  final String section;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: compact ? 56 : 64,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(bottom: BorderSide(color: AppColors.outline)),
      ),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.route_rounded,
              color: Colors.white,
              size: 19,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Davel Trace',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -.2,
                  ),
                ),
                Text(
                  'Đà Nẵng · $section',
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          trailing ??
              const CircleAvatar(
                radius: 16,
                backgroundColor: AppColors.sand,
                child: Icon(
                  Icons.person_rounded,
                  color: AppColors.primary,
                  size: 18,
                ),
              ),
        ],
      ),
    );
  }
}
