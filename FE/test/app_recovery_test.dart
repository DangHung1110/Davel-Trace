import 'package:davel_trace/app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('shows API recovery and succeeds on retry', (tester) async {
    final repository = FakeManagementRepository(seeded: true)
      ..failListProfiles = true;

    await tester.pumpWidget(DavelTraceApp(repository: repository));
    await tester.pumpAndSettle();

    expect(find.text('Backend chưa sẵn sàng'), findsOneWidget);
    repository.failListProfiles = false;
    await tester.tap(find.byKey(const Key('retry-api-button')));
    await tester.pumpAndSettle();

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.text('Cuối tuần Đà Nẵng'), findsNWidgets(2));
  });
}
