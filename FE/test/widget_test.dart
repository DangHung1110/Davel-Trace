import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:davel_trace/app.dart';

void main() {
  testWidgets('shows the three primary product areas', (tester) async {
    await tester.pumpWidget(const DavelTraceApp());

    expect(find.text('Tạo chuyến đi mới'), findsOneWidget);
    expect(find.text('Lịch trình'), findsOneWidget);
    expect(find.text('Bản đồ'), findsOneWidget);
    expect(find.text('Chi tiêu'), findsOneWidget);
    expect(find.byKey(const Key('generate-plan-button')), findsOneWidget);
  });
}
