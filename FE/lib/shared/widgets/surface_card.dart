import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

class SurfaceCard extends StatelessWidget {
  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.color = AppColors.surface,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(22),
        boxShadow: color == AppColors.surface
            ? const [
                BoxShadow(
                  color: Color(0x06263D3A),
                  blurRadius: 18,
                  offset: Offset(0, 5),
                ),
              ]
            : const [],
        border: Border.all(
          color: color == AppColors.surface
              ? AppColors.outline
              : Colors.transparent,
        ),
      ),
      child: child,
    );
  }
}
