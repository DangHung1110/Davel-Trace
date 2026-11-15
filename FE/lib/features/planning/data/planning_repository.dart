import '../../../core/networking/api_client.dart';
import '../domain/models.dart';

abstract interface class PlanningRepository {
  Future<PlanningResult> requestPlan(Map<String, dynamic> request);
  Future<AcceptanceSummary> accept(String itineraryId, String key);
  Future<Map<String, dynamic>> readiness();
  Future<void> logExpense(String tripId, Map<String, dynamic> expense);
}

abstract interface class ItineraryLifecycleRepository {
  Future<List<ItineraryVersionSummary>> history(String tripId);
  Future<void> activateVersion(String versionId, String key);
  Future<PlanningResult> replan(
    String tripId,
    String sourceVersionId,
    String key, {
    List<String> completedActivityIds,
    List<String> skippedActivityIds,
  });
}

abstract interface class AiPlanningRepository {
  Future<Map<String, dynamic>> aiReadiness();
  Future<AiInterpretationProposal> interpret(String tripId, String text);
  Future<PlanExplanation> explain(String alternativeId);
}

class HttpPlanningRepository
    implements
        PlanningRepository,
        ItineraryLifecycleRepository,
        AiPlanningRepository {
  HttpPlanningRepository(this._api);
  final ApiClient _api;

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async {
    final json = await _api.post(
      '/v1/trips/${request['trip_id']}/planning-requests',
      headers: {'Idempotency-Key': request['_idempotency_key'] as String},
      body: {
        'target_count': request['target_count'] ?? 5,
        'constraint_overrides': request['constraint_overrides'] ?? const {},
      },
    ) as Map<String, dynamic>;
    final shortage = json['shortage_reason'] as String?;
    final items = (json['alternatives'] as List? ?? const [])
        .map(
          (item) => PlanAlternative.fromJson(
            Map<String, dynamic>.from(item as Map),
            shortageReason: shortage,
          ),
        )
        .toList();
    return PlanningResult(
      items: items,
      shortageReason: shortage,
      requestId: json['request_id'] as String?,
      status: json['status'] as String? ?? 'completed',
      failureCode: json['failure_code'] as String?,
    );
  }

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) async {
    final json = await _api.post(
      '/v1/itinerary-alternatives/$itineraryId/accept',
      headers: {'Idempotency-Key': key},
    ) as Map<String, dynamic>;
    return AcceptanceSummary.fromJson(
      Map<String, dynamic>.from(json['acceptance'] as Map),
    );
  }

  @override
  Future<Map<String, dynamic>> readiness() async => Map<String, dynamic>.from(
    await _api.get('/v1/planning/readiness') as Map,
  );

  @override
  Future<Map<String, dynamic>> aiReadiness() async =>
      Map<String, dynamic>.from(await _api.get('/v1/ai/readiness') as Map);

  @override
  Future<AiInterpretationProposal> interpret(
    String tripId,
    String text,
  ) async => AiInterpretationProposal.fromJson(
    Map<String, dynamic>.from(
      await _api.post(
        '/v1/trips/$tripId/ai/interpretations',
        body: {'text': text},
      ) as Map,
    ),
  );

  @override
  Future<PlanExplanation> explain(String alternativeId) async =>
      PlanExplanation.fromJson(
        Map<String, dynamic>.from(
          await _api.post(
            '/v1/itinerary-alternatives/$alternativeId/ai/explanation',
          ) as Map,
        ),
      );

  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {
    await _api.post(
      '/v1/expenses',
      body: {
        'trip_id': tripId,
        'label': expense['label'],
        'amount': expense['amount_vnd'],
        'kind': expense['category'],
        'at': expense['spent_at'],
      },
    );
  }

  @override
  Future<List<ItineraryVersionSummary>> history(String tripId) async {
    final json = Map<String, dynamic>.from(
      await _api.get('/v1/trips/$tripId/itinerary-versions') as Map,
    );
    return (json['items'] as List? ?? const [])
        .map(
          (item) => ItineraryVersionSummary.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  @override
  Future<void> activateVersion(String versionId, String key) async {
    await _api.post(
      '/v1/itinerary-versions/$versionId/activate',
      headers: {'Idempotency-Key': key},
    );
  }

  @override
  Future<PlanningResult> replan(
    String tripId,
    String sourceVersionId,
    String key, {
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
  }) async {
    final json = Map<String, dynamic>.from(
      await _api.post(
        '/v1/trips/$tripId/replans',
        headers: {'Idempotency-Key': key},
        body: {
          'source_version_id': sourceVersionId,
          'completed_activity_ids': completedActivityIds,
          'skipped_activity_ids': skippedActivityIds,
          'target_count': 5,
        },
      ) as Map,
    );
    final shortage = json['shortage_reason'] as String?;
    return PlanningResult(
      items: (json['alternatives'] as List? ?? const [])
          .map(
            (item) => PlanAlternative.fromJson(
              Map<String, dynamic>.from(item as Map),
              shortageReason: shortage,
            ),
          )
          .toList(),
      shortageReason: shortage,
      requestId: json['request_id'] as String?,
      status: json['status'] as String? ?? 'completed',
      failureCode: json['failure_code'] as String?,
    );
  }
}
