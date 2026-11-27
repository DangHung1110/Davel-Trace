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
        {
          'poi_id': 'son-tra',
          'name': 'Bán đảo Sơn Trà',
          'start': '07:30',
          'end': '09:30',
        },
        {
          'poi_id': 'mi-quang',
          'name': 'Ăn trưa với mì Quảng',
          'start': '11:30',
          'end': '12:30',
        },
        {
          'poi_id': 'cham-museum',
          'name': 'Bảo tàng Điêu khắc Chăm',
          'start': '14:00',
          'end': '15:30',
        },
        {
          'poi_id': 'my-khe',
          'name': 'Biển Mỹ Khê',
          'start': '16:30',
          'end': '18:00',
        },
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
        {
          'poi_id': 'cham-museum',
          'name': 'Bảo tàng Điêu khắc Chăm',
          'start': '09:00',
          'end': '10:30',
        },
        {
          'poi_id': 'han-market',
          'name': 'Chợ Hàn',
          'start': '11:00',
          'end': '12:00',
        },
        {
          'poi_id': 'my-khe',
          'name': 'Biển Mỹ Khê',
          'start': '15:30',
          'end': '18:00',
        },
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

class SavedItineraryPlan {
  const SavedItineraryPlan({
    required this.versionId,
    required this.tripId,
    required this.plan,
    this.date,
  });

  final String versionId;
  final String tripId;
  final PlanAlternative plan;
  final DateTime? date;

  factory SavedItineraryPlan.fromJson(Map<String, dynamic> json) {
    final request = json['request'] as Map?;
    final trip = request?['trip'] as Map?;
    final date = trip?['start_date'] as String?;
    return SavedItineraryPlan(
      versionId: json['version_id'] as String,
      tripId: json['trip_id'] as String,
      plan: PlanAlternative.fromJson({
        ...json,
        'alternative_id': json['version_id'],
      }),
      date: date == null ? null : DateTime.tryParse(date),
    );
  }
}

class PlaceNameCandidate {
  const PlaceNameCandidate({
    required this.id,
    required this.name,
    this.type = '',
    this.latitude,
    this.longitude,
    this.address = '',
  });

  final String id;
  final String name;
  final String type;
  final double? latitude;
  final double? longitude;
  final String address;

  factory PlaceNameCandidate.fromJson(Map<String, dynamic> json) =>
      PlaceNameCandidate(
        id: json['poi_id'] as String,
        name: json['name'] as String,
        type: json['type'] as String? ?? '',
        latitude: (json['lat'] as num?)?.toDouble(),
        longitude: (json['lon'] as num?)?.toDouble(),
        address: json['address'] as String? ?? '',
      );

  String get description => [
    if (type.isNotEmpty) type,
    if (address.isNotEmpty) address,
    if (address.isEmpty && latitude != null && longitude != null)
      '${latitude!.toStringAsFixed(5)}, ${longitude!.toStringAsFixed(5)}',
  ].join(' · ');
}

class PlaceNameResolution {
  const PlaceNameResolution({
    required this.constraint,
    required this.name,
    required this.status,
    required this.candidates,
  });

  final String constraint;
  final String name;
  final String status;
  final List<PlaceNameCandidate> candidates;

  factory PlaceNameResolution.fromJson(Map<String, dynamic> json) =>
      PlaceNameResolution(
        constraint: json['constraint'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
        candidates: (json['candidates'] as List? ?? const [])
            .map(
              (item) => PlaceNameCandidate.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList(),
      );
}

class AiInterpretationProposal {
  const AiInterpretationProposal({
    required this.id,
    required this.fields,
    required this.hardConstraints,
    required this.softPreferences,
    required this.assumptions,
    required this.unresolved,
    required this.provider,
    required this.model,
    required this.externalProcessing,
    this.placeResolutions = const [],
  });

  final String id;
  final Map<String, dynamic> fields;
  final Map<String, dynamic> hardConstraints;
  final Map<String, dynamic> softPreferences;
  final List<String> assumptions;
  final List<String> unresolved;
  final String provider;
  final String? model;
  final bool externalProcessing;
  final List<PlaceNameResolution> placeResolutions;

  factory AiInterpretationProposal.fromJson(Map<String, dynamic> json) =>
      AiInterpretationProposal(
        id: json['proposal_id'] as String,
        fields: Map<String, dynamic>.from(json['fields'] as Map? ?? const {}),
        hardConstraints: Map<String, dynamic>.from(
          json['hard_constraints'] as Map? ?? const {},
        ),
        softPreferences: Map<String, dynamic>.from(
          json['soft_preferences'] as Map? ?? const {},
        ),
        assumptions: (json['assumptions'] as List? ?? const [])
            .map((item) => item.toString())
            .toList(),
        unresolved: (json['unresolved'] as List? ?? const [])
            .map((item) => item.toString())
            .toList(),
        provider: json['provider'] as String? ?? 'unknown',
        model: json['model'] as String?,
        externalProcessing: json['external_processing'] as bool? ?? false,
        placeResolutions: (json['place_resolutions'] as List? ?? const [])
            .map(
              (item) => PlaceNameResolution.fromJson(
                Map<String, dynamic>.from(item as Map),
              ),
            )
            .toList(),
      );

  Map<String, dynamic> get confirmedOverrides => {
    ...fields,
    ...hardConstraints,
    ...softPreferences,
  };
}

class PlanExplanation {
  const PlanExplanation({
    required this.source,
    required this.summary,
    required this.reasons,
    required this.warnings,
  });

  final String source;
  final String summary;
  final List<Map<String, dynamic>> reasons;
  final List<String> warnings;

  factory PlanExplanation.fromJson(Map<String, dynamic> json) =>
      PlanExplanation(
        source: json['source'] as String? ?? 'deterministic',
        summary: json['summary'] as String? ?? '',
        reasons: (json['reasons'] as List? ?? const [])
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(),
        warnings: (json['warnings'] as List? ?? const [])
            .map((item) => item.toString())
            .toList(),
      );
}
