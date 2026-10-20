import 'package:davel_trace/app.dart';
import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/features/shell/presentation/main_shell.dart';
import 'package:davel_trace/theme/app_theme.dart';
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

  testWidgets('keeps loaded data visible with a non-blocking retry banner', (
    tester,
  ) async {
    final repository = FakeManagementRepository(seeded: true);
    final state = AppState(repository);
    await state.initialize();
    state.errorMessage = 'Mất kết nối.';

    await tester.pumpWidget(
      AnimatedBuilder(
        animation: state,
        builder: (context, _) => MaterialApp(
          theme: AppTheme.light,
          home: MainShell(state: state),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('stale-data-error-banner')), findsOneWidget);
    expect(find.text('Cuối tuần Đà Nẵng'), findsNWidgets(2));

    await tester.tap(find.byKey(const Key('retry-stale-data-button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('stale-data-error-banner')), findsNothing);
    expect(find.text('Cuối tuần Đà Nẵng'), findsNWidgets(2));
  });
}
