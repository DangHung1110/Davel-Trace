import 'dart:async';
import 'dart:convert';

import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/core/errors/api_exception.dart';
import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:davel_trace/features/management/data/offline_management_repository.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';
import 'support/memory_offline_persistence.dart';

void main() {
  final now = DateTime.utc(2026, 11, 10, 8);

  test(
    'restores covered reads from the same account after network failure',
    () async {
      final live = _LiveFake();
      final persistence = MemoryOfflinePersistence();
      final online = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );
      final first = await online.listProfiles();
      expect(first.$1.single.displayName, 'Đặng Hùng');

      live.networkDown = true;
      final restarted = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now.add(const Duration(minutes: 5)),
      );
      final cached = await restarted.listProfiles();

      expect(cached.$1.single.displayName, 'Đặng Hùng');
      expect(restarted.status.usingStaleCache, isTrue);
      expect(restarted.status.lastSuccessAt, now);
    },
  );

  test(
    'keeps cached trip lists isolated by profile within one account',
    () async {
      final live = _LiveFake();
      final secondProfile = await live.createProfile({
        'display_name': 'Bạn đồng hành',
      });
      await live.createTrip({
        'profile_id': secondProfile.id,
        'title': 'Hội An một ngày',
        'start_date': '2026-11-20',
        'end_date': '2026-11-20',
        'day_start': '07:00:00',
        'day_end': '21:00:00',
        'travelers': 2,
        'budget_vnd': 2000000,
        'transport': 'car',
      });
      final persistence = MemoryOfflinePersistence();
      final repository = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );

      await repository.listTrips('profile-1');
      await repository.listTrips(secondProfile.id);
      live.networkDown = true;

      expect((await repository.listTrips('profile-1')).single.id, 'trip-1');
      expect(
        (await repository.listTrips(secondProfile.id)).single.title,
        'Hội An một ngày',
      );
    },
  );

  test(
    'rejects an expired projection after another projection refreshed',
    () async {
      final live = _LiveFake();
      final persistence = MemoryOfflinePersistence();
      final online = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );
      await online.listTrips('profile-1');
      await online.listProfiles();

      final stored =
          jsonDecode(persistence.values['account-a']!) as Map<String, dynamic>;
      final snapshots = stored['snapshots'] as Map<String, dynamic>;
      final tripProjection =
          snapshots['trips:profile-1:available'] as Map<String, dynamic>;
      tripProjection['saved_at'] = now
          .subtract(const Duration(days: 31))
          .toIso8601String();
      persistence.values['account-a'] = jsonEncode(stored);
      live.networkDown = true;

      final restarted = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );

      await expectLater(
        restarted.listTrips('profile-1'),
        throwsA(isA<ApiException>()),
      );
    },
  );

  test('late live read cannot recreate cache after account cleanup', () async {
    final live = _LiveFake();
    final baseline = await live.listProfiles();
    final gate = Completer<(List<UserProfile>, String?)>();
    live.profileReadGate = gate;
    final persistence = MemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );

    final read = repository.listProfiles();
    await Future<void>.delayed(Duration.zero);
    await repository.clearAccount();
    gate.complete(baseline);
    await read;

    expect(persistence.values, isNot(contains('account-a')));
  });

  test('account cleanup waits for an in-flight cache write', () async {
    final persistence = _BlockingMemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: _LiveFake(),
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );

    final read = repository.listProfiles();
    await persistence.writeStarted.future;
    final cleanup = repository.clearAccount();
    persistence.releaseWrite.complete();
    await Future.wait([read, cleanup]);

    expect(persistence.values, isNot(contains('account-a')));
  });

  test('disposed app state ignores late initialization completion', () async {
    SharedPreferences.setMockInitialValues({});
    final live = _LiveFake();
    final baseline = await live.listProfiles();
    final gate = Completer<(List<UserProfile>, String?)>();
    live.profileReadGate = gate;
    final state = AppState(
      OfflineManagementRepository(
        live: live,
        persistence: MemoryOfflinePersistence(),
        accountId: 'account-a',
        clock: () => now,
      ),
    );

    final initialization = state.initialize();
    await Future<void>.delayed(Duration.zero);
    state.dispose();
    gate.complete(baseline);

    await expectLater(initialization, completes);
  });

  test(
    'coalesces offline expense edits and survives adapter restart',
    () async {
      final live = _LiveFake();
      final persistence = MemoryOfflinePersistence();
      final repository = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );
      await repository.listProfiles();
      await repository.listTrips('profile-1');
      await repository.getTrip('trip-1');
      await repository.listExpenses('trip-1');
      live.networkDown = true;

      final first = await repository.updateExpense('expense-1', {
        'label': 'Bữa sáng mới',
        'version': 1,
      });
      final second = await repository.updateExpense('expense-1', {
        'amount_vnd': 125000,
        'version': 1,
      });

      expect(first.$1.label, 'Bữa sáng mới');
      expect(second.$1.amountVnd, 125000);
      expect(repository.status.pendingCount, 1);

      final restarted = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now.add(const Duration(minutes: 1)),
      );
      await restarted.loadStatus();
      expect(restarted.status.pendingCount, 1);
    },
  );

  test('queues only allowlisted updates for existing records', () async {
    final live = _LiveFake();
    final persistence = MemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );
    await repository.listProfiles();
    await repository.listTrips('profile-1');
    await repository.getTrip('trip-1');
    await repository.listExpenses('trip-1');
    live.networkDown = true;

    final profile = await repository.updateProfile('profile-1', {
      'display_name': 'Ngoại tuyến',
      'version': 1,
    });
    final trip = await repository.updateTrip('trip-1', {
      'title': 'Chuyến đi ngoại tuyến',
      'version': 1,
    });
    final itinerary = await repository.updateActivity('activity-1', {
      'trip_id': 'trip-1',
      'progress_state': 'completed',
      'version': 1,
    });

    expect(profile.displayName, 'Ngoại tuyến');
    expect(trip.title, 'Chuyến đi ngoại tuyến');
    expect(itinerary.activities.single.progressState, 'completed');
    expect(repository.status.pendingCount, 3);

    expect(
      () => repository.addExpense('trip-1', {
        'label': 'Không được xếp hàng',
        'amount_vnd': 1,
        'category': 'other',
        'spent_at': now.toIso8601String(),
        'notes': '',
      }),
      throwsA(isA<ApiException>()),
    );
    expect(repository.status.pendingCount, 3);
  });

  test('active-trip selection fails honestly while offline', () async {
    final live = _LiveFake();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: MemoryOfflinePersistence(),
      accountId: 'account-a',
      clock: () => now,
    );
    final trip = (await repository.listTrips('profile-1')).single;
    live.networkDown = true;

    await expectLater(
      repository.setActiveTrip(trip),
      throwsA(
        isA<ApiException>().having(
          (error) => error.code,
          'code',
          'NETWORK_ERROR',
        ),
      ),
    );

    expect(repository.activeTripId, 'trip-1');
    expect(repository.status.pendingCount, 0);
  });

  test('removes a successful replay and never applies it twice', () async {
    final live = _LiveFake();
    final persistence = MemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );
    await repository.listProfiles();
    await repository.listTrips('profile-1');
    await repository.getTrip('trip-1');
    await repository.listExpenses('trip-1');
    live.networkDown = true;
    await repository.updateExpense('expense-1', {
      'amount_vnd': 125000,
      'version': 1,
    });

    live.networkDown = false;
    await repository.synchronize();
    await repository.synchronize();

    expect(repository.status.pendingCount, 0);
    expect(live.expenses.single.amountVnd, 125000);
    expect(live.expenses.single.version, 2);
  });

  test(
    'resumes an interrupted ordered replay without duplicating success',
    () async {
      final live = _LiveFake();
      final persistence = MemoryOfflinePersistence();
      final repository = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );
      await repository.listProfiles();
      await repository.listTrips('profile-1');
      await repository.getTrip('trip-1');
      await repository.listExpenses('trip-1');
      live.networkDown = true;
      await repository.updateExpense('expense-1', {
        'amount_vnd': 125000,
        'version': 1,
      });
      await repository.updateProfile('profile-1', {
        'display_name': 'Đặng Hùng offline',
        'version': 1,
      });

      live
        ..networkDown = false
        ..interruptReplayAt = 2;
      final interrupted = await repository.synchronize();

      expect(interrupted.isSyncing, isFalse);
      expect(interrupted.pendingCount, 1);
      expect(live.expenses.single.version, 2);
      expect(live.replayLog, ['expense:expense-1', 'profile:profile-1']);

      live.interruptReplayAt = null;
      await repository.synchronize();

      expect(repository.status.pendingCount, 0);
      expect(live.expenses.single.version, 2);
      expect(live.profiles.single.displayName, 'Đặng Hùng offline');
      expect(live.replayLog, [
        'expense:expense-1',
        'profile:profile-1',
        'profile:profile-1',
      ]);
    },
  );

  test(
    'continues independent replay and explicitly retries a conflict',
    () async {
      final live = _LiveFake();
      final persistence = MemoryOfflinePersistence();
      final repository = OfflineManagementRepository(
        live: live,
        persistence: persistence,
        accountId: 'account-a',
        clock: () => now,
      );
      await repository.listProfiles();
      await repository.listTrips('profile-1');
      await repository.getTrip('trip-1');
      await repository.listExpenses('trip-1');
      live.networkDown = true;
      await repository.updateExpense('expense-1', {
        'amount_vnd': 125000,
        'version': 1,
      });
      await repository.updateProfile('profile-1', {
        'display_name': 'Đặng Hùng offline',
        'version': 1,
      });

      live
        ..networkDown = false
        ..conflictExpense = true;
      await repository.synchronize();

      expect(repository.status.conflictCount, 1);
      expect(repository.status.pendingCount, 0);
      expect(live.profiles.single.displayName, 'Đặng Hùng offline');

      live.conflictExpense = false;
      final retried = await repository.retryConflicts();
      expect(retried.isSyncing, isFalse);
      expect(retried.conflictCount, 0);
      expect(retried.pendingCount, 0);
      expect(live.expenses.single.amountVnd, 125000);
    },
  );

  test('marks a terminal replay failure until it is discarded', () async {
    final live = _LiveFake();
    final persistence = MemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );
    await repository.listTrips('profile-1');
    await repository.getTrip('trip-1');
    live.networkDown = true;
    await repository.updateTrip('trip-1', {
      'title': 'Không hợp lệ',
      'version': 1,
    });

    live
      ..networkDown = false
      ..terminalTrip = true;
    await repository.synchronize();

    expect(repository.status.failedCount, 1);
    expect(repository.status.pendingCount, 0);
    await repository.discardConflicts();
    expect(repository.status.failedCount, 0);
  });

  test('retains a version conflict until it is explicitly discarded', () async {
    final live = _LiveFake();
    final persistence = MemoryOfflinePersistence();
    final repository = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );
    await repository.listProfiles();
    await repository.listTrips('profile-1');
    await repository.getTrip('trip-1');
    await repository.listExpenses('trip-1');
    live.networkDown = true;
    await repository.updateExpense('expense-1', {
      'amount_vnd': 125000,
      'version': 1,
    });

    live
      ..networkDown = false
      ..conflictExpense = true;
    await repository.synchronize();
    expect(repository.status.pendingCount, 0);
    expect(repository.status.conflictCount, 1);

    await repository.discardConflicts();
    expect(repository.status.conflictCount, 0);
  });

  test('never exposes account A cache through account B', () async {
    final live = _LiveFake();
    final persistence = MemoryOfflinePersistence();
    final accountA = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-a',
      clock: () => now,
    );
    await accountA.listProfiles();
    live.networkDown = true;

    final accountB = OfflineManagementRepository(
      live: live,
      persistence: persistence,
      accountId: 'account-b',
      clock: () => now,
    );
    await expectLater(accountB.listProfiles(), throwsA(isA<ApiException>()));

    await accountA.clearAccount();
    expect(persistence.values, isNot(contains('account-a')));
  });
}

class _LiveFake extends FakeManagementRepository
    implements LiveManagementRepository {
  _LiveFake() : super(seeded: true) {
    expenses.add(
      ExpenseItem(
        id: 'expense-1',
        label: 'Bữa sáng',
        amountVnd: 100000,
        category: 'food',
        spentAt: DateTime.utc(2026, 10, 17, 8),
        notes: '',
        version: 1,
      ),
    );
    activities.add(
      ActivityItem(
        id: 'activity-1',
        position: 0,
        title: 'Cầu Rồng',
        notes: '',
        latitude: 16.0611,
        longitude: 108.2274,
        startAt: DateTime.utc(2026, 10, 17, 9),
        endAt: DateTime.utc(2026, 10, 17, 10),
        category: 'landmark',
        estimatedCostVnd: 0,
        source: 'external_reference',
        version: 1,
      ),
    );
  }

  bool networkDown = false;
  bool conflictExpense = false;
  bool terminalTrip = false;
  int? interruptReplayAt;
  Completer<(List<UserProfile>, String?)>? profileReadGate;
  int _replayAttempt = 0;
  final List<String> replayLog = [];

  Never _offline() => throw const ApiException('NETWORK_ERROR', 'Mất mạng.');

  void _beforeReplay(String label) {
    if (networkDown) _offline();
    replayLog.add(label);
    _replayAttempt += 1;
    if (_replayAttempt == interruptReplayAt) _offline();
  }

  @override
  String? get activeTripId => 'trip-1';

  @override
  set activeTripId(String? value) {}

  @override
  Future<void> setActiveTrip(Trip? trip) async {
    if (networkDown) _offline();
  }

  @override
  Future<(List<UserProfile>, String?)> listProfiles() {
    final gate = profileReadGate;
    if (gate != null) return gate.future;
    if (networkDown) _offline();
    return super.listProfiles();
  }

  @override
  Future<List<Trip>> listTrips(String profileId, {String? state}) {
    if (networkDown) _offline();
    return super.listTrips(profileId, state: state);
  }

  @override
  Future<(Trip, ItineraryData, ExpenseSummaryData)> getTrip(String id) {
    if (networkDown) _offline();
    return super.getTrip(id);
  }

  @override
  Future<(List<ExpenseItem>, ExpenseSummaryData)> listExpenses(String tripId) {
    if (networkDown) _offline();
    return super.listExpenses(tripId);
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> updateExpense(
    String id,
    Map<String, dynamic> data,
  ) {
    _beforeReplay('expense:$id');
    if (conflictExpense) {
      throw const ApiException(
        'VERSION_CONFLICT',
        'Khoản chi đã thay đổi.',
        statusCode: 409,
      );
    }
    return super.updateExpense(id, data);
  }

  @override
  Future<UserProfile> updateProfile(String id, Map<String, dynamic> data) {
    _beforeReplay('profile:$id');
    return super.updateProfile(id, data);
  }

  @override
  Future<Trip> updateTrip(String id, Map<String, dynamic> data) {
    _beforeReplay('trip:$id');
    if (terminalTrip) {
      throw const ApiException(
        'VALIDATION_ERROR',
        'Dữ liệu chuyến đi không hợp lệ.',
        statusCode: 422,
      );
    }
    return super.updateTrip(id, data);
  }

  @override
  Future<ItineraryData> updateActivity(String id, Map<String, dynamic> data) {
    _beforeReplay('activity:$id');
    return super.updateActivity(id, data);
  }

  @override
  Future<(ExpenseItem, ExpenseSummaryData)> addExpense(
    String tripId,
    Map<String, dynamic> data,
  ) {
    if (networkDown) _offline();
    return super.addExpense(tripId, data);
  }
}

class _BlockingMemoryOfflinePersistence extends MemoryOfflinePersistence {
  final writeStarted = Completer<void>();
  final releaseWrite = Completer<void>();

  @override
  Future<void> write(String accountId, String value) async {
    writeStarted.complete();
    await releaseWrite.future;
    await super.write(accountId, value);
  }
}
