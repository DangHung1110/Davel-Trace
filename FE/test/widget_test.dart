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

  testWidgets(
    'collapsed expense filters and one action menu retain filtering edit and delete',
    (tester) async {
      final repository = FakeManagementRepository(seeded: true);
      await repository.addExpense('trip-1', {
        'label': 'Mì Quảng',
        'amount_vnd': 50000,
        'category': 'food',
        'spent_at': '2026-10-17',
        'notes': '',
      });
      await tester.pumpWidget(DavelTraceApp(repository: repository));
      await tester.pumpAndSettle();
      await tapKey(tester, 'expenses-tab');
      expect(find.byType(ChoiceChip), findsNothing);
      await tapKey(tester, 'expense-filters');
      final transport = find.widgetWithText(ChoiceChip, 'Di chuyển');
      await tester.ensureVisible(transport);
      await tester.pumpAndSettle();
      await tester.tap(transport);
      await tester.pumpAndSettle();
      expect(find.text('Mì Quảng'), findsNothing);
      final food = find.widgetWithText(ChoiceChip, 'Ăn uống');
      await tester.ensureVisible(food);
      await tester.pumpAndSettle();
      await tester.tap(food);
      await tester.pumpAndSettle();
      final menu = find.byTooltip('Tùy chọn khoản chi');
      await tester.scrollUntilVisible(
        menu,
        220,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(menu);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sửa khoản chi'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('expense-title-field')),
        'Mì Quảng buổi trưa',
      );
      await tapKey(tester, 'save-expense-button');
      expect(repository.expenses.single.label, 'Mì Quảng buổi trưa');
      await tester.ensureVisible(menu);
      await tester.pumpAndSettle();
      await tester.tap(menu);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Xóa khoản chi'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Xóa khoản chi'));
      await tester.pumpAndSettle();
      expect(repository.expenses, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('opens account before preferences and creates a travel profile', (
    tester,
  ) async {
    final repository = FakeManagementRepository();
    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    expect(find.byType(NavigationBar), findsOneWidget);
    await tapKey(tester, 'profile-tab');
    await tapKey(tester, 'travel-preferences-button');
    final profileName = find.byKey(const Key('profile-name-field'));
    await tester.scrollUntilVisible(
      profileName,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.enterText(profileName, 'Hùng');
    await tapKey(tester, 'create-first-profile-button');

    expect(repository.profiles.single.displayName, 'Hùng');
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tapKey(tester, 'itinerary-tab');
    expect(find.text('Chưa có chuyến đi'), findsOneWidget);
  });

  testWidgets('creates a trip and adds a manual activity', (tester) async {
    final repository = FakeManagementRepository(seeded: true);
    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    expect(find.text('Cuối tuần Đà Nẵng'), findsOneWidget);
    await tapKey(tester, 'open-trip-trip-1');
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
