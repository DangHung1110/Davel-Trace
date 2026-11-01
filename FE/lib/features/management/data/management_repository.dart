import '../../../core/networking/api_client.dart';
import '../domain/models.dart';

abstract interface class ManagementRepository {
  Future<(List<UserProfile>, String?)> listProfiles();
  Future<UserProfile> createProfile(Map<String, dynamic> data);
  Future<UserProfile> updateProfile(String id, Map<String, dynamic> data);
  Future<void> setActiveProfile(String id);
  Future<void> deleteProfile(UserProfile profile);
  Future<List<Trip>> listTrips(String profileId);
  Future<Trip> createTrip(Map<String, dynamic> data);
  Future<Trip> updateTrip(String id, Map<String, dynamic> data);
  Future<void> deleteTrip(Trip trip);
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id);
  Future<ItineraryData> addActivity(String tripId, Map<String, dynamic> data);
  Future<ItineraryData> updateActivity(String id, Map<String, dynamic> data);
  Future<ItineraryData> deleteActivity(
    ActivityItem activity,
    int itineraryVersion,
  );
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int itineraryVersion,
  );
  Future<(List<ExpenseItem>, ExpenseSummaryData)> listExpenses(String tripId);
  Future<(ExpenseItem, ExpenseSummaryData)> addExpense(
    String tripId,
    Map<String, dynamic> data,
  );
  Future<(ExpenseItem, ExpenseSummaryData)> updateExpense(
    String id,
    Map<String, dynamic> data,
  );
  Future<ExpenseSummaryData> deleteExpense(ExpenseItem expense);
  Future<List<PoiItem>> searchPois(String query);
  Future<RoutePreviewData> previewRoute(String tripId, List<String> ids);
}

class HttpManagementRepository implements ManagementRepository {
  HttpManagementRepository(this._api);

  final ApiClient _api;

  @override
  Future<(List<UserProfile>, String?)> listProfiles() async {
    final json = await _api.get('/v1/profiles') as Map<String, dynamic>;
    return (
      (json['items'] as List)
          .map((item) => UserProfile.fromJson(item as Map<String, dynamic>))
          .toList(),
      json['active_profile_id'] as String?,
    );
  }

  @override
  Future<UserProfile> createProfile(Map<String, dynamic> data) async =>
      UserProfile.fromJson(
        await _api.post('/v1/profiles', body: data) as Map<String, dynamic>,
      );

  @override
  Future<UserProfile> updateProfile(
    String id,
    Map<String, dynamic> data,
  ) async => UserProfile.fromJson(
    await _api.patch('/v1/profiles/$id', body: data) as Map<String, dynamic>,
  );

  @override
  Future<void> setActiveProfile(String id) async {
    await _api.put('/v1/profiles/$id/active');
  }

  @override
  Future<void> deleteProfile(UserProfile profile) => _api.delete(
    '/v1/profiles/${profile.id}',
    query: {'version': '${profile.version}', 'confirm': 'true'},
  );

  @override
  Future<List<Trip>> listTrips(String profileId) async {
    final json = await _api.get(
      '/v1/trips',
      query: {'profile_id': profileId},
    ) as Map<String, dynamic>;
    return (json['items'] as List)
        .map((item) => Trip.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Trip> createTrip(Map<String, dynamic> data) async => Trip.fromJson(
    await _api.post('/v1/trips', body: data) as Map<String, dynamic>,
  );

  @override
  Future<Trip> updateTrip(String id, Map<String, dynamic> data) async =>
      Trip.fromJson(
        await _api.patch('/v1/trips/$id', body: data) as Map<String, dynamic>,
      );

  @override
  Future<void> deleteTrip(Trip trip) => _api.delete(
    '/v1/trips/${trip.id}',
    query: {'version': '${trip.version}', 'confirm': 'true'},
  );

  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) async {
    final json = await _api.get('/v1/trips/$id') as Map<String, dynamic>;
    return (
      Trip.fromJson(json),
      ItineraryData.fromJson(json['itinerary'] as Map<String, dynamic>),
      ExpenseSummaryData.fromJson(
        json['expense_summary'] as Map<String, dynamic>,
      ),
    );
  }

  @override
  Future<ItineraryData> addActivity(
    String tripId,
    Map<String, dynamic> data,
  ) async => ItineraryData.fromJson(
    await _api.post('/v1/trips/$tripId/activities', body: data)
        as Map<String, dynamic>,
  );

  @override
  Future<ItineraryData> updateActivity(
    String id,
    Map<String, dynamic> data,
  ) async => ItineraryData.fromJson(
    await _api.patch('/v1/activities/$id', body: data) as Map<String, dynamic>,
  );

  @override
  Future<ItineraryData> deleteActivity(
    ActivityItem activity,
    int itineraryVersion,
  ) async => ItineraryData.fromJson(
    await _api.delete(
      '/v1/activities/${activity.id}',
      query: {
        'version': '${activity.version}',
        'itinerary_version': '$itineraryVersion',
      },
    ) as Map<String, dynamic>,
  );

  @override
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int itineraryVersion,
  ) async => ItineraryData.fromJson(
    await _api.put(
      '/v1/trips/$tripId/activities/order',
      body: {'activity_ids': ids, 'itinerary_version': itineraryVersion},
    ) as Map<String, dynamic>,
  );

  @override
  Future<(List<ExpenseItem>, ExpenseSummaryData)> listExpenses(
    String tripId,
  ) async {
    final json =
        await _api.get('/v1/trips/$tripId/expenses') as Map<String, dynamic>;
    return (
      (json['items'] as List)
          .map((item) => ExpenseItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      ExpenseSummaryData.fromJson(json['summary'] as Map<String, dynamic>),
    );
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> addExpense(
    String tripId,
    Map<String, dynamic> data,
  ) async {
    final json = await _api.post(
      '/v1/trips/$tripId/expenses',
      body: data,
    ) as Map<String, dynamic>;
    return (
      ExpenseItem.fromJson(json['expense'] as Map<String, dynamic>),
      ExpenseSummaryData.fromJson(json['summary'] as Map<String, dynamic>),
    );
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> updateExpense(
    String id,
    Map<String, dynamic> data,
  ) async {
    final json = await _api.patch(
      '/v1/expenses/$id',
      body: data,
    ) as Map<String, dynamic>;
    return (
      ExpenseItem.fromJson(json['expense'] as Map<String, dynamic>),
      ExpenseSummaryData.fromJson(json['summary'] as Map<String, dynamic>),
    );
  }

  @override
  Future<ExpenseSummaryData> deleteExpense(ExpenseItem expense) async =>
      ExpenseSummaryData.fromJson(
        await _api.delete(
          '/v1/expenses/${expense.id}',
          query: {'version': '${expense.version}'},
        ) as Map<String, dynamic>,
      );

  @override
  Future<List<PoiItem>> searchPois(String query) async {
    final json = await _api.get(
      '/v1/pois',
      query: {'q': query, 'limit': '30'},
    ) as Map<String, dynamic>;
    return (json['items'] as List)
        .map((item) => PoiItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<RoutePreviewData> previewRoute(
    String tripId,
    List<String> ids,
  ) async => RoutePreviewData.fromJson(
    await _api.post(
      '/v1/routes/preview',
      body: {'trip_id': tripId, 'activity_ids': ids, 'mode': 'driving'},
    ) as Map<String, dynamic>,
  );
}
