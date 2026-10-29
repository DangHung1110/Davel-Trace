import '../domain/models.dart';
import 'management_repository.dart';

/// Device-local management kit used by the laptop demo. Planner intelligence
/// still comes from FastAPI; these CRUD objects keep the UI usable offline.
class DemoManagementRepository implements ManagementRepository {
  DemoManagementRepository() {
    profiles.add(_profile('profile-demo', 'Đặng Hùng'));
    trips.add(_trip('trip-demo', 'profile-demo', 'Một ngày Đà Nẵng'));
    activities.addAll(_seedActivities());
  }

  final profiles = <UserProfile>[];
  final trips = <Trip>[];
  final activities = <ActivityItem>[];
  final expenses = <ExpenseItem>[];
  String? activeProfileId = 'profile-demo';
  int itineraryVersion = 1;

  UserProfile _profile(String id, String name) => UserProfile(
    id: id,
    displayName: name,
    partyType: 'couple',
    tripPurpose: 'discovery',
    spendingLevel: 2,
    pace: 2,
    fitness: 2,
    foodPreferences: const ['mì Quảng', 'hải sản'],
    mustAvoid: const ['bar ồn'],
    version: 1,
  );

  Trip _trip(String id, String profileId, String title) => Trip(
    id: id,
    profileId: profileId,
    title: title,
    startDate: DateTime(2026, 10, 28),
    endDate: DateTime(2026, 10, 28),
    dayStart: '07:00:00',
    dayEnd: '19:00:00',
    travelers: 2,
    budgetVnd: 3000000,
    transport: 'motorbike',
    status: 'draft',
    version: 1,
  );

  List<ActivityItem> _seedActivities() => [
    ActivityItem(
      id: 'act-1',
      position: 0,
      poiId: 'son-tra',
      title: 'Bán đảo Sơn Trà',
      notes: 'Ngắm thành phố buổi sáng',
      latitude: 16.105,
      longitude: 108.278,
      startAt: DateTime(2026, 10, 28, 7, 30),
      endAt: DateTime(2026, 10, 28, 9, 30),
      category: 'nature',
      estimatedCostVnd: 0,
      source: 'seeded',
      version: 1,
    ),
    ActivityItem(
      id: 'act-2',
      position: 1,
      poiId: 'cham-museum',
      title: 'Bảo tàng Điêu khắc Chăm',
      notes: 'Điểm văn hóa trong nhà',
      latitude: 16.0603,
      longitude: 108.2235,
      startAt: DateTime(2026, 10, 28, 14),
      endAt: DateTime(2026, 10, 28, 15, 30),
      category: 'museum',
      estimatedCostVnd: 60000,
      source: 'seeded',
      version: 1,
    ),
    ActivityItem(
      id: 'act-3',
      position: 2,
      poiId: 'my-khe',
      title: 'Biển Mỹ Khê',
      notes: 'Hoàng hôn',
      latitude: 16.061,
      longitude: 108.247,
      startAt: DateTime(2026, 10, 28, 16, 30),
      endAt: DateTime(2026, 10, 28, 18),
      category: 'beach',
      estimatedCostVnd: 0,
      source: 'seeded',
      version: 1,
    ),
  ];

  ItineraryData get itinerary => ItineraryData(
    id: 'it-demo',
    tripId: trips.first.id,
    version: itineraryVersion,
    activities: [...activities],
    warnings: const ['Dữ liệu lịch quản lý đang ở chế độ demo trên thiết bị.'],
  );

  ExpenseSummaryData get summary {
    final spent = expenses.fold<int>(0, (sum, item) => sum + item.amountVnd);
    final budget = trips.isEmpty ? 0 : trips.first.budgetVnd;
    return ExpenseSummaryData(
      budgetVnd: budget,
      spentVnd: spent,
      remainingVnd: budget - spent,
      byCategory: const {},
      alert: spent >= budget && spent > 0 ? '100' : 'none',
    );
  }

  @override
  Future<(List<UserProfile>, String?)> listProfiles() async =>
      ([...profiles], activeProfileId);
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
    final item = UserProfile(
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
    profiles[profiles.indexOf(old)] = item;
    return item;
  }

  @override
  Future<void> setActiveProfile(String id) async => activeProfileId = id;
  @override
  Future<void> deleteProfile(UserProfile profile) async =>
      profiles.remove(profile);
  @override
  Future<List<Trip>> listTrips(String profileId) async =>
      trips.where((item) => item.profileId == profileId).toList();
  @override
  Future<Trip> createTrip(Map<String, dynamic> data) async {
    final item = _trip(
      'trip-${trips.length + 1}',
      data['profile_id'] as String,
      data['title'] as String,
    );
    trips.add(item);
    return item;
  }

  @override
  Future<Trip> updateTrip(String id, Map<String, dynamic> data) async =>
      trips.firstWhere((item) => item.id == id);
  @override
  Future<void> deleteTrip(Trip trip) async => trips.remove(trip);
  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) async =>
      (trips.firstWhere((item) => item.id == id), itinerary, summary);
  @override
  Future<ItineraryData> addActivity(
    String tripId,
    Map<String, dynamic> data,
  ) async {
    activities.add(
      ActivityItem(
        id: 'act-${activities.length + 1}',
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
      ),
    );
    itineraryVersion++;
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
    int version,
  ) async {
    activities.remove(activity);
    itineraryVersion++;
    return itinerary;
  }

  @override
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int version,
  ) async {
    final byId = {for (final item in activities) item.id: item};
    activities
      ..clear()
      ..addAll(ids.map((id) => byId[id]!));
    itineraryVersion++;
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
  ) async => (expenses.firstWhere((item) => item.id == id), summary);
  @override
  Future<ExpenseSummaryData> deleteExpense(ExpenseItem expense) async {
    expenses.remove(expense);
    return summary;
  }

  @override
  Future<List<PoiItem>> searchPois(String query) async => const [];
  @override
  Future<RoutePreviewData> previewRoute(
    String tripId,
    List<String> ids,
  ) async => const RoutePreviewData(
    source: 'osrm',
    isRealRoute: true,
    distanceM: 24600,
    durationS: 3600,
  );
}
