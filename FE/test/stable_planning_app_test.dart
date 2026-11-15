import 'package:davel_trace/app.dart';
import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/features/planning/data/planning_repository.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _LifecyclePlanningRepository
    implements PlanningRepository, ItineraryLifecycleRepository {
  final planningKeys = <String>[];
  final acceptanceKeys = <String>[];
  final replanKeys = <String>[];

  static const alternative = PlanAlternative(
    id: 'alternative-010',
    profile: 'Cân bằng',
    activities: [],
    rank: 1,
    gatePassed: true,
    dataVersion: 'danang-v1',
    totalCost: 100000,
    totalKm: 2,
    totalMinutes: 90,
  );

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async {
    planningKeys.add(request['_idempotency_key'] as String);
    return const PlanningResult(items: [alternative], requestId: 'request-010');
  }

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) async {
    acceptanceKeys.add(key);
    return AcceptanceSummary(
      id: 'acceptance-010',
      versionId: 'version-010',
      selectedAt: DateTime.utc(2026, 11, 10),
    );
  }

  @override
  Future<List<ItineraryVersionSummary>> history(String tripId) async => [
    ItineraryVersionSummary(
      id: 'version-010',
      ordinal: 1,
      active: true,
      dataVersion: 'danang-v1',
      createdAt: DateTime.utc(2026, 11, 10),
      reason: 'accept',
    ),
  ];

  @override
  Future<void> activateVersion(String versionId, String key) async {}

  @override
  Future<PlanningResult> replan(
    String tripId,
    String sourceVersionId,
    String key, {
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
  }) async {
    replanKeys.add(key);
    return const PlanningResult(
      items: [alternative],
      requestId: 'replan-request-010',
    );
  }

  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {}

  @override
  Future<Map<String, dynamic>> readiness() async => {'status': 'ready'};
}

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

  test('retries reuse stable lifecycle keys', () async {
    final planning = _LifecyclePlanningRepository();
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: planning,
    );
    await state.initialize();

    await state.requestPlan();
    await state.requestPlan();
    await state.acceptAlternative(_LifecyclePlanningRepository.alternative);
    await state.acceptAlternative(_LifecyclePlanningRepository.alternative);
    await state.requestReplan();
    await state.requestReplan();

    expect(planning.planningKeys.toSet(), hasLength(1));
    expect(planning.acceptanceKeys.toSet(), hasLength(1));
    expect(planning.replanKeys.toSet(), hasLength(1));
    expect(state.currentPlanningRequestId, 'replan-request-010');
  });

  testWidgets('primary planning actions fit a 390x844 viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      DavelTraceApp(repository: FakeManagementRepository(seeded: true)),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('request-plan-button')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
