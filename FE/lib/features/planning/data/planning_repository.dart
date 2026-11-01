import '../../../core/networking/api_client.dart';
import '../domain/models.dart';

abstract interface class PlanningRepository {
  Future<PlanningResult> requestPlan(Map<String, dynamic> request);
  Future<AcceptanceSummary> accept(String itineraryId, String key);
  Future<Map<String, dynamic>> readiness();
  Future<void> logExpense(String tripId, Map<String, dynamic> expense);
}

class HttpPlanningRepository implements PlanningRepository {
  HttpPlanningRepository(this._api);
  final ApiClient _api;

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async {
    final json = await _api.post(
      '/v1/itinerary?diverse=true',
      body: {'trip': request},
    ) as Map<String, dynamic>;
    final pool = json['solution_pool'] as Map<String, dynamic>?;
    final shortage = pool?['shortage_reason'] as String?;
    final items = (json['plans'] as List? ?? const [])
        .map(
          (item) => PlanAlternative.fromJson(
            Map<String, dynamic>.from(item as Map),
            shortageReason: shortage,
          ),
        )
        .toList();
    return PlanningResult(items: items, shortageReason: shortage);
  }

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) async {
    final json = await _api.post(
      '/v1/itinerary/select',
      body: {'itinerary_id': itineraryId, 'idempotency_key': key},
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
}
