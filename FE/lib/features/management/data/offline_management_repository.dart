import 'dart:convert';

import '../../../core/errors/api_exception.dart';
import '../../../core/offline/offline.dart';
import '../domain/models.dart';
import 'management_repository.dart';
import 'offline_models.dart';

abstract interface class OfflineSyncControl {
  SyncStatus get status;
  Future<void> loadStatus();
  Future<SyncStatus> synchronize();
  Future<SyncStatus> discardConflicts();
  Future<SyncStatus> retryConflicts();
  Future<void> clearAccount();
}

class OfflineManagementRepository
    implements LiveManagementRepository, OfflineSyncControl {
  OfflineManagementRepository({
    required this.live,
    required this.persistence,
    required this.accountId,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final LiveManagementRepository live;
  final OfflinePersistence persistence;
  final String accountId;
  final DateTime Function() _clock;
  OfflineEnvelope? _envelope;
  bool _usingStaleCache = false;
  bool _isSyncing = false;
  String? _message;
  String? _localActiveTripId;

  @override
  String? get activeTripId => _localActiveTripId ?? live.activeTripId;

  @override
  set activeTripId(String? value) => _localActiveTripId = value;

  @override
  SyncStatus get status {
    final queue = _envelope?.queue ?? const <PendingEdit>[];
    return SyncStatus(
      usingStaleCache: _usingStaleCache,
      lastSuccessAt: _envelope?.lastSuccessAt,
      pendingCount: queue
          .where((item) => item.state == PendingEditState.pending)
          .length,
      conflictCount: queue
          .where((item) => item.state == PendingEditState.conflict)
          .length,
      failedCount: queue
          .where((item) => item.state == PendingEditState.failed)
          .length,
      isSyncing: _isSyncing,
      message: _message,
    );
  }

  Future<OfflineEnvelope?> _loadExisting() async {
    if (_envelope != null) return _envelope;
    final raw = await persistence.read(accountId);
    if (raw == null) return null;
    try {
      _envelope = OfflineEnvelope.decode(
        raw,
        accountId: accountId,
        now: _clock(),
      );
      return _envelope;
    } on FormatException {
      await persistence.delete(accountId);
      return null;
    }
  }

  Future<OfflineEnvelope> _loadOrCreate() async =>
      await _loadExisting() ?? OfflineEnvelope.empty(accountId, _clock());

  Future<void> _persist(OfflineEnvelope envelope) async {
    _envelope = envelope;
    await persistence.write(accountId, jsonEncode(envelope.toJson()));
  }

  Future<void> _cache(
    String key,
    Map<String, dynamic> payload, {
    bool serverSuccess = true,
    Set<String>? pendingIds,
  }) async {
    var envelope = await _loadOrCreate();
    final savedAt = _clock().toUtc();
    final snapshots = {...envelope.snapshots};
    snapshots[key] = CachedProjection(
      key: key,
      payload: payload,
      savedAt: savedAt,
      pendingResourceIds:
          pendingIds ?? snapshots[key]?.pendingResourceIds ?? const {},
    );
    envelope = envelope.copyWith(
      snapshots: snapshots,
      lastSuccessAt: serverSuccess ? savedAt : envelope.lastSuccessAt,
    );
    if (serverSuccess) _usingStaleCache = false;
    await _persist(envelope);
  }

  bool _isNetwork(Object error) =>
      error is ApiException && error.code == 'NETWORK_ERROR';

  Future<Map<String, dynamic>> _fallback(String key, Object error) async {
    if (!_isNetwork(error)) throw error;
    final projection = (await _loadExisting())?.snapshots[key];
    if (projection == null) throw error;
    _usingStaleCache = true;
    _message = 'Đang dùng dữ liệu đã lưu trên thiết bị.';
    return projection.payload;
  }

  @override
  Future<void> loadStatus() async {
    await _loadExisting();
  }

  @override
  Future<(List<UserProfile>, String?)> listProfiles() async {
    try {
      final result = await live.listProfiles();
      await _cache('profile', {
        'items': result.$1.map(_profileJson).toList(),
        'active_id': result.$2,
      });
      return result;
    } catch (error) {
      final cached = await _fallback('profile', error);
      return (
        (cached['items'] as List)
            .map(
              (item) =>
                  UserProfile.fromJson(Map<String, dynamic>.from(item as Map)),
            )
            .toList(),
        cached['active_id'] as String?,
      );
    }
  }

  @override
  Future<List<Trip>> listTrips(String profileId, {String? state}) async {
    final key = 'trips:$profileId:${state ?? 'available'}';
    try {
      final result = await live.listTrips(profileId, state: state);
      _localActiveTripId = live.activeTripId;
      await _cache(key, {
        'items': result.map(_tripJson).toList(),
        'active_trip_id': _localActiveTripId,
      });
      return result;
    } catch (error) {
      final cached = await _fallback(key, error);
      _localActiveTripId = cached['active_trip_id'] as String?;
      return (cached['items'] as List)
          .map((item) => Trip.fromJson(Map<String, dynamic>.from(item as Map)))
          .toList();
    }
  }

  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) async {
    final key = 'trip:$id';
    try {
      final result = await live.getTrip(id);
      await _cache(key, {
        'trip': _tripJson(result.$1),
        'itinerary': _itineraryJson(result.$2),
        'summary': _summaryJson(result.$3),
      });
      return result;
    } catch (error) {
      final cached = await _fallback(key, error);
      return (
        Trip.fromJson(Map<String, dynamic>.from(cached['trip'] as Map)),
        _itineraryFromJson(
          Map<String, dynamic>.from(cached['itinerary'] as Map),
        ),
        ExpenseSummaryData.fromJson(
          Map<String, dynamic>.from(cached['summary'] as Map),
        ),
      );
    }
  }

  @override
  Future<(List<ExpenseItem>, ExpenseSummaryData)> listExpenses(
    String tripId,
  ) async {
    final key = 'expenses:$tripId';
    try {
      final result = await live.listExpenses(tripId);
      await _cache(key, {
        'items': result.$1.map(_expenseJson).toList(),
        'summary': _summaryJson(result.$2),
      });
      return result;
    } catch (error) {
      final cached = await _fallback(key, error);
      return (
        (cached['items'] as List)
            .map(
              (item) =>
                  ExpenseItem.fromJson(Map<String, dynamic>.from(item as Map)),
            )
            .toList(),
        ExpenseSummaryData.fromJson(
          Map<String, dynamic>.from(cached['summary'] as Map),
        ),
      );
    }
  }

  Future<void> _enqueue(
    OfflineOperationKind kind,
    String resourceId,
    Map<String, dynamic> data,
  ) async {
    final version = data['version'];
    if (version is! int || version < 1) {
      throw const ApiException(
        'OFFLINE_VERSION_REQUIRED',
        'Không thể lưu ngoại tuyến vì thiếu phiên bản máy chủ.',
      );
    }
    final envelope = (await _loadOrCreate()).queueEdit(
      PendingEdit.create(
        kind: kind,
        resourceId: resourceId,
        expectedVersion: version,
        payload: data,
        now: _clock(),
      ),
    );
    _message = 'Thay đổi đang chờ đồng bộ với máy chủ.';
    await _persist(envelope);
  }

  @override
  Future<UserProfile> updateProfile(
    String id,
    Map<String, dynamic> data,
  ) async {
    try {
      final result = await live.updateProfile(id, data);
      await _replaceProfile(result, serverSuccess: true);
      return result;
    } catch (error) {
      if (!_isNetwork(error)) rethrow;
      final projection = (await _loadExisting())?.snapshots['profile'];
      if (projection == null) rethrow;
      final items = (projection.payload['items'] as List)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
      final index = items.indexWhere((item) => item['id'] == id);
      if (index < 0) rethrow;
      items[index] = {...items[index], ...data, 'version': data['version']};
      final optimistic = UserProfile.fromJson(items[index]);
      await _enqueue(OfflineOperationKind.updateProfile, id, data);
      await _cache(
        'profile',
        {...projection.payload, 'items': items},
        serverSuccess: false,
        pendingIds: {...projection.pendingResourceIds, id},
      );
      return optimistic;
    }
  }

  @override
  Future<Trip> updateTrip(String id, Map<String, dynamic> data) async {
    try {
      final result = await live.updateTrip(id, data);
      await _replaceTrip(result, serverSuccess: true);
      return result;
    } catch (error) {
      if (!_isNetwork(error)) rethrow;
      final envelope = await _loadExisting();
      final detail = envelope?.snapshots['trip:$id'];
      if (detail == null) rethrow;
      final current = Map<String, dynamic>.from(detail.payload['trip'] as Map);
      final merged = _mergeTrip(current, data);
      final optimistic = Trip.fromJson(merged);
      await _enqueue(OfflineOperationKind.updateTrip, id, data);
      await _cache(
        'trip:$id',
        {...detail.payload, 'trip': merged},
        serverSuccess: false,
        pendingIds: {...detail.pendingResourceIds, id},
      );
      await _replaceTripInLists(optimistic, serverSuccess: false);
      return optimistic;
    }
  }

  @override
  Future<ItineraryData> updateActivity(
    String id,
    Map<String, dynamic> data,
  ) async {
    try {
      final result = await live.updateActivity(id, data);
      final tripId = data['trip_id'] as String?;
      if (tripId != null) await _cacheItinerary(tripId, result, true, id);
      return result;
    } catch (error) {
      if (!_isNetwork(error)) rethrow;
      final tripId = data['trip_id'] as String?;
      if (tripId == null) rethrow;
      final detail = (await _loadExisting())?.snapshots['trip:$tripId'];
      if (detail == null) rethrow;
      final itinerary = Map<String, dynamic>.from(
        detail.payload['itinerary'] as Map,
      );
      final activities = (itinerary['activities'] as List)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
      final index = activities.indexWhere((item) => item['id'] == id);
      if (index < 0) rethrow;
      activities[index] = {
        ...activities[index],
        ...data,
        'version': data['version'],
      };
      itinerary['activities'] = activities;
      final optimistic = _itineraryFromJson(itinerary);
      await _enqueue(OfflineOperationKind.updateActivity, id, data);
      await _cache(
        'trip:$tripId',
        {...detail.payload, 'itinerary': itinerary},
        serverSuccess: false,
        pendingIds: {...detail.pendingResourceIds, id},
      );
      return optimistic;
    }
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> updateExpense(
    String id,
    Map<String, dynamic> data,
  ) async {
    try {
      final result = await live.updateExpense(id, data);
      await _replaceExpense(result.$1, result.$2, serverSuccess: true);
      return result;
    } catch (error) {
      if (!_isNetwork(error)) rethrow;
      final match = _findExpenseProjection(id);
      if (match == null) rethrow;
      final projection = match.$2;
      final items = (projection.payload['items'] as List)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
      final index = items.indexWhere((item) => item['id'] == id);
      items[index] = {...items[index], ...data, 'version': data['version']};
      final expenses = items.map(ExpenseItem.fromJson).toList();
      final oldSummary = ExpenseSummaryData.fromJson(
        Map<String, dynamic>.from(projection.payload['summary'] as Map),
      );
      final summary = _recalculate(expenses, oldSummary.budgetVnd);
      final optimistic = expenses[index];
      await _enqueue(OfflineOperationKind.updateExpense, id, data);
      await _cache(
        match.$1,
        {'items': items, 'summary': _summaryJson(summary)},
        serverSuccess: false,
        pendingIds: {...projection.pendingResourceIds, id},
      );
      return (optimistic, summary);
    }
  }

  @override
  Future<SyncStatus> synchronize() async {
    if (_isSyncing) return status;
    _isSyncing = true;
    _message = 'Đang đồng bộ thay đổi ngoại tuyến.';
    try {
      final initialEnvelope = await _loadExisting();
      if (initialEnvelope != null) {
        var envelope = initialEnvelope;
        final blocked = <String>{};
        for (var index = 0; index < envelope.queue.length; index++) {
          final edit = envelope.queue[index];
          final resourceKey = '${edit.kind.name}:${edit.resourceId}';
          if (edit.state != PendingEditState.pending ||
              blocked.contains(resourceKey)) {
            continue;
          }
          try {
            await _replay(edit);
            envelope = _envelope ?? envelope;
            envelope = envelope.copyWith(
              queue: envelope.queue
                  .where((item) => item.operationId != edit.operationId)
                  .toList(),
            );
            await _persist(envelope);
            index -= 1;
          } on ApiException catch (error) {
            envelope = _envelope ?? envelope;
            final currentIndex = envelope.queue.indexWhere(
              (item) => item.operationId == edit.operationId,
            );
            if (currentIndex < 0) continue;
            if (error.code == 'NETWORK_ERROR' || error.statusCode == 503) {
              final updated = [...envelope.queue];
              updated[currentIndex] = edit.copyWith(
                attemptCount: edit.attemptCount + 1,
                lastAttemptAt: _clock(),
                failureCode: error.code,
                failureMessage: error.message,
              );
              await _persist(envelope.copyWith(queue: updated));
              break;
            }
            final updated = [...envelope.queue];
            final conflict = error.statusCode == 409;
            updated[currentIndex] = edit.copyWith(
              state: conflict
                  ? PendingEditState.conflict
                  : PendingEditState.failed,
              attemptCount: edit.attemptCount + 1,
              lastAttemptAt: _clock(),
              failureCode: error.code,
              failureMessage: error.message,
            );
            if (conflict) blocked.add(resourceKey);
            await _persist(envelope.copyWith(queue: updated));
            envelope = _envelope!;
          }
        }
      }
      _message = status.conflictCount > 0
          ? 'Có thay đổi xung đột cần xử lý.'
          : status.failedCount > 0
          ? 'Có thay đổi không thể đồng bộ.'
          : status.pendingCount > 0
          ? 'Một số thay đổi vẫn đang chờ kết nối.'
          : 'Đã đồng bộ tất cả thay đổi.';
    } finally {
      _isSyncing = false;
    }
    return status;
  }

  Future<void> _replay(PendingEdit edit) async {
    switch (edit.kind) {
      case OfflineOperationKind.updateProfile:
        final result = await live.updateProfile(edit.resourceId, edit.payload);
        await _replaceProfile(result, serverSuccess: true);
        break;
      case OfflineOperationKind.updateTrip:
        final result = await live.updateTrip(edit.resourceId, edit.payload);
        await _replaceTrip(result, serverSuccess: true);
        break;
      case OfflineOperationKind.updateActivity:
        final result = await live.updateActivity(edit.resourceId, edit.payload);
        final tripId = edit.payload['trip_id'] as String?;
        if (tripId != null) {
          await _cacheItinerary(tripId, result, true, edit.resourceId);
        }
        break;
      case OfflineOperationKind.updateExpense:
        final result = await live.updateExpense(edit.resourceId, edit.payload);
        await _replaceExpense(result.$1, result.$2, serverSuccess: true);
        break;
    }
  }

  @override
  Future<SyncStatus> discardConflicts() async {
    final envelope = await _loadExisting();
    if (envelope == null) return status;
    await _persist(
      envelope.copyWith(
        queue: envelope.queue
            .where((item) => item.state == PendingEditState.pending)
            .toList(),
      ),
    );
    _message = 'Đã bỏ thay đổi xung đột; hãy làm mới dữ liệu máy chủ.';
    return status;
  }

  @override
  Future<SyncStatus> retryConflicts() async {
    final envelope = await _loadExisting();
    if (envelope == null) return status;
    await _persist(
      envelope.copyWith(
        queue: [
          for (final item in envelope.queue)
            item.state == PendingEditState.pending
                ? item
                : item.copyWith(
                    state: PendingEditState.pending,
                    clearFailure: true,
                  ),
        ],
      ),
    );
    return synchronize();
  }

  @override
  Future<void> clearAccount() async {
    await persistence.delete(accountId);
    _envelope = null;
    _usingStaleCache = false;
    _message = null;
  }

  Future<void> _replaceProfile(
    UserProfile profile, {
    required bool serverSuccess,
  }) async {
    final projection = (await _loadExisting())?.snapshots['profile'];
    if (projection == null) return;
    final items = (projection.payload['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    final index = items.indexWhere((item) => item['id'] == profile.id);
    if (index >= 0) items[index] = _profileJson(profile);
    await _cache(
      'profile',
      {...projection.payload, 'items': items},
      serverSuccess: serverSuccess,
      pendingIds: {...projection.pendingResourceIds}..remove(profile.id),
    );
  }

  Future<void> _replaceTrip(Trip trip, {required bool serverSuccess}) async {
    final detail = (await _loadExisting())?.snapshots['trip:${trip.id}'];
    if (detail != null) {
      await _cache(
        'trip:${trip.id}',
        {...detail.payload, 'trip': _tripJson(trip)},
        serverSuccess: serverSuccess,
        pendingIds: {...detail.pendingResourceIds}..remove(trip.id),
      );
    }
    await _replaceTripInLists(trip, serverSuccess: serverSuccess);
  }

  Future<void> _replaceTripInLists(
    Trip trip, {
    required bool serverSuccess,
  }) async {
    final envelope = await _loadExisting();
    if (envelope == null) return;
    for (final entry in envelope.snapshots.entries.where(
      (entry) => entry.key.startsWith('trips:'),
    )) {
      final items = (entry.value.payload['items'] as List)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();
      final index = items.indexWhere((item) => item['id'] == trip.id);
      if (index < 0) continue;
      items[index] = _tripJson(trip);
      await _cache(
        entry.key,
        {...entry.value.payload, 'items': items},
        serverSuccess: serverSuccess,
        pendingIds: {...entry.value.pendingResourceIds}..remove(trip.id),
      );
    }
  }

  Future<void> _cacheItinerary(
    String tripId,
    ItineraryData itinerary,
    bool serverSuccess,
    String resourceId,
  ) async {
    final detail = (await _loadExisting())?.snapshots['trip:$tripId'];
    if (detail == null) return;
    await _cache(
      'trip:$tripId',
      {...detail.payload, 'itinerary': _itineraryJson(itinerary)},
      serverSuccess: serverSuccess,
      pendingIds: {...detail.pendingResourceIds}..remove(resourceId),
    );
  }

  (String, CachedProjection)? _findExpenseProjection(String expenseId) {
    final envelope = _envelope;
    if (envelope == null) return null;
    for (final entry in envelope.snapshots.entries.where(
      (entry) => entry.key.startsWith('expenses:'),
    )) {
      final items = entry.value.payload['items'] as List;
      if (items.any((item) => (item as Map)['id'] == expenseId)) {
        return (entry.key, entry.value);
      }
    }
    return null;
  }

  Future<void> _replaceExpense(
    ExpenseItem expense,
    ExpenseSummaryData summary, {
    required bool serverSuccess,
  }) async {
    final match = _findExpenseProjection(expense.id);
    if (match == null) return;
    final items = (match.$2.payload['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    final index = items.indexWhere((item) => item['id'] == expense.id);
    if (index >= 0) items[index] = _expenseJson(expense);
    await _cache(
      match.$1,
      {'items': items, 'summary': _summaryJson(summary)},
      serverSuccess: serverSuccess,
      pendingIds: {...match.$2.pendingResourceIds}..remove(expense.id),
    );
  }

  @override
  Future<void> setActiveTrip(Trip? trip) async {
    try {
      await live.setActiveTrip(trip);
    } on ApiException catch (error) {
      if (error.code != 'NETWORK_ERROR') rethrow;
    }
    _localActiveTripId = trip?.id;
  }

  @override
  Future<UserProfile> createProfile(Map<String, dynamic> data) =>
      live.createProfile(data);
  @override
  Future<UserProfile> resetProfile(UserProfile profile) =>
      live.resetProfile(profile);
  @override
  Future<void> setActiveProfile(String id) => live.setActiveProfile(id);
  @override
  Future<void> deleteProfile(UserProfile profile) =>
      live.deleteProfile(profile);
  @override
  Future<Trip> createTrip(Map<String, dynamic> data) => live.createTrip(data);
  @override
  Future<void> deleteTrip(Trip trip) => live.deleteTrip(trip);
  @override
  Future<Trip> archiveTrip(Trip trip) => live.archiveTrip(trip);
  @override
  Future<Trip> restoreTrip(Trip trip) => live.restoreTrip(trip);
  @override
  Future<ItineraryData> addActivity(String tripId, Map<String, dynamic> data) =>
      live.addActivity(tripId, data);
  @override
  Future<ItineraryData> deleteActivity(
    ActivityItem activity,
    int itineraryVersion,
  ) => live.deleteActivity(activity, itineraryVersion);
  @override
  Future<ItineraryData> reorderActivities(
    String tripId,
    List<String> ids,
    int itineraryVersion,
  ) => live.reorderActivities(tripId, ids, itineraryVersion);
  @override
  Future<(ExpenseItem, ExpenseSummaryData)> addExpense(
    String tripId,
    Map<String, dynamic> data,
  ) => live.addExpense(tripId, data);
  @override
  Future<ExpenseSummaryData> deleteExpense(ExpenseItem expense) =>
      live.deleteExpense(expense);
  @override
  Future<Map<String, dynamic>> exportExpenses(
    String tripId, {
    String? date,
    String? category,
  }) => live.exportExpenses(tripId, date: date, category: category);
  @override
  Future<List<PoiItem>> searchPois(String query) => live.searchPois(query);
  @override
  Future<PoiItem> getPoiDetails(String id) => live.getPoiDetails(id);
  @override
  Future<RoutePreviewData> previewRoute(String tripId, List<String> ids) =>
      live.previewRoute(tripId, ids);
}

Map<String, dynamic> _profileJson(UserProfile item) => {
  'id': item.id,
  'display_name': item.displayName,
  'party_type': item.partyType,
  'trip_purpose': item.tripPurpose,
  'spending_level': item.spendingLevel,
  'pace': item.pace,
  'fitness': item.fitness,
  'food_preferences': item.foodPreferences,
  'must_avoid': item.mustAvoid,
  'preferred_activities': item.preferredActivities,
  'usual_transport': item.usualTransport,
  'allergies': item.allergies,
  'accessibility_needs': item.accessibilityNeeds,
  'version': item.version,
};

Map<String, dynamic> _tripJson(Trip item) => {
  'id': item.id,
  'profile_id': item.profileId,
  'title': item.title,
  'start_date': isoDate(item.startDate),
  'end_date': isoDate(item.endDate),
  'day_start': item.dayStart,
  'day_end': item.dayEnd,
  'travelers': item.travelers,
  'budget_vnd': item.budgetVnd,
  'transport': item.transport,
  'status': item.status,
  'version': item.version,
};

Map<String, dynamic> _mergeTrip(
  Map<String, dynamic> current,
  Map<String, dynamic> data,
) => {
  ...current,
  ...data,
  'travelers': data['travelers'] ?? current['travelers'],
  'budget_vnd': data['budget_vnd'] ?? current['budget_vnd'],
  'transport': data['transport'] ?? current['transport'],
  'version': data['version'],
};

Map<String, dynamic> _activityJson(ActivityItem item) => {
  'id': item.id,
  'position': item.position,
  'poi_id': item.poiId,
  'title': item.title,
  'notes': item.notes,
  'latitude': item.latitude,
  'longitude': item.longitude,
  'start_at': item.startAt.toIso8601String(),
  'end_at': item.endAt.toIso8601String(),
  'category': item.category,
  'estimated_cost_vnd': item.estimatedCostVnd,
  'source': item.source,
  'version': item.version,
  'progress_state': item.progressState,
};

Map<String, dynamic> _itineraryJson(ItineraryData item) => {
  'id': item.id,
  'trip_id': item.tripId,
  'version': item.version,
  'activities': item.activities.map(_activityJson).toList(),
  'warnings': item.warnings,
};

ItineraryData _itineraryFromJson(Map<String, dynamic> json) => ItineraryData(
  id: json['id'] as String,
  tripId: json['trip_id'] as String,
  version: json['version'] as int,
  activities: (json['activities'] as List)
      .map(
        (item) => ActivityItem.fromJson(Map<String, dynamic>.from(item as Map)),
      )
      .toList(),
  warnings: List<String>.from(json['warnings'] as List? ?? const []),
);

Map<String, dynamic> _expenseJson(ExpenseItem item) => {
  'id': item.id,
  'label': item.label,
  'amount_vnd': item.amountVnd,
  'category': item.category,
  'spent_at': item.spentAt.toIso8601String(),
  'notes': item.notes,
  'version': item.version,
};

Map<String, dynamic> _summaryJson(ExpenseSummaryData item) => {
  'budget_vnd': item.budgetVnd,
  'spent_vnd': item.spentVnd,
  'remaining_vnd': item.remainingVnd,
  'by_category': item.byCategory,
  'alert': item.alert,
  'by_day': item.byDay,
  'average_vnd': item.averageVnd,
  'entry_count': item.entryCount,
  'utilization_percent': item.utilizationPercent,
};

ExpenseSummaryData _recalculate(List<ExpenseItem> items, int budget) {
  final spent = items.fold<int>(0, (total, item) => total + item.amountVnd);
  final byCategory = <String, int>{};
  final byDay = <String, int>{};
  for (final item in items) {
    byCategory[item.category] =
        (byCategory[item.category] ?? 0) + item.amountVnd;
    final day = isoDate(item.spentAt);
    byDay[day] = (byDay[day] ?? 0) + item.amountVnd;
  }
  final utilization = budget == 0 ? 0.0 : spent / budget * 100;
  return ExpenseSummaryData(
    budgetVnd: budget,
    spentVnd: spent,
    remainingVnd: budget - spent,
    byCategory: byCategory,
    byDay: byDay,
    averageVnd: items.isEmpty ? 0 : spent ~/ items.length,
    entryCount: items.length,
    utilizationPercent: utilization,
    alert: utilization >= 100
        ? '100'
        : utilization >= 80
        ? '80'
        : 'none',
  );
}
