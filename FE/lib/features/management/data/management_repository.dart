import '../../../core/networking/api_client.dart';
import '../domain/models.dart';

abstract interface class ManagementRepository {
  Future<(List<UserProfile>, String?)> listProfiles();
  Future<UserProfile> createProfile(Map<String, dynamic> data);
  Future<UserProfile> updateProfile(String id, Map<String, dynamic> data);
  Future<UserProfile> resetProfile(UserProfile profile);
  Future<void> setActiveProfile(String id);
  Future<void> deleteProfile(UserProfile profile);
  Future<List<Trip>> listTrips(String profileId, {String? state});
  Future<Trip> createTrip(Map<String, dynamic> data);
  Future<Trip> updateTrip(String id, Map<String, dynamic> data);
  Future<void> deleteTrip(Trip trip);
  Future<Trip> archiveTrip(Trip trip);
  Future<Trip> restoreTrip(Trip trip);
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
  Future<Map<String, dynamic>> exportExpenses(
    String tripId, {
    String? date,
    String? category,
  });
  Future<List<PoiItem>> searchPois(String query);
  Future<PoiItem> getPoiDetails(String id);
  Future<RoutePreviewData> previewRoute(String tripId, List<String> ids);
}

abstract interface class LiveManagementRepository
    implements ManagementRepository {
  String? get activeTripId;
  set activeTripId(String? value);
  Future<void> setActiveTrip(Trip? trip);
}

class HttpManagementRepository implements LiveManagementRepository {
  HttpManagementRepository(this._api);

  final ApiClient _api;
  String? _profileId;
  final Map<String, String> _firstDayByTrip = {};
  final Map<String, Map<String, String>> _dayByTripDate = {};
  final Map<String, int> _dayVersionById = {};
  final Map<String, String> _tripByActivity = {};
  final Map<String, String> _dayByActivity = {};
  @override
  String? activeTripId;
  int _selectionVersion = 0;

  String _key(String operation) =>
      'mobile-$operation-${DateTime.now().microsecondsSinceEpoch}';

  @override
  Future<(List<UserProfile>, String?)> listProfiles() async {
    final json = await _api.get('/v1/profile') as Map<String, dynamic>;
    final raw = json['profile'] as Map<String, dynamic>?;
    if (raw == null) return (const <UserProfile>[], null);
    _profileId = raw['id'] as String;
    return ([UserProfile.fromJson(raw)], _profileId);
  }

  @override
  Future<UserProfile> createProfile(Map<String, dynamic> data) async {
    final json = await _api.put(
      '/v1/profile',
      body: {...data, 'expected_version': null},
    ) as Map<String, dynamic>;
    final profile = UserProfile.fromJson(
      json['profile'] as Map<String, dynamic>,
    );
    _profileId = profile.id;
    return profile;
  }

  @override
  Future<UserProfile> updateProfile(
    String id,
    Map<String, dynamic> data,
  ) async {
    final json = await _api.put(
      '/v1/profile',
      body: {...data, 'expected_version': data['version']},
    ) as Map<String, dynamic>;
    return UserProfile.fromJson(json['profile'] as Map<String, dynamic>);
  }

  @override
  Future<UserProfile> resetProfile(UserProfile profile) async {
    final json = await _api.post(
      '/v1/profile/reset',
      body: {'expected_version': profile.version},
    ) as Map<String, dynamic>;
    return UserProfile.fromJson(json['profile'] as Map<String, dynamic>);
  }

  @override
  Future<void> setActiveProfile(String id) async => _profileId = id;

  @override
  Future<void> deleteProfile(UserProfile profile) async {
    throw StateError('Hãy dùng chức năng xóa tài khoản để xóa hồ sơ sở hữu.');
  }

  @override
  Future<List<Trip>> listTrips(String profileId, {String? state}) async {
    final json = await _api.get(
      '/v1/trips',
      query: state == null ? const {} : {'state': state},
    ) as Map<String, dynamic>;
    activeTripId = json['active_trip_id'] as String?;
    _selectionVersion = json['selection_version'] as int? ?? 0;
    return (json['items'] as List)
        .map((item) => Trip.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> setActiveTrip(Trip? trip) async {
    final json = await _api.put(
      '/v1/trips/active',
      body: {
        'trip_id': trip?.id,
        'expected_selection_version': _selectionVersion,
      },
    ) as Map<String, dynamic>;
    activeTripId = json['active_trip_id'] as String?;
    _selectionVersion = json['version'] as int;
  }

  @override
  Future<Trip> createTrip(Map<String, dynamic> data) async => Trip.fromJson(
    await _api.post(
      '/v1/trips',
      headers: {'Idempotency-Key': _key('trip')},
      body: {
        'title': data['title'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'traveler_count': data['travelers'],
        'indicative_budget': data['budget_vnd'],
        'preferred_transport': data['transport'],
        'day_start': data['day_start'],
        'day_end': data['day_end'],
        'notes': data['notes'] ?? '',
        'preference_overrides': const {},
      },
    ) as Map<String, dynamic>,
  );

  @override
  Future<Trip> updateTrip(
    String id,
    Map<String, dynamic> data,
  ) async => Trip.fromJson(
    await _api.patch(
      '/v1/trips/$id',
      body: {
        'expected_version': data['version'],
        if (data['confirm_removed_days'] == true) 'confirm_removed_days': true,
        if (data['title'] != null) 'title': data['title'],
        if (data['start_date'] != null) 'start_date': data['start_date'],
        if (data['end_date'] != null) 'end_date': data['end_date'],
        if (data['travelers'] != null) 'traveler_count': data['travelers'],
        if (data['budget_vnd'] != null) 'indicative_budget': data['budget_vnd'],
        if (data['transport'] != null) 'preferred_transport': data['transport'],
        if (data['day_start'] != null) 'day_start': data['day_start'],
        if (data['day_end'] != null) 'day_end': data['day_end'],
      },
    ) as Map<String, dynamic>,
  );

  @override
  Future<void> deleteTrip(Trip trip) async {
    await _api.post(
      '/v1/trips/${trip.id}/deletion',
      body: {'expected_version': trip.version},
    );
    if (_profileId != null) await listTrips(_profileId!);
  }

  @override
  Future<Trip> archiveTrip(Trip trip) async {
    final result = Trip.fromJson(
      await _api.post(
        '/v1/trips/${trip.id}/archive',
        body: {'expected_version': trip.version},
      ) as Map<String, dynamic>,
    );
    if (_profileId != null) await listTrips(_profileId!);
    return result;
  }

  @override
  Future<Trip> restoreTrip(Trip trip) async => Trip.fromJson(
    await _api.post(
      '/v1/trips/${trip.id}/restore',
      body: {'expected_version': trip.version},
    ) as Map<String, dynamic>,
  );

  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) async {
    final json = await _api.get('/v1/trips/$id') as Map<String, dynamic>;
    final days = (json['days'] as List? ?? const []);
    final activities = <Map<String, dynamic>>[];
    final warnings = <String>[];
    _dayByTripDate[id] = {};
    for (final rawDay in days) {
      final day = rawDay as Map<String, dynamic>;
      final dayId = day['id'] as String;
      final date = day['date'] as String;
      _firstDayByTrip.putIfAbsent(id, () => dayId);
      _dayByTripDate[id]![date] = dayId;
      _dayVersionById[dayId] = day['version'] as int;
      warnings.addAll(List<String>.from(day['warnings'] as List? ?? const []));
      for (final raw in day['activities'] as List? ?? const []) {
        final item = Map<String, dynamic>.from(raw as Map);
        item['start_at'] = '${date}T${item['start_time'] ?? '09:00:00'}';
        item['end_at'] = '${date}T${item['end_time'] ?? '10:00:00'}';
        item['estimated_cost_vnd'] =
            (item['estimated_cost'] as num?)?.round() ?? 0;
        item['source'] = item['poi_id'] == null
            ? 'custom'
            : 'external_reference';
        item['category'] = item['kind'];
        item['latitude'] = 16.0544;
        item['longitude'] = 108.2022;
        _tripByActivity[item['id'] as String] = id;
        _dayByActivity[item['id'] as String] = dayId;
        activities.add(item);
      }
    }
    return (
      Trip.fromJson(json),
      ItineraryData(
        id: 'manual-$id',
        tripId: id,
        version: days.isEmpty
            ? 1
            : _dayVersionById[(days.first as Map<String, dynamic>)['id']] ?? 1,
        activities: activities.map(ActivityItem.fromJson).toList(),
        warnings: warnings,
      ),
      ExpenseSummaryData.empty,
    );
  }

  @override
  Future<ItineraryData> addActivity(
    String tripId,
    Map<String, dynamic> data,
  ) async {
    final date = data['start_at']?.toString().split('T').first;
    final dayId = date == null
        ? _firstDayByTrip[tripId]
        : _dayByTripDate[tripId]?[date];
    if (dayId == null) throw StateError('Chuyến đi chưa có ngày hợp lệ.');
    await _api.post(
      '/v1/trips/$tripId/days/$dayId/activities',
      headers: {'Idempotency-Key': _key('activity')},
      body: {
        'title': data['title'],
        'start_time': _timeOnly(data['start_at']),
        'end_time': _timeOnly(data['end_at']),
        'estimated_cost': data['estimated_cost_vnd'],
        'notes': data['notes'] ?? '',
        'kind': data['category'] ?? 'custom',
        'poi_id': data['poi_id'],
      },
    );
    return (await getTrip(tripId)).$2;
  }

  @override
  Future<ItineraryData> updateActivity(
    String id,
    Map<String, dynamic> data,
  ) async {
    await _api.patch(
      '/v1/activities/$id',
      body: {
        'expected_version': data['version'],
        if (data['title'] != null) 'title': data['title'],
        if (data['start_at'] != null) 'start_time': _timeOnly(data['start_at']),
        if (data['end_at'] != null) 'end_time': _timeOnly(data['end_at']),
        if (data['estimated_cost_vnd'] != null)
          'estimated_cost': data['estimated_cost_vnd'],
        if (data['notes'] != null) 'notes': data['notes'],
        if (data['category'] != null) 'kind': data['category'],
        if (data['progress_state'] != null)
          'progress_state': data['progress_state'],
      },
    );
    final tripId = data['trip_id'] as String? ?? _tripByActivity[id];
    if (tripId == null) throw StateError('Thiếu trip_id để làm mới hoạt động.');
    return (await getTrip(tripId)).$2;
  }

  @override
  Future<ItineraryData> deleteActivity(
    ActivityItem activity,
    int itineraryVersion,
  ) async {
    final tripId = _tripByActivity[activity.id];
    await _api.delete(
      '/v1/activities/${activity.id}',
      query: {'expected_version': '${activity.version}'},
    );
    if (tripId == null) throw StateError('Thiếu trip_id để làm mới hoạt động.');
    return (await getTrip(tripId)).$2;
  }

  @override
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int itineraryVersion,
  ) async {
    final dayId = ids.isEmpty ? null : _dayByActivity[ids.first];
    if (dayId == null) throw StateError('Chuyến đi chưa có ngày hợp lệ.');
    await _api.put(
      '/v1/trips/$tripId/days/$dayId/activities/order',
      body: {
        'activity_ids': ids,
        'expected_day_version': _dayVersionById[dayId] ?? itineraryVersion,
      },
    );
    return (await getTrip(tripId)).$2;
  }

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
      headers: {'Idempotency-Key': _key('expense')},
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
  Future<Map<String, dynamic>> exportExpenses(
    String tripId, {
    String? date,
    String? category,
  }) async => Map<String, dynamic>.from(
    await _api.get(
      '/v1/trips/$tripId/expenses/export',
      query: {'date': ?date, 'category': ?category},
    ) as Map,
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
  Future<PoiItem> getPoiDetails(String id) async => PoiItem.fromJson(
    await _api.get('/v1/pois/${Uri.encodeComponent(id)}')
        as Map<String, dynamic>,
  );

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

String? _timeOnly(Object? value) {
  if (value == null) return null;
  final text = value.toString();
  final marker = text.indexOf('T');
  return marker >= 0 ? text.substring(marker + 1) : text;
}
