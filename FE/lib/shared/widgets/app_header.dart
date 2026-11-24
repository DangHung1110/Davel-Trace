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
    return LayoutBuilder(
      builder: (context, constraints) {
        final stacked =
            constraints.maxWidth < 340 ||
            MediaQuery.textScalerOf(context).scale(14) > 19;
        return Container(
          constraints: BoxConstraints(minHeight: compact ? 56 : 64),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: const BoxDecoration(color: AppColors.canvas),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: AppColors.sand,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.explore_outlined,
                      color: AppColors.primary,
                      size: 19,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          section,
                          maxLines: stacked ? 2 : 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.primary,
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -.2,
                          ),
                        ),
                        if (!stacked)
                          const Text(
                            'ĐÀ NẴNG · CHUYẾN ĐI CỦA BẠN',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: AppColors.muted,
                              fontSize: 9,
                              letterSpacing: .5,
                            ),
                          ),
                      ],
                    ),
                  ),
                  if (!stacked) ?trailing,
                ],
              ),
              if (stacked && trailing != null)
                Align(alignment: Alignment.centerRight, child: trailing!),
            ],
          ),
        );
      },
    );
  }
}
