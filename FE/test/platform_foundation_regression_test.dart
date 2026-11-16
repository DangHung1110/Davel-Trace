import 'package:davel_trace/app.dart';
import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:davel_trace/features/itinerary/presentation/itinerary_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('desktop frame navigates itinerary map expenses and profile', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      DavelTraceApp(repository: FakeManagementRepository(seeded: true)),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('desktop-phone-frame')), findsOneWidget);
    expect(find.byKey(const Key('trip-demo-notice')), findsOneWidget);

    await tester.tap(find.byKey(const Key('map-tab')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('locate-user-button')), findsOneWidget);

    await tester.tap(find.byKey(const Key('expenses-tab')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('expense-source-status')), findsOneWidget);

    await tester.tap(find.byKey(const Key('profile-tab')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('account-identity')), findsOneWidget);
    await tester.tap(find.byKey(const Key('travel-preferences-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('edit-profile-button')), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('itinerary-tab')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('trip-demo-notice')), findsOneWidget);
  });

  testWidgets('live and stale planning states stay visibly distinct', (
    tester,
  ) async {
    final state = AppState(FakeManagementRepository(seeded: true));
    await state.initialize();
    state.demoSource = DemoSource.live;
    await tester.pumpWidget(MaterialApp(home: PlanningScreen(state: state)));
    await tester.pumpAndSettle();
    expect(find.text('Phương án từ hệ thống'), findsOneWidget);

    state.demoSource = DemoSource.stale;
    await tester.pumpWidget(MaterialApp(home: PlanningScreen(state: state)));
    await tester.pumpAndSettle();
    expect(find.text('Dữ liệu gần nhất · mất kết nối'), findsOneWidget);
  });
}
