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

  testWidgets('creates a mock plan and opens the map', (tester) async {
    await tester.pumpWidget(const DavelTraceApp());

    await tester.tap(find.byKey(const Key('generate-plan-button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Hành trình demo'), findsOneWidget);
    expect(find.textContaining('2 điểm'), findsOneWidget);
    expect(find.byKey(const Key('play-car-button')), findsOneWidget);
  });

  testWidgets('adds an in-memory expense', (tester) async {
    await tester.pumpWidget(const DavelTraceApp());

    await tester.tap(find.text('Chi tiêu'));
    await tester.pump();
    await tester.tap(find.byKey(const Key('add-expense-button')));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const Key('expense-title-field')),
      'Cà phê demo',
    );
    await tester.enterText(
      find.byKey(const Key('expense-amount-field')),
      '50000',
    );
    await tester.tap(find.byKey(const Key('save-expense-button')));
    await tester.pumpAndSettle();

    expect(find.text('Cà phê demo'), findsOneWidget);
    expect(find.textContaining('Đã chi 400.000 ₫'), findsOneWidget);
  });
}
