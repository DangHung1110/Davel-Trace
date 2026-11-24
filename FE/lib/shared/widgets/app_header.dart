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
      constraints: BoxConstraints(minHeight: compact ? 56 : 64),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: const BoxDecoration(
        color: AppColors.canvas,
        border: Border(bottom: BorderSide(color: AppColors.outline)),
      ),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: AppColors.sand,
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Icon(
              Icons.route_rounded,
              color: AppColors.primaryDark,
              size: 19,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              section,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}
