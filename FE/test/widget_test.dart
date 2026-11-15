import 'package:davel_trace/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

Future<void> tapKey(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      finder,
      300,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await Scrollable.ensureVisible(tester.element(finder), alignment: 0.5);
  await tester.pump();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('creates the first local profile and opens management shell', (
    tester,
  ) async {
    final repository = FakeManagementRepository();
    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    expect(find.text('ĐÀ NẴNG GO'), findsOneWidget);
    final profileName = find.byKey(const Key('profile-name-field'));
    await tester.scrollUntilVisible(
      profileName,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(profileName, 'Hùng');
    await tapKey(tester, 'create-first-profile-button');

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Chưa có chuyến đi'), findsOneWidget);
    expect(repository.profiles.single.displayName, 'Hùng');
  });

  testWidgets('creates a trip and adds a manual activity', (tester) async {
    final repository = FakeManagementRepository(seeded: true);
    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    expect(find.text('Cuối tuần Đà Nẵng'), findsNWidgets(2));
    await tapKey(tester, 'add-activity-button');
    await tester.enterText(
      find.byKey(const Key('activity-title-field')),
      'Cầu Rồng',
    );
    await tapKey(tester, 'save-activity-button');

    expect(find.text('Cầu Rồng'), findsOneWidget);
    expect(repository.activities.single.source, 'manual');
  });

  testWidgets('persists an expense and updates the budget summary', (
    tester,
  ) async {
    final repository = FakeManagementRepository(seeded: true);
    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Chi tiêu').last);
    await tester.pumpAndSettle();
    await tapKey(tester, 'add-expense-button');
    await tester.enterText(
      find.byKey(const Key('expense-title-field')),
      'Mì Quảng',
    );
    await tester.enterText(
      find.byKey(const Key('expense-amount-field')),
      '50000',
    );
    await tapKey(tester, 'save-expense-button');

    final expenseLabel = find.text('Mì Quảng');
    await tester.scrollUntilVisible(
      expenseLabel,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(expenseLabel, findsOneWidget);
    expect(find.text('50.000 ₫'), findsNWidgets(2));
    expect(repository.expenses.single.amountVnd, 50000);
  });
}
