import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:davel_trace/features/management/data/demo_management_repository.dart';
import 'package:davel_trace/features/management/data/offline_management_repository.dart';
import 'package:davel_trace/features/management/data/offline_models.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/features/shell/presentation/main_shell.dart';
import 'package:davel_trace/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_management_repository.dart';

void main() {
  test('explicit demo repository has no production sync control', () {
    expect(DemoManagementRepository(), isNot(isA<OfflineSyncControl>()));
  });

  testWidgets('keeps offline synchronization actions reachable at 390x844', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = _SyncRepository();
    final state = AppState(repository);

    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: AnimatedBuilder(
          animation: state,
          builder: (context, _) =>
              Scaffold(body: OfflineSyncBanner(state: state)),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byKey(const Key('offline-sync-banner')), findsOneWidget);
    expect(
      find.byKey(const Key('sync-offline-changes-button')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);

    repository.current = const SyncStatus(
      conflictCount: 1,
      lastSuccessAt: null,
    );
    state.notifyListeners();
    await tester.pump();

    expect(
      find.byKey(const Key('discard-offline-conflicts-button')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}

class _SyncRepository extends FakeManagementRepository
    implements LiveManagementRepository, OfflineSyncControl {
  _SyncRepository() : super(seeded: true);

  SyncStatus current = SyncStatus(
    usingStaleCache: true,
    pendingCount: 2,
    lastSuccessAt: DateTime.utc(2026, 11, 10, 8),
  );

  @override
  String? activeTripId;

  @override
  SyncStatus get status => current;

  @override
  Future<void> setActiveTrip(Trip? trip) async => activeTripId = trip?.id;

  @override
  Future<void> loadStatus() async {}

  @override
  Future<SyncStatus> synchronize() async {
    current = const SyncStatus();
    return current;
  }

  @override
  Future<SyncStatus> discardConflicts() async {
    current = const SyncStatus();
    return current;
  }

  @override
  Future<SyncStatus> retryConflicts() async => current;

  @override
  Future<void> clearAccount() async {
    current = const SyncStatus();
  }
}
