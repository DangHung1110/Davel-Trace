import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/core/errors/api_exception.dart';
import 'package:davel_trace/features/planning/data/planning_repository.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _FailingAcceptanceRepository implements PlanningRepository {
  static const alternative = PlanAlternative(
    id: 'live-plan-1',
    profile: 'Cân bằng',
    activities: [],
    rank: 1,
    gatePassed: true,
    dataVersion: 'danang-v1',
    totalCost: 100000,
    totalKm: 4,
    totalMinutes: 120,
  );

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async =>
      const PlanningResult(items: [alternative]);

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) {
    throw const ApiException(
      'DATABASE_UNAVAILABLE',
      'Không thể lưu trên server.',
      statusCode: 503,
    );
  }

  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {}

  @override
  Future<Map<String, dynamic>> readiness() async => {'status': 'ready'};
}

void main() {
  test('failed production acceptance is never reported as persisted', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: _FailingAcceptanceRepository(),
    );
    await state.initialize();
    await state.requestPlan();
    expect(state.demoSource, DemoSource.live);

    await state.acceptAlternative(_FailingAcceptanceRepository.alternative);

    expect(state.acceptance, isNull);
    expect(state.plannerMessage, contains('Chưa thể chốt trên server'));
    expect(state.errorMessage, 'Không thể lưu trên server.');
  });

  test('seeded demo choice remains explicitly local', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(FakeManagementRepository(seeded: true));
    await state.initialize();
    final alternative = state.planAlternatives.first;

    await state.acceptAlternative(alternative);

    expect(state.acceptance, isNull);
    expect(state.plannerMessage, contains('chưa tạo acceptance trên server'));
  });
}
