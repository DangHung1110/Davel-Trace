import 'dart:async';

import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/core/errors/api_exception.dart';
import 'package:davel_trace/features/planning/data/planning_repository.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _AiRepository implements PlanningRepository, AiPlanningRepository {
  Map<String, dynamic>? submittedOverrides;

  @override
  Future<Map<String, dynamic>> aiReadiness() async => {
    'available': true,
    'capabilities': {'interpretation': true, 'explanation': true},
  };

  @override
  Future<AiInterpretationProposal> interpret(
    String tripId,
    String text,
  ) async => const AiInterpretationProposal(
    id: 'proposal-1',
    fields: {'indicative_budget': 3000000, 'traveler_count': 2},
    hardConstraints: {
      'must_visit': ['dragon-bridge'],
      'avoid': <String>[],
      'accessibility': ['wheelchair'],
    },
    softPreferences: {
      'activities': ['museum'],
      'food_preferences': ['seafood'],
    },
    assumptions: [],
    unresolved: ['Địa điểm bịa'],
    provider: 'gemini',
    model: 'gemini-test',
    externalProcessing: true,
  );

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async {
    submittedOverrides = Map<String, dynamic>.from(
      request['constraint_overrides'] as Map,
    );
    return const PlanningResult(
      items: [
        PlanAlternative(
          id: 'alternative-1',
          profile: 'balanced',
          activities: [],
          rank: 1,
          gatePassed: true,
          dataVersion: 'danang-v1',
          totalCost: 0,
          totalKm: 0,
          totalMinutes: 0,
        ),
      ],
    );
  }

  @override
  Future<PlanExplanation> explain(String alternativeId) async =>
      const PlanExplanation(
        source: 'deterministic',
        summary: 'Đạt cổng khả thi.',
        reasons: [],
        warnings: [],
      );

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) =>
      throw UnimplementedError();

  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {}

  @override
  Future<Map<String, dynamic>> readiness() async => {'status': 'ready'};
}

class _FailedAiRepository extends _AiRepository {
  @override
  Future<AiInterpretationProposal> interpret(String tripId, String text) async {
    throw const ApiException('LLM_QUOTA', 'AI hết quota; vẫn lập lịch được.');
  }
}

class _DelayedAiRepository extends _AiRepository {
  final pending = Completer<AiInterpretationProposal>();
  @override
  Future<AiInterpretationProposal> interpret(String tripId, String text) =>
      pending.future;
}

class _AmbiguousAiRepository extends _AiRepository {
  @override
  Future<AiInterpretationProposal> interpret(
    String tripId,
    String text,
  ) async => AiInterpretationProposal.fromJson({
    'proposal_id': 'ambiguous',
    'hard_constraints': {
      'must_visit': ['dragon-bridge'],
      'avoid': <String>[],
    },
    'place_resolutions': [
      {
        'constraint': 'must_visit',
        'name': 'An',
        'status': 'ambiguous',
        'candidates': [
          {'poi_id': 'an-1', 'name': 'An 1'},
          {'poi_id': 'an-2', 'name': 'An 2'},
        ],
      },
    ],
  });
}

void main() {
  test('pending local place resolution cannot bypass review; selected IDs reach planning', () async {
    SharedPreferences.setMockInitialValues({});
    final repository = _AmbiguousAiRepository();
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: repository,
    );
    addTearDown(state.dispose);
    await state.initialize();
    await state.interpretPlanningRequest('ghé An');
    await state.confirmAiProposalAndPlan();
    expect(repository.submittedOverrides, isNull);
    expect(state.aiProposal, isNotNull);
    await state.confirmAiProposalAndPlan(
      corrections: {
        'must_visit': ['dragon-bridge', 'an-2'],
        'avoid': <String>[],
      },
    );
    expect(repository.submittedOverrides?['must_visit'], [
      'dragon-bridge',
      'an-2',
    ]);
    expect(
      repository.submittedOverrides.toString(),
      isNot(contains('place_resolutions')),
    );
  });

  test(
    'explicitly dropping an ambiguous name preserves ordinary planning',
    () async {
      SharedPreferences.setMockInitialValues({});
      final repository = _AmbiguousAiRepository();
      final state = AppState(
        FakeManagementRepository(seeded: true),
        planningRepository: repository,
      );
      addTearDown(state.dispose);
      await state.initialize();
      await state.interpretPlanningRequest('ghé An');
      await state.confirmAiProposalAndPlan(
        corrections: {
          'must_visit': ['dragon-bridge'],
          'avoid': <String>[],
        },
      );
      expect(repository.submittedOverrides?['must_visit'], ['dragon-bridge']);
      expect(state.aiProposal, isNull);
    },
  );

  test('AI quota failure leaves structured planning enabled', () async {
    SharedPreferences.setMockInitialValues({});
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: _FailedAiRepository(),
    );
    await state.initialize();
    await state.interpretPlanningRequest('Đi biển buổi sáng');
    expect(state.aiMessage, contains('quota'));
    expect(state.aiProposal, isNull);
    expect(state.isPlanning, isFalse);
    await state.requestPlan();
    expect(state.demoSource, DemoSource.live);
    expect(state.errorMessage, isNull);
  });

  test('late interpretation after sign-out is discarded', () async {
    SharedPreferences.setMockInitialValues({});
    final repository = _DelayedAiRepository();
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: repository,
    );
    await state.initialize();
    final request = state.interpretPlanningRequest('Đi biển buổi sáng');
    await Future<void>.delayed(Duration.zero);
    state.clearForSignOut();
    repository.pending.complete(await _AiRepository().interpret('', ''));
    await request;
    expect(state.aiProposal, isNull);
    expect(state.isInterpreting, isFalse);
  });
  test(
    'only confirmed interpretation values reach deterministic planning',
    () async {
      SharedPreferences.setMockInitialValues({});
      final repository = _AiRepository();
      final state = AppState(
        FakeManagementRepository(seeded: true),
        planningRepository: repository,
      );
      await state.initialize();

      await state.interpretPlanningRequest('Đi 2 người và phải ghé Cầu Rồng');
      expect(state.aiProposal, isNotNull);
      expect(repository.submittedOverrides, isNull);

      await state.confirmAiProposalAndPlan();
      expect(repository.submittedOverrides?['must_visit'], ['dragon-bridge']);
      expect(repository.submittedOverrides?['food_preferences'], ['seafood']);
      expect(
        repository.submittedOverrides.toString(),
        isNot(contains('Địa điểm bịa')),
      );
    },
  );
}
