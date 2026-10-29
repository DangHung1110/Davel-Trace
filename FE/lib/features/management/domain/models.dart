class UserProfile {
  const UserProfile({
    required this.id,
    required this.displayName,
    required this.partyType,
    required this.tripPurpose,
    required this.spendingLevel,
    required this.pace,
    required this.fitness,
    required this.foodPreferences,
    required this.mustAvoid,
    required this.version,
  });

  final String id;
  final String displayName;
  final String partyType;
  final String tripPurpose;
  final int spendingLevel;
  final int pace;
  final int fitness;
  final List<String> foodPreferences;
  final List<String> mustAvoid;
  final int version;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
    id: json['id'] as String,
    displayName: json['display_name'] as String,
    partyType: json['party_type'] as String? ?? 'solo',
    tripPurpose: json['trip_purpose'] as String? ?? 'leisure',
    spendingLevel: json['spending_level'] as int? ?? 2,
    pace: json['pace'] as int? ?? 2,
    fitness: json['fitness'] as int? ?? 2,
    foodPreferences: List<String>.from(
      json['food_preferences'] as List? ?? const [],
    ),
    mustAvoid: List<String>.from(json['must_avoid'] as List? ?? const []),
    version: json['version'] as int,
  );
}

class Trip {
  const Trip({
    required this.id,
    required this.profileId,
    required this.title,
    required this.startDate,
    required this.endDate,
    required this.dayStart,
    required this.dayEnd,
    required this.travelers,
    required this.budgetVnd,
    required this.transport,
    required this.status,
    required this.version,
  });

  final String id;
  final String profileId;
  final String title;
  final DateTime startDate;
  final DateTime endDate;
  final String dayStart;
  final String dayEnd;
  final int travelers;
  final int budgetVnd;
  final String transport;
  final String status;
  final int version;

  factory Trip.fromJson(Map<String, dynamic> json) => Trip(
    id: json['id'] as String,
    profileId: json['profile_id'] as String,
    title: json['title'] as String,
    startDate: DateTime.parse(json['start_date'] as String),
    endDate: DateTime.parse(json['end_date'] as String),
    dayStart: json['day_start'] as String,
    dayEnd: json['day_end'] as String,
    travelers: json['travelers'] as int,
    budgetVnd: json['budget_vnd'] as int,
    transport: json['transport'] as String,
    status: json['status'] as String,
    version: json['version'] as int,
  );
}

class ActivityItem {
  const ActivityItem({
    required this.id,
    required this.position,
    required this.title,
    required this.notes,
    required this.latitude,
    required this.longitude,
    required this.startAt,
    required this.endAt,
    required this.category,
    required this.estimatedCostVnd,
    required this.source,
    required this.version,
    this.poiId,
  });

  final String id;
  final int position;
  final String? poiId;
  final String title;
  final String notes;
  final double latitude;
  final double longitude;
  final DateTime startAt;
  final DateTime endAt;
  final String category;
  final int estimatedCostVnd;
  final String source;
  final int version;

  factory ActivityItem.fromJson(Map<String, dynamic> json) => ActivityItem(
    id: json['id'] as String,
    position: json['position'] as int,
    poiId: json['poi_id'] as String?,
    title: json['title'] as String,
    notes: json['notes'] as String? ?? '',
    latitude: (json['latitude'] as num).toDouble(),
    longitude: (json['longitude'] as num).toDouble(),
    startAt: DateTime.parse(json['start_at'] as String),
    endAt: DateTime.parse(json['end_at'] as String),
    category: json['category'] as String,
    estimatedCostVnd: json['estimated_cost_vnd'] as int,
    source: json['source'] as String,
    version: json['version'] as int,
  );
}

class ItineraryData {
  const ItineraryData({
    required this.id,
    required this.tripId,
    required this.version,
    required this.activities,
    required this.warnings,
  });

  final String id;
  final String tripId;
  final int version;
  final List<ActivityItem> activities;
  final List<String> warnings;

  factory ItineraryData.fromJson(Map<String, dynamic> json) => ItineraryData(
    id: json['id'] as String,
    tripId: json['trip_id'] as String,
    version: json['version'] as int,
    activities: (json['activities'] as List? ?? const [])
        .map((item) => ActivityItem.fromJson(item as Map<String, dynamic>))
        .toList(),
    warnings: (json['warnings'] as List? ?? const [])
        .map((item) => (item as Map<String, dynamic>)['message'] as String)
        .toList(),
  );
}

class ExpenseItem {
  const ExpenseItem({
    required this.id,
    required this.label,
    required this.amountVnd,
    required this.category,
    required this.spentAt,
    required this.notes,
    required this.version,
  });

  final String id;
  final String label;
  final int amountVnd;
  final String category;
  final DateTime spentAt;
  final String notes;
  final int version;

  factory ExpenseItem.fromJson(Map<String, dynamic> json) => ExpenseItem(
    id: json['id'] as String,
    label: json['label'] as String,
    amountVnd: json['amount_vnd'] as int,
    category: json['category'] as String,
    spentAt: DateTime.parse(json['spent_at'] as String),
    notes: json['notes'] as String? ?? '',
    version: json['version'] as int,
  );
}

class ExpenseSummaryData {
  const ExpenseSummaryData({
    required this.budgetVnd,
    required this.spentVnd,
    required this.remainingVnd,
    required this.byCategory,
    required this.alert,
  });

  final int budgetVnd;
  final int spentVnd;
  final int remainingVnd;
  final Map<String, int> byCategory;
  final String alert;

  static const empty = ExpenseSummaryData(
    budgetVnd: 0,
    spentVnd: 0,
    remainingVnd: 0,
    byCategory: {},
    alert: 'none',
  );

  factory ExpenseSummaryData.fromJson(Map<String, dynamic> json) =>
      ExpenseSummaryData(
        budgetVnd: json['budget_vnd'] as int,
        spentVnd: json['spent_vnd'] as int,
        remainingVnd: json['remaining_vnd'] as int,
        byCategory: (json['by_category'] as Map<String, dynamic>).map(
          (key, value) => MapEntry(key, value as int),
        ),
        alert: json['alert'] as String,
      );
}

class PoiItem {
  const PoiItem({
    required this.id,
    required this.name,
    required this.type,
    required this.latitude,
    required this.longitude,
    required this.verified,
  });

  final String id;
  final String name;
  final String type;
  final double latitude;
  final double longitude;
  final bool verified;

  factory PoiItem.fromJson(Map<String, dynamic> json) => PoiItem(
    id: json['poi_id'] as String,
    name: json['name'] as String,
    type: json['type'] as String,
    latitude: (json['lat'] as num).toDouble(),
    longitude: (json['lon'] as num).toDouble(),
    verified: json['verified'] as bool? ?? false,
  );
}

class RoutePreviewData {
  const RoutePreviewData({
    required this.source,
    required this.isRealRoute,
    required this.distanceM,
    required this.durationS,
    this.warning,
  });

  final String source;
  final bool isRealRoute;
  final int distanceM;
  final int durationS;
  final String? warning;

  factory RoutePreviewData.fromJson(Map<String, dynamic> json) =>
      RoutePreviewData(
        source: json['source'] as String,
        isRealRoute: json['is_real_route'] as bool,
        distanceM: json['distance_m'] as int,
        durationS: json['duration_s'] as int,
        warning: json['warning'] as String?,
      );
}

String isoDate(DateTime value) =>
    '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';

String moneyVnd(int value) {
  final negative = value < 0;
  final digits = value.abs().toString();
  final output = StringBuffer();
  for (var index = 0; index < digits.length; index++) {
    if (index > 0 && (digits.length - index) % 3 == 0) output.write('.');
    output.write(digits[index]);
  }
  return '${negative ? '-' : ''}${output.toString()} ₫';
}
