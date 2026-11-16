import 'dart:async';

import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/features/planning/data/planning_repository.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _CountingManagement extends FakeManagementRepository {
  _CountingManagement() : super(seeded: true);
  int detailLoads = 0;
  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) {
    detailLoads++;
    return super.getTrip(id);
  }
}

class _Planning implements PlanningRepository, ItineraryLifecycleRepository {
  Completer<PlanningResult>? pending;
  int accepts = 0;
  static const alternative = PlanAlternative(
    id: 'server-alternative',
    profile: 'Cân bằng',
    activities: [],
    rank: 1,
    gatePassed: true,
    dataVersion: 'test',
    totalCost: 0,
    totalKm: 0,
    totalMinutes: 0,
  );
  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async =>
      pending == null
      ? const PlanningResult(items: [alternative], requestId: 'request-trip-a')
      : pending!.future;
  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) async {
    accepts++;
    return AcceptanceSummary(
      id: 'accepted-trip-a',
      versionId: 'version-a',
      selectedAt: DateTime(2026),
    );
  }

  @override
  Future<Map<String, dynamic>> readiness() async => {};
  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {}
  @override
  Future<List<ItineraryVersionSummary>> history(String tripId) async => [];
  @override
  Future<void> activateVersion(String versionId, String key) async {}
  @override
  Future<PlanningResult> replan(
    String tripId,
    String sourceVersionId,
    String key, {
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
  }) => requestPlan({});
}

const _tripB = {
  'title': 'Chuyến thứ hai',
  'start_date': '2026-11-18',
  'end_date': '2026-11-19',
  'travelers': 2,
  'budget_vnd': 3000000,
  'transport': 'car',
  'day_start': '08:00:00',
  'day_end': '18:00:00',
};

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test(
    'changing trips clears alternatives and cannot accept a previous trip plan',
    () async {
      final planner = _Planning();
      final state = AppState(
        _CountingManagement(),
        planningRepository: planner,
      );
      await state.initialize();
      await state.requestPlan();
      expect(state.currentPlanningRequestId, 'request-trip-a');
      await state.createTrip(_tripB);
      expect(state.activeTrip?.id, 'trip-2');
      expect(state.activeAlternative, isNull);
      expect(state.currentPlanningRequestId, isNull);
      await state.acceptAlternative(_Planning.alternative);
      expect(planner.accepts, 0);
      state.dispose();
    },
  );

  test('late planning results cannot populate a different trip', () async {
    final planner = _Planning()..pending = Completer<PlanningResult>();
    final state = AppState(_CountingManagement(), planningRepository: planner);
    await state.initialize();
    final request = state.requestPlan();
    await state.createTrip(_tripB);
    planner.pending!.complete(
      const PlanningResult(
        items: [_Planning.alternative],
        requestId: 'old-request',
      ),
    );
    await request;
    expect(state.activeTrip?.id, 'trip-2');
    expect(
      state.planAlternatives.any((p) => p.id == 'server-alternative'),
      isFalse,
    );
    expect(state.currentPlanningRequestId, isNull);
    expect(state.isPlanning, isFalse);
    state.dispose();
  });

  test(
    'accepting and activating a saved version reload the displayed itinerary',
    () async {
      final management = _CountingManagement();
      final state = AppState(management, planningRepository: _Planning());
      await state.initialize();
      final initialLoads = management.detailLoads;
      await state.requestPlan();
      await state.acceptAlternative(_Planning.alternative);
      expect(state.acceptance?.id, 'accepted-trip-a');
      expect(management.detailLoads, initialLoads + 1);
      await state.activateItineraryVersion(
        ItineraryVersionSummary(
          id: 'old-version',
          ordinal: 1,
          active: false,
          dataVersion: 'test',
          createdAt: DateTime(2026),
          reason: 'accept',
        ),
      );
      expect(management.detailLoads, initialLoads + 2);
      state.dispose();
    },
  );

  test('late planning response after sign out/dispose is ignored', () async {
    final planner = _Planning()..pending = Completer<PlanningResult>();
    final state = AppState(_CountingManagement(), planningRepository: planner);
    await state.initialize();
    final request = state.requestPlan();
    state.clearForSignOut();
    state.dispose();
    planner.pending!.complete(
      const PlanningResult(items: [_Planning.alternative]),
    );
    await request;
    expect(state.activeAlternative, isNull);
    expect(state.currentPlanningRequestId, isNull);
  });
}
