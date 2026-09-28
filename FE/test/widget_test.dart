import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:davel_trace/app.dart';

Future<void> tapKey(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
  await tester.pump();
}

void main() {
  testWidgets('opens the Stitch-inspired planner after onboarding', (
    tester,
  ) async {
    await tester.pumpWidget(const DavelTraceApp());

    expect(find.text('Hiểu gu du hành'), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);

    await tapKey(tester, 'onboarding-continue-button');

    expect(find.text('Đi đâu hôm nay?'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byKey(const Key('generate-plan-button')), findsOneWidget);
  });

  testWidgets('clicks through the mock planning flow and opens the map', (
    tester,
  ) async {
    await tester.pumpWidget(const DavelTraceApp());
    await tapKey(tester, 'onboarding-continue-button');

    await tapKey(tester, 'generate-plan-button');
    expect(find.text('Bạn muốn bắt đầu lúc nào?'), findsOneWidget);

    await tapKey(tester, 'clarification-confirm-button');
    expect(find.text('Lịch trình đã vượt qua kiểm tra'), findsOneWidget);

    await tapKey(tester, 'feasibility-continue-button');
    await tapKey(tester, 'select-balanced-plan-button');
    expect(find.text('Đà Nẵng chậm mà chất'), findsOneWidget);

    await tapKey(tester, 'start-trip-button');

    expect(find.text('ĐANG ĐI · 2/4'), findsOneWidget);
    expect(find.byKey(const Key('play-car-button')), findsOneWidget);
    expect(find.byKey(const Key('locate-user-button')), findsOneWidget);
  });

  testWidgets('adds an in-memory expense', (tester) async {
    await tester.pumpWidget(const DavelTraceApp());
    await tapKey(tester, 'onboarding-continue-button');

    await tester.tap(find.text('Chi tiêu').last);
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
    expect(find.textContaining('Đã chi 3.300.000 ₫'), findsOneWidget);
  });
}
