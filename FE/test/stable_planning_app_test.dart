import 'package:davel_trace/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('shows the phone frame and honest demo planning state', (
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
    expect(find.byKey(const Key('source-status-banner')), findsOneWidget);
    expect(find.byKey(const Key('request-plan-button')), findsOneWidget);
    expect(find.byKey(const Key('map-tab')), findsOneWidget);
    expect(find.byKey(const Key('expenses-tab')), findsOneWidget);
    expect(find.byKey(const Key('profile-tab')), findsOneWidget);
  });
}
