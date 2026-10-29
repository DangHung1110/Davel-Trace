import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/api/api_exception.dart';

class FakeManagementRepository implements ManagementRepository {
  FakeManagementRepository({bool seeded = false}) {
    if (seeded) {
      profiles.add(_profile('profile-1', 'Đặng Hùng'));
      activeProfileId = 'profile-1';
      trips.add(_trip('trip-1', 'profile-1', 'Cuối tuần Đà Nẵng'));
    }
  }

  final List<UserProfile> profiles = [];
  final List<Trip> trips = [];
  final List<ExpenseItem> expenses = [];
  String? activeProfileId;
  bool failListProfiles = false;
  int _itineraryVersion = 1;
  final List<ActivityItem> activities = [];

  static UserProfile _profile(String id, String name) => UserProfile(
    id: id,
    displayName: name,
    partyType: 'solo',
    tripPurpose: 'leisure',
    spendingLevel: 2,
    pace: 2,
    fitness: 2,
    foodPreferences: const [],
    mustAvoid: const [],
    version: 1,
  );

  static Trip _trip(String id, String profileId, String title) => Trip(
    id: id,
    profileId: profileId,
    title: title,
    startDate: DateTime(2026, 10, 17),
    endDate: DateTime(2026, 10, 18),
    dayStart: '07:00:00',
    dayEnd: '21:00:00',
    travelers: 2,
    budgetVnd: 3000000,
    transport: 'motorbike',
    status: 'draft',
    version: 1,
  );

  ItineraryData get itinerary => ItineraryData(
    id: 'itinerary-1',
    tripId: trips.first.id,
    version: _itineraryVersion,
    activities: [...activities],
    warnings: const [],
  );

  ExpenseSummaryData get summary {
    final spent = expenses.fold(
      0,
      (total, expense) => total + expense.amountVnd,
    );
    final budget = trips.isEmpty ? 0 : trips.first.budgetVnd;
    return ExpenseSummaryData(
      budgetVnd: budget,
      spentVnd: spent,
      remainingVnd: budget - spent,
      byCategory: {},
      alert: spent >= budget && spent > 0 ? '100' : 'none',
    );
  }

  @override
  Future<(List<UserProfile>, String?)> listProfiles() async {
    if (failListProfiles) {
      throw const ApiException('NETWORK_ERROR', 'Backend test chưa sẵn sàng.');
    }
    return ([...profiles], activeProfileId);
  }

  @override
  Future<UserProfile> createProfile(Map<String, dynamic> data) async {
    final item = _profile(
      'profile-${profiles.length + 1}',
      data['display_name'] as String,
    );
    profiles.add(item);
    activeProfileId = item.id;
    return item;
  }

  @override
  Future<UserProfile> updateProfile(
    String id,
    Map<String, dynamic> data,
  ) async {
    final old = profiles.firstWhere((item) => item.id == id);
    final updated = UserProfile(
      id: old.id,
      displayName: data['display_name'] as String? ?? old.displayName,
      partyType: data['party_type'] as String? ?? old.partyType,
      tripPurpose: data['trip_purpose'] as String? ?? old.tripPurpose,
      spendingLevel: data['spending_level'] as int? ?? old.spendingLevel,
      pace: data['pace'] as int? ?? old.pace,
      fitness: data['fitness'] as int? ?? old.fitness,
      foodPreferences: List<String>.from(
        data['food_preferences'] as List? ?? old.foodPreferences,
      ),
      mustAvoid: List<String>.from(
        data['must_avoid'] as List? ?? old.mustAvoid,
      ),
      version: old.version + 1,
    );
    profiles[profiles.indexOf(old)] = updated;
    return updated;
  }

  @override
  Future<void> setActiveProfile(String id) async => activeProfileId = id;

  @override
  Future<void> deleteProfile(UserProfile profile) async {
    profiles.removeWhere((item) => item.id == profile.id);
  }

  @override
  Future<List<Trip>> listTrips(String profileId) async =>
      trips.where((trip) => trip.profileId == profileId).toList();

  @override
  Future<Trip> createTrip(Map<String, dynamic> data) async {
    final trip = Trip(
      id: 'trip-${trips.length + 1}',
      profileId: data['profile_id'] as String,
      title: data['title'] as String,
      startDate: DateTime.parse(data['start_date'] as String),
      endDate: DateTime.parse(data['end_date'] as String),
      dayStart: data['day_start'] as String,
      dayEnd: data['day_end'] as String,
      travelers: data['travelers'] as int,
      budgetVnd: data['budget_vnd'] as int,
      transport: data['transport'] as String,
      status: 'draft',
      version: 1,
    );
    trips.add(trip);
    return trip;
  }

  @override
  Future<Trip> updateTrip(String id, Map<String, dynamic> data) async {
    final old = trips.firstWhere((item) => item.id == id);
    final updated = Trip(
      id: old.id,
      profileId: old.profileId,
      title: data['title'] as String? ?? old.title,
      startDate: data['start_date'] == null
          ? old.startDate
          : DateTime.parse(data['start_date'] as String),
      endDate: data['end_date'] == null
          ? old.endDate
          : DateTime.parse(data['end_date'] as String),
      dayStart: data['day_start'] as String? ?? old.dayStart,
      dayEnd: data['day_end'] as String? ?? old.dayEnd,
      travelers: data['travelers'] as int? ?? old.travelers,
      budgetVnd: data['budget_vnd'] as int? ?? old.budgetVnd,
      transport: data['transport'] as String? ?? old.transport,
      status: data['status'] as String? ?? old.status,
      version: old.version + 1,
    );
    trips[trips.indexOf(old)] = updated;
    return updated;
  }

  @override
  Future<void> deleteTrip(Trip trip) async => trips.remove(trip);

  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) async =>
      (trips.firstWhere((trip) => trip.id == id), itinerary, summary);

  @override
  Future<ItineraryData> addActivity(
    String tripId,
    Map<String, dynamic> data,
  ) async {
    final item = ActivityItem(
      id: 'activity-${activities.length + 1}',
      position: activities.length,
      poiId: data['poi_id'] as String?,
      title: data['title'] as String,
      notes: data['notes'] as String,
      latitude: data['latitude'] as double,
      longitude: data['longitude'] as double,
      startAt: DateTime.parse(data['start_at'] as String),
      endAt: DateTime.parse(data['end_at'] as String),
      category: data['category'] as String,
      estimatedCostVnd: data['estimated_cost_vnd'] as int,
      source: 'manual',
      version: 1,
    );
    activities.add(item);
    _itineraryVersion++;
    return itinerary;
  }

  @override
  Future<ItineraryData> updateActivity(
    String id,
    Map<String, dynamic> data,
  ) async => itinerary;

  @override
  Future<ItineraryData> deleteActivity(
    ActivityItem activity,
    int itineraryVersion,
  ) async {
    activities.remove(activity);
    _itineraryVersion++;
    return itinerary;
  }

  @override
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int itineraryVersion,
  ) async {
    final byId = {for (final item in activities) item.id: item};
    final ordered = ids.map((id) => byId[id]!).toList();
    activities
      ..clear()
      ..addAll(ordered);
    _itineraryVersion++;
    return itinerary;
  }

  @override
  Future<(List<ExpenseItem>, ExpenseSummaryData)> listExpenses(
    String tripId,
  ) async => ([...expenses], summary);

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> addExpense(
    String tripId,
    Map<String, dynamic> data,
  ) async {
    final item = ExpenseItem(
      id: 'expense-${expenses.length + 1}',
      label: data['label'] as String,
      amountVnd: data['amount_vnd'] as int,
      category: data['category'] as String,
      spentAt: DateTime.parse(data['spent_at'] as String),
      notes: data['notes'] as String,
      version: 1,
    );
    expenses.add(item);
    return (item, summary);
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> updateExpense(
    String id,
    Map<String, dynamic> data,
  ) async {
    final item = expenses.firstWhere((expense) => expense.id == id);
    return (item, summary);
  }

  @override
  Future<ExpenseSummaryData> deleteExpense(ExpenseItem expense) async {
    expenses.remove(expense);
    return summary;
  }

  @override
  Future<List<PoiItem>> searchPois(String query) async => const [
    PoiItem(
      id: 'dragon-bridge',
      name: 'Cầu Rồng',
      type: 'Điểm tham quan',
      latitude: 16.0611,
      longitude: 108.2274,
      verified: false,
    ),
  ];

  @override
  Future<RoutePreviewData> previewRoute(
    String tripId,
    List<String> ids,
  ) async => const RoutePreviewData(
    source: 'osrm',
    isRealRoute: true,
    distanceM: 3200,
    durationS: 720,
  );
}
