import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// A short introduction for the two entry screens, with an abstract route mark.
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
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: ColoredBox(
        color: AppColors.primaryDark,
        child: Stack(
          children: [
            const Positioned.fill(
              child: RepaintBoundary(child: CustomPaint(painter: _RouteMark())),
            ),
            Padding(
              padding: EdgeInsets.fromLTRB(20, compact ? 14 : 22, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.route_outlined,
                    color: Color(0xFFDBB983),
                    size: 25,
                  ),
                  SizedBox(height: compact ? 8 : 15),
                  Text(
                    title,
                    style: (compact ? type.headlineMedium : type.displaySmall)
                        ?.copyWith(color: AppColors.surface),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    description,
                    style: type.bodyMedium?.copyWith(color: AppColors.sand),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RouteMark extends CustomPainter {
  const _RouteMark();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.translate(size.width, 0);
    final contour = Paint()
      ..color = const Color(0xFF426B58)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (var i = 0; i < 6; i++) {
      final offset = i * 12.0;
      final trace = Path()
        ..moveTo(-92 - offset, -14)
        ..cubicTo(-132 - offset, 25, -37 - offset, 31, -53 - offset, 59)
        ..cubicTo(-65 - offset, 85, -12 - offset, 90, 22, 97 + offset);
      canvas.drawPath(trace, contour);
    }
    final route = Paint()
      ..color = const Color(0xFFDBB983)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    canvas.drawPath(
      Path()
        ..moveTo(-92, 21)
        ..cubicTo(-70, 25, -81, 46, -57, 50)
        ..quadraticBezierTo(-39, 54, -26, 34),
      route,
    );
    for (final point in const [
      Offset(-92, 21),
      Offset(-57, 50),
      Offset(-26, 34),
    ]) {
      canvas.drawCircle(point, 3, route..style = PaintingStyle.fill);
    }
  }

  @override
  bool shouldRepaint(covariant _RouteMark oldDelegate) => false;
}
