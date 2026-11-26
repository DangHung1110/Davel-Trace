import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

class FieldCover extends StatelessWidget {
  const FieldCover({
    super.key,
    required this.title,
    required this.description,
    this.compact = false,
  });

  final String title;
  final String description;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final type = Theme.of(context).textTheme;
    final largeText = MediaQuery.textScalerOf(context).scale(16) > 22;
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: ColoredBox(
        color: AppColors.primaryDark,
        child: Stack(
          children: [
            Positioned.fill(
              child: Image.asset(
                'assets/images/da-nang-bridge.jpg',
                fit: BoxFit.cover,
                alignment: const Alignment(0, .16),
                excludeFromSemantics: true,
                errorBuilder: (context, error, stack) => const SizedBox(),
              ),
            ),
            const Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.bottomLeft,
                    end: Alignment.topRight,
                    colors: [
                      Color(0xFC102E4C),
                      Color(0x98102E4C),
                      Color(0x16102E4C),
                    ],
                  ),
                ),
              ),
            ),
            ConstrainedBox(
              constraints: BoxConstraints(
                minHeight: largeText
                    ? 0
                    : compact
                    ? 175
                    : 214,
              ),
              child: Align(
                alignment: Alignment.bottomLeft,
                child: Padding(
                  padding: EdgeInsets.fromLTRB(18, largeText ? 20 : 56, 18, 18),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style:
                            (largeText
                                    ? type.headlineMedium
                                    : type.displaySmall)
                                ?.copyWith(color: Colors.white),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        description,
                        style: type.bodyMedium?.copyWith(color: AppColors.sand),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
