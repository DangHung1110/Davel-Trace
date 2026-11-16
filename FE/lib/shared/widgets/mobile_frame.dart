import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// Constrains the Navigator, so dialogs, editors and account pages share the shell.
class MobileFrame extends StatelessWidget {
  const MobileFrame({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: AppColors.surfaceHigh,
    child: LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth > 600;
        final width = desktop ? 390.0 : constraints.maxWidth;
        final height = desktop && constraints.maxHeight > 876
            ? 844.0
            : constraints.maxHeight;
        return Center(
          child: SizedBox(
            key: const Key('desktop-phone-frame'),
            width: width,
            height: height,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(desktop ? 28 : 0),
              child: MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(size: Size(width, height)),
                child: child,
              ),
            ),
          ),
        );
      },
    ),
  );
}
