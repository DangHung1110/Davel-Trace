import 'dart:convert';

enum OfflineOperationKind {
  updateProfile,
  updateTrip,
  updateActivity,
  updateExpense,
}

enum PendingEditState { pending, conflict, failed }

class OfflineQueueFullException implements Exception {
  const OfflineQueueFullException();

  @override
  String toString() => 'Hàng đợi ngoại tuyến đã đạt giới hạn 100 thay đổi.';
}

class PendingEdit {
  const PendingEdit({
    required this.operationId,
    required this.kind,
    required this.resourceId,
    required this.expectedVersion,
    required this.payload,
    required this.createdAt,
    required this.state,
    this.attemptCount = 0,
    this.lastAttemptAt,
    this.failureCode,
    this.failureMessage,
  });

  final String operationId;
  final OfflineOperationKind kind;
  final String resourceId;
  final int expectedVersion;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  final PendingEditState state;
  final int attemptCount;
  final DateTime? lastAttemptAt;
  final String? failureCode;
  final String? failureMessage;

  static const _allowed = <OfflineOperationKind, Set<String>>{
    OfflineOperationKind.updateProfile: {
      'display_name',
      'party_type',
      'trip_purpose',
      'spending_level',
      'pace',
      'fitness',
      'food_preferences',
      'must_avoid',
      'preferred_activities',
      'usual_transport',
      'allergies',
      'accessibility_needs',
      'version',
    },
    OfflineOperationKind.updateTrip: {
      'title',
      'start_date',
      'end_date',
      'travelers',
      'budget_vnd',
      'transport',
      'day_start',
      'day_end',
      'confirm_removed_days',
      'version',
    },
    OfflineOperationKind.updateActivity: {
      'title',
      'start_at',
      'end_at',
      'estimated_cost_vnd',
      'notes',
      'category',
      'progress_state',
      'trip_id',
      'itinerary_version',
      'version',
    },
    OfflineOperationKind.updateExpense: {
      'label',
      'amount_vnd',
      'category',
      'spent_at',
      'notes',
      'version',
    },
  };

  factory PendingEdit.create({
    required OfflineOperationKind kind,
    required String resourceId,
    required int expectedVersion,
    required Map<String, dynamic> payload,
    required DateTime now,
  }) {
    final safe = _sanitize(kind, payload, expectedVersion);
    return PendingEdit(
      operationId:
          'offline-${now.microsecondsSinceEpoch}-${kind.name}-$resourceId',
      kind: kind,
      resourceId: resourceId,
      expectedVersion: expectedVersion,
      payload: safe,
      createdAt: now.toUtc(),
      state: PendingEditState.pending,
    );
  }

  static Map<String, dynamic> _sanitize(
    OfflineOperationKind kind,
    Map<String, dynamic> payload,
    int expectedVersion,
  ) {
    final safe = <String, dynamic>{};
    for (final entry in payload.entries) {
      if (_allowed[kind]!.contains(entry.key)) safe[entry.key] = entry.value;
    }
    safe['version'] = expectedVersion;
    return safe;
  }

  PendingEdit merge(PendingEdit newer) {
    if (state != PendingEditState.pending) return this;
    return copyWith(
      payload: {...payload, ...newer.payload, 'version': expectedVersion},
    );
  }

  PendingEdit copyWith({
    Map<String, dynamic>? payload,
    PendingEditState? state,
    int? attemptCount,
    DateTime? lastAttemptAt,
    String? failureCode,
    String? failureMessage,
    bool clearFailure = false,
  }) => PendingEdit(
    operationId: operationId,
    kind: kind,
    resourceId: resourceId,
    expectedVersion: expectedVersion,
    payload: payload ?? this.payload,
    createdAt: createdAt,
    state: state ?? this.state,
    attemptCount: attemptCount ?? this.attemptCount,
    lastAttemptAt: lastAttemptAt ?? this.lastAttemptAt,
    failureCode: clearFailure ? null : failureCode ?? this.failureCode,
    failureMessage: clearFailure ? null : failureMessage ?? this.failureMessage,
  );

  Map<String, dynamic> toJson() => {
    'operation_id': operationId,
    'kind': kind.name,
    'resource_id': resourceId,
    'expected_version': expectedVersion,
    'payload': payload,
    'created_at': createdAt.toUtc().toIso8601String(),
    'state': state.name,
    'attempt_count': attemptCount,
    'last_attempt_at': lastAttemptAt?.toUtc().toIso8601String(),
    'failure_code': failureCode,
    'failure_message': failureMessage,
  };

  factory PendingEdit.fromJson(Map<String, dynamic> json) {
    final kind = OfflineOperationKind.values.byName(json['kind'] as String);
    final version = json['expected_version'] as int;
    if (version < 1) throw const FormatException('Invalid expected version.');
    return PendingEdit(
      operationId: json['operation_id'] as String,
      kind: kind,
      resourceId: json['resource_id'] as String,
      expectedVersion: version,
      payload: _sanitize(
        kind,
        Map<String, dynamic>.from(json['payload'] as Map),
        version,
      ),
      createdAt: DateTime.parse(json['created_at'] as String).toUtc(),
      state: PendingEditState.values.byName(json['state'] as String),
      attemptCount: json['attempt_count'] as int? ?? 0,
      lastAttemptAt: json['last_attempt_at'] == null
          ? null
          : DateTime.parse(json['last_attempt_at'] as String).toUtc(),
      failureCode: json['failure_code'] as String?,
      failureMessage: json['failure_message'] as String?,
    );
  }
}

class CachedProjection {
  const CachedProjection({
    required this.key,
    required this.payload,
    required this.savedAt,
    this.pendingResourceIds = const {},
  });

  final String key;
  final Map<String, dynamic> payload;
  final DateTime savedAt;
  final Set<String> pendingResourceIds;

  CachedProjection copyWith({
    Map<String, dynamic>? payload,
    DateTime? savedAt,
    Set<String>? pendingResourceIds,
  }) => CachedProjection(
    key: key,
    payload: payload ?? this.payload,
    savedAt: savedAt ?? this.savedAt,
    pendingResourceIds: pendingResourceIds ?? this.pendingResourceIds,
  );

  Map<String, dynamic> toJson() => {
    'key': key,
    'payload': payload,
    'saved_at': savedAt.toUtc().toIso8601String(),
    'pending_resource_ids': pendingResourceIds.toList()..sort(),
  };

  factory CachedProjection.fromJson(Map<String, dynamic> json) =>
      CachedProjection(
        key: json['key'] as String,
        payload: Map<String, dynamic>.from(json['payload'] as Map),
        savedAt: DateTime.parse(json['saved_at'] as String).toUtc(),
        pendingResourceIds: Set<String>.from(
          json['pending_resource_ids'] as List? ?? const [],
        ),
      );
}

class OfflineEnvelope {
  const OfflineEnvelope({
    required this.accountId,
    required this.lastSuccessAt,
    required this.snapshots,
    required this.queue,
  });

  static const schemaVersion = 1;
  static const maxQueueSize = 100;
  static const maxCacheAge = Duration(days: 30);

  final String accountId;
  final DateTime lastSuccessAt;
  final Map<String, CachedProjection> snapshots;
  final List<PendingEdit> queue;

  factory OfflineEnvelope.empty(String accountId, DateTime now) =>
      OfflineEnvelope(
        accountId: accountId,
        lastSuccessAt: now.toUtc(),
        snapshots: const {},
        queue: const [],
      );

  OfflineEnvelope queueEdit(PendingEdit edit) {
    final index = queue.indexWhere(
      (item) =>
          item.kind == edit.kind &&
          item.resourceId == edit.resourceId &&
          item.state == PendingEditState.pending,
    );
    if (index >= 0) {
      final updated = [...queue];
      updated[index] = updated[index].merge(edit);
      return copyWith(queue: updated);
    }
    if (queue.length >= maxQueueSize) throw const OfflineQueueFullException();
    return copyWith(queue: [...queue, edit]);
  }

  OfflineEnvelope copyWith({
    DateTime? lastSuccessAt,
    Map<String, CachedProjection>? snapshots,
    List<PendingEdit>? queue,
  }) => OfflineEnvelope(
    accountId: accountId,
    lastSuccessAt: lastSuccessAt ?? this.lastSuccessAt,
    snapshots: snapshots ?? this.snapshots,
    queue: queue ?? this.queue,
  );

  Map<String, dynamic> toJson() => {
    'schema_version': schemaVersion,
    'account_id': accountId,
    'last_success_at': lastSuccessAt.toUtc().toIso8601String(),
    'snapshots': snapshots.map((key, value) => MapEntry(key, value.toJson())),
    'queue': queue.map((item) => item.toJson()).toList(),
  };

  factory OfflineEnvelope.decode(
    String value, {
    required String accountId,
    required DateTime now,
  }) {
    try {
      final json = _decodeObject(value);
      if (json['schema_version'] != schemaVersion ||
          json['account_id'] != accountId) {
        throw const FormatException('Offline cache scope/schema mismatch.');
      }
      final lastSuccess = DateTime.parse(json['last_success_at'] as String)
          .toUtc();
      if (now.toUtc().difference(lastSuccess) > maxCacheAge) {
        throw const FormatException('Offline cache expired.');
      }
      final rawSnapshots = Map<String, dynamic>.from(
        json['snapshots'] as Map? ?? const {},
      );
      final queue = (json['queue'] as List? ?? const [])
          .map(
            (item) =>
                PendingEdit.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList();
      if (queue.length > maxQueueSize) {
        throw const FormatException('Offline queue exceeds capacity.');
      }
      return OfflineEnvelope(
        accountId: accountId,
        lastSuccessAt: lastSuccess,
        snapshots: rawSnapshots.map(
          (key, value) => MapEntry(
            key,
            CachedProjection.fromJson(Map<String, dynamic>.from(value as Map)),
          ),
        ),
        queue: queue,
      );
    } on FormatException {
      rethrow;
    } catch (_) {
      throw const FormatException('Malformed offline cache.');
    }
  }
}

Map<String, dynamic> _decodeObject(String value) {
  // Kept here to keep JSON validation centralized without exposing raw storage.
  final decoded = jsonDecode(value);
  if (decoded is! Map<String, dynamic>) {
    throw const FormatException('Offline cache root must be an object.');
  }
  return decoded;
}

class SyncStatus {
  const SyncStatus({
    this.usingStaleCache = false,
    this.lastSuccessAt,
    this.pendingCount = 0,
    this.conflictCount = 0,
    this.failedCount = 0,
    this.isSyncing = false,
    this.message,
  });

  final bool usingStaleCache;
  final DateTime? lastSuccessAt;
  final int pendingCount;
  final int conflictCount;
  final int failedCount;
  final bool isSyncing;
  final String? message;
}
