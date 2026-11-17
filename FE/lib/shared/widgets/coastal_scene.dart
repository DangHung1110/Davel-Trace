import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// A bundled illustration: no remote image request or invented travel data.
class CoastalScene extends StatelessWidget {
  const CoastalScene({super.key, this.height = 126, this.child});
  final double height;
  final Widget? child;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: height,
    width: double.infinity,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: CustomPaint(painter: const _CoastPainter(), child: child),
    ),
  );
}

class _CoastPainter extends CustomPainter {
  const _CoastPainter();
  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFEDF4F0), Color(0xFFD7E9E4)],
        ).createShader(rect),
    );
    canvas.drawCircle(
      Offset(size.width * .78, size.height * .27),
      21,
      Paint()..color = const Color(0xFFF2DDC3),
    );
    final hill = Path()
      ..moveTo(0, size.height * .64)
      ..cubicTo(
        size.width * .13,
        size.height * .38,
        size.width * .25,
        size.height * .56,
        size.width * .39,
        size.height * .43,
      )
      ..cubicTo(
        size.width * .52,
        size.height * .18,
        size.width * .66,
        size.height * .61,
        size.width,
        size.height * .5,
      )
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(hill, Paint()..color = const Color(0xFFA9C5B9));
    final shore = Path()
      ..moveTo(0, size.height * .78)
      ..cubicTo(
        size.width * .28,
        size.height * .52,
        size.width * .55,
        size.height * 1.3,
        size.width,
        size.height * .72,
      )
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(shore, Paint()..color = const Color(0xFFD3E7E4));
    canvas.drawPath(
      shore,
      Paint()
        ..color = AppColors.surface.withValues(alpha: .55)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(covariant _CoastPainter oldDelegate) => false;
}
