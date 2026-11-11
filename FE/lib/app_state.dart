import 'package:flutter/foundation.dart';

import 'core/errors/api_exception.dart';
import 'core/networking/api_client.dart';
import 'features/management/data/management_repository.dart';
import 'features/management/data/offline_management_repository.dart';
import 'features/management/data/offline_models.dart';
import 'features/management/domain/models.dart';
import 'features/planning/data/planning_repository.dart';
import 'features/planning/domain/models.dart';
import 'local_preferences.dart';

class AppState extends ChangeNotifier {
  AppState(
    this.repository, {
    LocalPreferences? preferences,
    PlanningRepository? planningRepository,
  }) : preferences = preferences ?? const LocalPreferences(),
       planningRepository =
           planningRepository ?? HttpPlanningRepository(ApiClient());

  final ManagementRepository repository;
  final LocalPreferences preferences;
  final PlanningRepository planningRepository;

  bool get isDemoManagement => repository is! LiveManagementRepository;

  OfflineSyncControl? get offlineSync => repository is OfflineSyncControl
      ? repository as OfflineSyncControl
      : null;

  SyncStatus? get syncStatus => offlineSync?.status;

  bool isLoading = true;
  bool isMutating = false;
  String? errorMessage;
  List<UserProfile> profiles = [];
  UserProfile? activeProfile;
  List<Trip> trips = [];
  List<Trip> archivedTrips = [];
  List<Trip> deletedTrips = [];
  Trip? activeTrip;
  ItineraryData? itinerary;
  DateTime? selectedTripDate;
  List<ExpenseItem> expenses = [];
  ExpenseSummaryData expenseSummary = ExpenseSummaryData.empty;
  List<PoiItem> pois = [];
  RoutePreviewData? routePreview;
  final Map<String, PoiItem?> mapPlaces = {};
  int _mapPlacesRevision = 0;
  DemoSource demoSource = DemoSource.seeded;
  List<PlanAlternative> planAlternatives = PlanAlternative.seeded();
  PlanAlternative? activeAlternative;
  AcceptanceSummary? acceptance;
  String? currentPlanningRequestId;
  List<ItineraryVersionSummary> itineraryVersions = [];
  Map<String, dynamic>? planningReadiness;
  bool isPlanning = false;
  bool _disposed = false;
  String plannerMessage =
      'Đang dùng dữ liệu mẫu trên máy. Bấm tạo phương án để thử FastAPI.';

  @override
  void notifyListeners() {
    if (!_disposed) super.notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  final Map<String, String> _planningKeys = {};
  final Map<String, String> _acceptanceKeys = {};
  final Map<String, String> _activationKeys = {};
  final Map<String, String> _replanKeys = {};

  Future<void> initialize() async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
      await offlineSync?.loadStatus();
      final result = await repository.listProfiles();
      profiles = result.$1;
      final preferredId = result.$2 ?? await preferences.activeProfileId();
      activeProfile = _findProfile(preferredId) ?? profiles.firstOrNull;
      if (activeProfile != null) {
        await _loadTrips(selectFirst: true);
      } else {
        _clearTripData();
      }
      await preferences.recordSuccessfulSync();
    } catch (error) {
      errorMessage = _message(error);
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  UserProfile? _findProfile(String? id) {
    if (id == null) return null;
    for (final profile in profiles) {
      if (profile.id == id) return profile;
    }
    return null;
  }

  Future<void> _loadTrips({String? selectId, bool selectFirst = false}) async {
    final profile = activeProfile;
    if (profile == null) return;
    trips = await repository.listTrips(profile.id);
    if (repository is LiveManagementRepository) {
      final lifecycle = await Future.wait([
        repository.listTrips(profile.id, state: 'archived'),
        repository.listTrips(profile.id, state: 'deleted'),
      ]);
      archivedTrips = lifecycle[0];
      deletedTrips = lifecycle[1];
    } else {
      archivedTrips = await repository.listTrips(profile.id, state: 'archived');
      deletedTrips = [];
    }
    Trip? selected;
    final liveActive = repository is LiveManagementRepository
        ? (repository as LiveManagementRepository).activeTripId
        : null;
    final wanted = selectId ?? activeTrip?.id ?? liveActive;
    if (wanted != null) {
      for (final trip in trips) {
        if (trip.id == wanted) selected = trip;
      }
    }
    selected ??= selectFirst && repository is! LiveManagementRepository
        ? trips.firstOrNull
        : null;
    if (selected == null) {
      _clearTripData(keepTrips: true);
    } else {
      await _loadTripDetail(selected.id);
    }
  }

  Future<void> _loadTripDetail(String id) async {
    final detail = await repository.getTrip(id);
    activeTrip = detail.$1;
    itinerary = detail.$2;
    expenseSummary = detail.$3;
    try {
      final expenseData = await repository.listExpenses(id);
      expenses = expenseData.$1;
      expenseSummary = expenseData.$2;
    } on ApiException catch (error) {
      if (error.statusCode != 404) rethrow;
      expenses = [];
      expenseSummary = ExpenseSummaryData(
        budgetVnd: activeTrip!.budgetVnd,
        spentVnd: 0,
        remainingVnd: activeTrip!.budgetVnd,
        byCategory: const {},
        alert: 'none',
      );
    }
    if (!isDemoManagement &&
        planningRepository is ItineraryLifecycleRepository) {
      try {
        itineraryVersions =
            await (planningRepository as ItineraryLifecycleRepository).history(
              id,
            );
      } catch (_) {
        itineraryVersions = [];
      }
    }
    routePreview = null;
    final selected = selectedTripDate;
    selectedTripDate =
        selected != null &&
            !selected.isBefore(activeTrip!.startDate) &&
            !selected.isAfter(activeTrip!.endDate)
        ? selected
        : activeTrip!.startDate;
  }

  void _clearTripData({bool keepTrips = false}) {
    if (!keepTrips) trips = [];
    activeTrip = null;
    itinerary = null;
    selectedTripDate = null;
    expenses = [];
    expenseSummary = ExpenseSummaryData.empty;
    routePreview = null;
    currentPlanningRequestId = null;
    itineraryVersions = [];
  }

  Future<void> refresh() => initialize();

  void clearForSignOut() {
    profiles = [];
    activeProfile = null;
    archivedTrips = [];
    deletedTrips = [];
    _clearTripData();
    errorMessage = null;
    isLoading = true;
    notifyListeners();
  }

  Future<T> _mutate<T>(Future<T> Function() action) async {
    isMutating = true;
    errorMessage = null;
    notifyListeners();
    try {
      return await action();
    } catch (error) {
      errorMessage = _message(error);
      rethrow;
    } finally {
      isMutating = false;
      notifyListeners();
    }
  }

  Future<void> createProfile(Map<String, dynamic> data) => _mutate(() async {
    final created = await repository.createProfile(data);
    profiles = [...profiles, created];
    await selectProfile(created);
  });

  Future<void> updateActiveProfile(Map<String, dynamic> data) =>
      _mutate(() async {
        final profile = activeProfile!;
        final updated = await repository.updateProfile(profile.id, {
          ...data,
          'version': profile.version,
        });
        profiles = [
          for (final item in profiles) item.id == updated.id ? updated : item,
        ];
        activeProfile = updated;
      });

  Future<void> resetActiveProfile() => _mutate(() async {
    final updated = await repository.resetProfile(activeProfile!);
    profiles = [
      for (final item in profiles) item.id == updated.id ? updated : item,
    ];
    activeProfile = updated;
  });

  Future<void> selectProfile(UserProfile profile) => _mutate(() async {
    await repository.setActiveProfile(profile.id);
    activeProfile = profile;
    await preferences.setActiveProfileId(profile.id);
    _clearTripData();
    await _loadTrips(selectFirst: true);
  });

  Future<void> deleteActiveProfile() => _mutate(() async {
    final profile = activeProfile!;
    await repository.deleteProfile(profile);
    profiles = profiles.where((item) => item.id != profile.id).toList();
    activeProfile = profiles.firstOrNull;
    _clearTripData();
    if (activeProfile != null) {
      await repository.setActiveProfile(activeProfile!.id);
      await _loadTrips(selectFirst: true);
    }
  });

  Future<void> createTrip(Map<String, dynamic> data) => _mutate(() async {
    final created = await repository.createTrip({
      ...data,
      'profile_id': activeProfile!.id,
      'city': 'da-nang',
    });
    if (repository is LiveManagementRepository) {
      await (repository as LiveManagementRepository).setActiveTrip(created);
    }
    await _loadTrips(selectId: created.id);
  });

  Future<void> updateActiveTrip(
    Map<String, dynamic> data, {
    bool confirmRemovedDays = false,
  }) => _mutate(() async {
    final trip = activeTrip!;
    final updated = await repository.updateTrip(trip.id, {
      ...data,
      'version': trip.version,
      'confirm_removed_days': confirmRemovedDays,
    });
    activeTrip = updated;
    trips = [for (final item in trips) item.id == updated.id ? updated : item];
  });

  Future<void> selectTrip(Trip trip) => _mutate(() async {
    if (repository is LiveManagementRepository) {
      await (repository as LiveManagementRepository).setActiveTrip(trip);
    }
    await _loadTripDetail(trip.id);
  });

  Future<void> clearActiveTrip() => _mutate(() async {
    if (repository is LiveManagementRepository) {
      await (repository as LiveManagementRepository).setActiveTrip(null);
    }
    _clearTripData(keepTrips: true);
  });

  Future<void> archiveActiveTrip() => _mutate(() async {
    final trip = activeTrip!;
    final archived = await repository.archiveTrip(trip);
    trips = trips.where((item) => item.id != trip.id).toList();
    archivedTrips = [archived, ...archivedTrips];
    _clearTripData(keepTrips: true);
  });

  Future<void> restoreTrip(Trip trip) => _mutate(() async {
    final restored = await repository.restoreTrip(trip);
    archivedTrips = archivedTrips.where((item) => item.id != trip.id).toList();
    deletedTrips = deletedTrips.where((item) => item.id != trip.id).toList();
    trips = [restored, ...trips];
  });

  Future<void> deleteActiveTrip() => _mutate(() async {
    final trip = activeTrip!;
    await repository.deleteTrip(trip);
    if (repository is LiveManagementRepository) {
      (repository as LiveManagementRepository).activeTripId = null;
    }
    trips = trips.where((item) => item.id != trip.id).toList();
    deletedTrips = repository is LiveManagementRepository
        ? await repository.listTrips(activeProfile!.id, state: 'deleted')
        : [trip, ...deletedTrips];
    if (repository is LiveManagementRepository) {
      _clearTripData(keepTrips: true);
    } else {
      final next = trips.firstOrNull;
      if (next == null) {
        _clearTripData(keepTrips: true);
      } else {
        await _loadTripDetail(next.id);
      }
    }
  });

  Future<void> saveActivity({
    ActivityItem? existing,
    required Map<String, dynamic> data,
  }) => _mutate(() async {
    final current = itinerary!;
    itinerary = existing == null
        ? await repository.addActivity(activeTrip!.id, {
            ...data,
            'itinerary_version': current.version,
          })
        : await repository.updateActivity(existing.id, {
            ...data,
            'trip_id': activeTrip!.id,
            'version': existing.version,
            'itinerary_version': current.version,
          });
    routePreview = null;
  });

  Future<void> deleteActivity(ActivityItem activity) => _mutate(() async {
    itinerary = await repository.deleteActivity(activity, itinerary!.version);
    routePreview = null;
  });

  Future<void> setActivityStatus(ActivityItem activity, String status) =>
      _mutate(() async {
        itinerary = await repository.updateActivity(activity.id, {
          'version': activity.version,
          'trip_id': activeTrip!.id,
          'progress_state': status,
        });
      });

  Future<void> moveActivity(int from, int to) => _mutate(() async {
    final current = itinerary!;
    final activities = [...activitiesForSelectedDay];
    final item = activities.removeAt(from);
    activities.insert(to, item);
    itinerary = await repository.reorderActivities(
      activeTrip!.id,
      activities.map((activity) => activity.id).toList(),
      current.version,
    );
    routePreview = null;
  });

  List<ActivityItem> get activitiesForSelectedDay {
    final date = selectedTripDate;
    if (date == null) return itinerary?.activities ?? const [];
    return (itinerary?.activities ?? const <ActivityItem>[])
        .where(
          (item) =>
              item.startAt.year == date.year &&
              item.startAt.month == date.month &&
              item.startAt.day == date.day,
        )
        .toList();
  }

  List<DateTime> get tripDates {
    final trip = activeTrip;
    if (trip == null) return const [];
    return List.generate(
      trip.endDate.difference(trip.startDate).inDays + 1,
      (index) => trip.startDate.add(Duration(days: index)),
    );
  }

  void selectTripDate(DateTime date) {
    selectedTripDate = date;
    notifyListeners();
  }

  Future<List<PoiItem>> searchPois(String query) async {
    try {
      pois = await repository.searchPois(query);
      notifyListeners();
      return pois;
    } catch (error) {
      errorMessage = _message(error);
      notifyListeners();
      rethrow;
    }
  }

  Future<PoiItem> getPoiDetails(String id) async {
    try {
      return await repository.getPoiDetails(id);
    } catch (error) {
      errorMessage = _message(error);
      notifyListeners();
      rethrow;
    }
  }

  Future<void> saveExpense({
    ExpenseItem? existing,
    required Map<String, dynamic> data,
  }) => _mutate(() async {
    if (existing == null) {
      final result = await repository.addExpense(activeTrip!.id, data);
      expenses = [result.$1, ...expenses];
      expenseSummary = result.$2;
    } else {
      final result = await repository.updateExpense(existing.id, {
        ...data,
        'version': existing.version,
      });
      expenses = [
        for (final item in expenses) item.id == existing.id ? result.$1 : item,
      ];
      expenseSummary = result.$2;
    }
  });

  Future<void> deleteExpense(ExpenseItem expense) => _mutate(() async {
    expenseSummary = await repository.deleteExpense(expense);
    expenses = expenses.where((item) => item.id != expense.id).toList();
  });

  Future<void> synchronizeOfflineChanges() => _mutate(() async {
    final sync = offlineSync;
    if (sync == null) return;
    await sync.synchronize();
    await initialize();
  });

  Future<void> discardOfflineConflicts() => _mutate(() async {
    final sync = offlineSync;
    if (sync == null) return;
    await sync.discardConflicts();
    await initialize();
  });

  Future<void> clearOfflineAccount() async => offlineSync?.clearAccount();

  Future<Map<String, dynamic>> exportExpenses({
    String? date,
    String? category,
  }) async {
    final trip = activeTrip;
    if (trip == null) return const {};
    try {
      return await repository.exportExpenses(
        trip.id,
        date: date,
        category: category,
      );
    } catch (error) {
      errorMessage = _message(error);
      notifyListeners();
      rethrow;
    }
  }

  Future<void> loadRoutePreview() async {
    final allActivities = itinerary?.activities ?? const <ActivityItem>[];
    final activities = allActivities
        .where((item) => item.poiId != null)
        .toList();
    final customCount = allActivities.length - activities.length;
    final placeLookup = _loadMapPlaces(activities);
    if (activeTrip == null || activities.length < 2) {
      routePreview = RoutePreviewData(
        source: 'none',
        isRealRoute: false,
        distanceM: 0,
        durationS: 0,
        quality: 'unavailable',
        warning: customCount == 0
            ? 'Cần ít nhất hai hoạt động có liên kết địa điểm để xem tuyến.'
            : 'Cần ít nhất hai hoạt động có liên kết địa điểm. '
                  '$customCount hoạt động riêng được bỏ qua.',
      );
      await placeLookup;
      notifyListeners();
      return;
    }
    try {
      routePreview = await repository.previewRoute(
        activeTrip!.id,
        activities.map((item) => item.id).toList(),
      );
    } catch (_) {
      routePreview = const RoutePreviewData(
        source: 'none',
        isRealRoute: false,
        distanceM: 0,
        durationS: 0,
        quality: 'unavailable',
        warning: 'Không thể tải thông tin tuyến lúc này.',
      );
    }
    if (customCount > 0) {
      final current = routePreview!;
      routePreview = RoutePreviewData(
        source: current.source,
        isRealRoute: current.isRealRoute,
        distanceM: current.distanceM,
        durationS: current.durationS,
        quality: current.quality,
        geometry: current.geometry,
        warning: [
          current.warning,
          '$customCount hoạt động riêng không có POI nên được bỏ qua.',
        ].whereType<String>().where((value) => value.isNotEmpty).join(' '),
      );
    }
    await placeLookup;
    notifyListeners();
  }

  Future<void> _loadMapPlaces(List<ActivityItem> activities) async {
    final ids = activities
        .map((item) => item.poiId!)
        .toSet()
        .where((id) => !mapPlaces.containsKey(id))
        .toList();
    if (ids.isEmpty) return;
    final revision = ++_mapPlacesRevision;
    final places = await Future.wait(
      ids.map((id) async {
        try {
          return MapEntry<String, PoiItem?>(
            id,
            await repository.getPoiDetails(id),
          );
        } catch (_) {
          return MapEntry<String, PoiItem?>(id, null);
        }
      }),
    );
    if (revision != _mapPlacesRevision) return;
    mapPlaces.addEntries(places.where((entry) => entry.value != null));
  }

  Future<void> requestPlan() async {
    final trip = activeTrip;
    final profile = activeProfile;
    if (trip == null || profile == null) return;
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      final result = await planningRepository.requestPlan({
        'trip_id': trip.id,
        'user_id': profile.id,
        'city': 'da-nang',
        'date': isoDate(trip.startDate),
        'start_time': trip.dayStart.substring(0, 5),
        'end_time': trip.dayEnd.substring(0, 5),
        'days': 1,
        'travelers': trip.travelers,
        'budget': trip.budgetVnd,
        'transport': [trip.transport],
        'must_visit': <String>[],
        'avoid': profile.mustAvoid,
        'activities': <String>[],
        'food_prefs': profile.foodPreferences,
        'profile': {
          'party_type': profile.partyType,
          'trip_purpose': profile.tripPurpose,
          'spending_level': profile.spendingLevel,
          'pace': profile.pace,
          'fitness': profile.fitness,
          'food_prefs': profile.foodPreferences,
          'must_avoid': profile.mustAvoid,
          'transport': [trip.transport],
        },
        'target_count': 5,
        '_idempotency_key': _planningKeys.putIfAbsent(
          '${trip.id}:${trip.version}',
          () => 'plan-${trip.id}-v${trip.version}',
        ),
      });
      if (result.status == 'failed') {
        throw ApiException(
          result.failureCode ?? 'PLANNING_FAILED',
          'Không thể lập lịch với dữ liệu hiện tại. Hãy kiểm tra ràng buộc chuyến đi.',
        );
      }
      if (result.items.isEmpty) {
        throw const ApiException(
          'NO_FEASIBLE_PLAN',
          'Backend chưa tìm được phương án khả thi.',
        );
      }
      planAlternatives = result.items;
      activeAlternative = result.items.first;
      acceptance = null;
      currentPlanningRequestId = result.requestId;
      demoSource = DemoSource.live;
      plannerMessage = result.shortageReason == null
          ? 'FastAPI đã trả ${result.items.length} phương án qua cổng cứng.'
          : 'FastAPI trả ${result.items.length} phương án; không thêm phương án kém chỉ để đủ số lượng.';
      try {
        planningReadiness = await planningRepository.readiness();
      } catch (_) {
        planningReadiness = null;
      }
    } catch (error) {
      demoSource = planAlternatives.isEmpty
          ? DemoSource.seeded
          : DemoSource.stale;
      if (planAlternatives.isEmpty) {
        planAlternatives = PlanAlternative.seeded();
      }
      plannerMessage = 'Không nối được planner; giữ dữ liệu demo và không giả lập lưu server.';
      errorMessage = _message(error);
    } finally {
      isPlanning = false;
      notifyListeners();
    }
  }

  Future<void> acceptAlternative(PlanAlternative alternative) async {
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      activeAlternative = alternative;
      acceptance = null;
      if (demoSource == DemoSource.live) {
        final key = _acceptanceKeys.putIfAbsent(
          alternative.id,
          () => 'accept-${activeTrip?.id ?? 'trip'}-${alternative.id}',
        );
        acceptance = await planningRepository.accept(alternative.id, key);
        await loadItineraryHistory();
        plannerMessage =
            'Đã chốt và lưu acceptance ${acceptance!.id.substring(0, 8)}.';
      } else {
        plannerMessage =
            'Đã chọn cục bộ để demo; chưa tạo acceptance trên server.';
      }
    } catch (error) {
      errorMessage = _message(error);
      plannerMessage =
          'Chưa thể chốt trên server; lựa chọn chỉ hiển thị cục bộ.';
    } finally {
      isPlanning = false;
      notifyListeners();
    }
  }

  Future<void> loadItineraryHistory() async {
    final trip = activeTrip;
    if (trip == null || planningRepository is! ItineraryLifecycleRepository) {
      return;
    }
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    itineraryVersions = await lifecycle.history(trip.id);
    notifyListeners();
  }

  Future<void> activateItineraryVersion(ItineraryVersionSummary version) async {
    if (planningRepository is! ItineraryLifecycleRepository || version.active) {
      return;
    }
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      final key = _activationKeys.putIfAbsent(
        version.id,
        () => 'activate-${activeTrip?.id ?? 'trip'}-${version.id}',
      );
      await lifecycle.activateVersion(version.id, key);
      await loadItineraryHistory();
      plannerMessage = 'Đã kích hoạt lại phiên bản ${version.ordinal}.';
    } catch (error) {
      errorMessage = _message(error);
    } finally {
      isPlanning = false;
      notifyListeners();
    }
  }

  Future<void> requestReplan() async {
    final trip = activeTrip;
    final source = itineraryVersions.where((item) => item.active).firstOrNull;
    if (trip == null ||
        planningRepository is! ItineraryLifecycleRepository ||
        source == null) {
      return;
    }
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      final key = _replanKeys.putIfAbsent(
        source.id,
        () => 'replan-${trip.id}-${source.id}',
      );
      final result = await lifecycle.replan(trip.id, source.id, key);
      if (result.status == 'failed') {
        throw ApiException(
          result.failureCode ?? 'REPLAN_FAILED',
          'Không thể lập lại phần còn lại với các ràng buộc hiện tại.',
        );
      }
      if (result.items.isEmpty) {
        throw const ApiException(
          'NO_FEASIBLE_REPLAN',
          'Không còn phương án khả thi cho phần chuyến đi còn lại.',
        );
      }
      planAlternatives = result.items;
      activeAlternative = result.items.first;
      acceptance = null;
      currentPlanningRequestId = result.requestId;
      demoSource = DemoSource.live;
      plannerMessage =
          'Đã tạo ${result.items.length} phương án cho phần còn lại.';
    } catch (error) {
      errorMessage = _message(error);
      plannerMessage = 'Chưa thể lập lại phần chuyến đi còn lại.';
    } finally {
      isPlanning = false;
      notifyListeners();
    }
  }

  void resetDemoPlanning() {
    demoSource = DemoSource.seeded;
    planAlternatives = PlanAlternative.seeded();
    activeAlternative = null;
    acceptance = null;
    currentPlanningRequestId = null;
    itineraryVersions = [];
    planningReadiness = null;
    plannerMessage = 'Đã quay về dữ liệu demo trên thiết bị.';
    notifyListeners();
  }

  String _message(Object error) => error is ApiException
      ? error.message
      : 'Có lỗi không mong muốn. Hãy thử lại.';
}

extension _FirstOrNull<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
