enum DemoSource { seeded, live, stale }

class PlanAlternative {
  const PlanAlternative({
    required this.id,
    required this.profile,
    required this.activities,
    required this.rank,
    required this.gatePassed,
    required this.dataVersion,
    required this.totalCost,
    required this.totalKm,
    required this.totalMinutes,
    this.shortageReason,
  });

  final String id;
  final String profile;
  final List<Map<String, dynamic>> activities;
  final int rank;
  final bool gatePassed;
  final String dataVersion;
  final int totalCost;
  final double totalKm;
  final int totalMinutes;
  final String? shortageReason;

  factory PlanAlternative.fromJson(
    Map<String, dynamic> json, {
    String? shortageReason,
  }) {
    final plan = json['plan'] is Map
        ? Map<String, dynamic>.from(json['plan'] as Map)
        : json;
    final gate = json['gate'] is Map
        ? json['gate'] as Map
        : plan['gate'] as Map?;
    return PlanAlternative(
      id: json['alternative_id'] as String? ?? plan['itinerary_id'] as String,
      profile:
          json['profile'] as String? ??
          plan['profile'] as String? ??
          'balanced',
      activities: (plan['activities'] as List? ?? const [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
      rank:
          json['deterministic_rank'] as int? ??
          plan['deterministic_rank'] as int? ??
          plan['diverse_rank'] as int? ??
          1,
      gatePassed: gate?['passed'] as bool? ?? true,
      dataVersion:
          json['data_version'] as String? ??
          plan['data_version'] as String? ??
          'unknown',
      totalCost: (plan['total_cost'] as num?)?.round() ?? 0,
      totalKm: (plan['total_km'] as num?)?.toDouble() ?? 0,
      totalMinutes: (plan['total_min'] as num?)?.round() ?? 0,
      shortageReason: shortageReason,
    );
  }

  static List<PlanAlternative> seeded() => const [
    PlanAlternative(
      id: 'seeded-balanced',
      profile: 'Cân bằng',
      activities: [
        {'poi_id': 'son-tra', 'start': '07:30', 'end': '09:30'},
        {'poi_id': 'mi-quang', 'start': '11:30', 'end': '12:30'},
        {'poi_id': 'cham-museum', 'start': '14:00', 'end': '15:30'},
        {'poi_id': 'my-khe', 'start': '16:30', 'end': '18:00'},
      ],
      rank: 1,
      gatePassed: true,
      dataVersion: 'seed-demo-2026-10-28',
      totalCost: 420000,
      totalKm: 24.6,
      totalMinutes: 390,
    ),
    PlanAlternative(
      id: 'seeded-relaxed',
      profile: 'Thư thả',
      activities: [
        {'poi_id': 'cham-museum', 'start': '09:00', 'end': '10:30'},
        {'poi_id': 'han-market', 'start': '11:00', 'end': '12:00'},
        {'poi_id': 'my-khe', 'start': '15:30', 'end': '18:00'},
      ],
      rank: 2,
      gatePassed: true,
      dataVersion: 'seed-demo-2026-10-28',
      totalCost: 300000,
      totalKm: 11.8,
      totalMinutes: 300,
    ),
  ];
}

class PlanningResult {
  const PlanningResult({
    required this.items,
    this.shortageReason,
    this.requestId,
    this.status = 'completed',
    this.failureCode,
  });
  final List<PlanAlternative> items;
  final String? shortageReason;
  final String? requestId;
  final String status;
  final String? failureCode;
}

class AcceptanceSummary {
  const AcceptanceSummary({
    required this.id,
    required this.selectedAt,
    this.versionId,
  });
  final String id;
  final DateTime selectedAt;
  final String? versionId;

  factory AcceptanceSummary.fromJson(Map<String, dynamic> json) =>
      AcceptanceSummary(
        id: json['acceptance_id'] as String,
        selectedAt: DateTime.parse(json['selected_at'] as String),
        versionId: json['version_id'] as String?,
      );
}

class ItineraryVersionSummary {
  const ItineraryVersionSummary({
    required this.id,
    required this.ordinal,
    required this.active,
    required this.dataVersion,
    required this.createdAt,
    required this.reason,
    this.parentId,
  });

  final String id;
  final int ordinal;
  final bool active;
  final String? parentId;
  final String dataVersion;
  final DateTime createdAt;
  final String reason;

  factory ItineraryVersionSummary.fromJson(Map<String, dynamic> json) =>
      ItineraryVersionSummary(
        id: json['version_id'] as String,
        ordinal: json['ordinal'] as int? ?? 1,
        active: json['active'] as bool? ?? false,
        parentId: json['parent_version_id'] as String?,
        dataVersion: json['data_version'] as String? ?? 'unknown',
        createdAt: DateTime.parse(json['created_at'] as String),
        reason: json['reason'] as String? ?? 'accept',
      );
}
