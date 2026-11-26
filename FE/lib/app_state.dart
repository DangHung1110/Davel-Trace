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
  int _routePreviewRevision = 0;
  DemoSource demoSource = DemoSource.seeded;
  List<PlanAlternative> planAlternatives = PlanAlternative.seeded();
  PlanAlternative? activeAlternative;
  AcceptanceSummary? acceptance;
  String? currentPlanningRequestId;
  List<ItineraryVersionSummary> itineraryVersions = [];
  SavedItineraryPlan? _savedItineraryPlan;
  Map<String, dynamic>? aiReadiness;
  AiInterpretationProposal? aiProposal;
  PlanExplanation? planExplanation;
  bool isInterpreting = false;
  bool isExplaining = false;
  String? aiMessage;
  Map<String, dynamic> _confirmedPlanningOverrides = const {};
  int _aiRequestRevision = 0;
  int _planningRevision = 0;
  bool _disposed = false;
  bool isPlanning = false;
  String plannerMessage =
      'Đang dùng dữ liệu mẫu trên máy. Bấm tạo phương án để thử FastAPI.';
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
    if (activeTrip?.id != id) {
      skipAiProposal();
      _resetPlanningContext();
    }
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
        await _loadItineraryVersions(id);
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

  void _resetPlanningContext() {
    _planningRevision++;
    isPlanning = false;
    planAlternatives = isDemoManagement ? PlanAlternative.seeded() : [];
    activeAlternative = null;
    acceptance = null;
    currentPlanningRequestId = null;
    itineraryVersions = [];
    _savedItineraryPlan = null;
    demoSource = DemoSource.seeded;
  }

  @override
  void dispose() {
    _disposed = true;
    _planningRevision++;
    super.dispose();
  }

  void _clearTripData({bool keepTrips = false}) {
    _resetPlanningContext();
    _aiRequestRevision += 1;
    isInterpreting = false;
    aiProposal = null;
    aiMessage = null;
    planExplanation = null;
    _confirmedPlanningOverrides = const {};
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
    _resetPlanningContext();
    skipAiProposal();
    activeTrip = updated;
    trips = [for (final item in trips) item.id == updated.id ? updated : item];
    await _loadTripDetail(updated.id);
  });

  Future<void> setPlanningHotel(String? poiId) async {
    final trip = activeTrip;
    if (trip == null || trip.basePoiId == poiId) return;
    final preferences = {...trip.preferenceOverrides};
    if (poiId == null) {
      preferences.remove('base_poi_id');
    } else {
      preferences['base_poi_id'] = poiId;
    }
    await updateActiveTrip({'preference_overrides': preferences});
  }

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

  SavedItineraryPlan? get savedPlanForSelectedDay {
    final saved = _savedItineraryPlan;
    final selected = selectedTripDate;
    final planned = saved?.date ?? activeTrip?.startDate;
    if (saved == null ||
        saved.tripId != activeTrip?.id ||
        saved.plan.activities.isEmpty) {
      return null;
    }
    return selected == null ||
            (planned != null &&
                selected.year == planned.year &&
                selected.month == planned.month &&
                selected.day == planned.day)
        ? saved
        : null;
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
    if (selectedTripDate == date) return;
    selectedTripDate = date;
    routePreview = null;
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
    final revision = ++_routePreviewRevision;
    final tripId = activeTrip?.id;
    final itinerarySnapshot = itinerary;
    final date = selectedTripDate;
    final allActivities = activitiesForSelectedDay;
    final activities = allActivities
        .where((item) => item.poiId != null)
        .toList();
    final customCount = allActivities.length - activities.length;
    final placeLookup = _loadMapPlaces(activities.map((item) => item.poiId!));
    RoutePreviewData result;
    if (tripId == null || activities.length < 2) {
      result = RoutePreviewData(
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
    } else {
      try {
        result = await repository.previewRoute(
          tripId,
          activities.map((item) => item.id).toList(),
        );
      } catch (_) {
        result = const RoutePreviewData(
          source: 'none',
          isRealRoute: false,
          distanceM: 0,
          durationS: 0,
          quality: 'unavailable',
          warning: 'Không thể tải thông tin tuyến lúc này.',
        );
      }
      if (customCount > 0) {
        result = RoutePreviewData(
          source: result.source,
          isRealRoute: result.isRealRoute,
          distanceM: result.distanceM,
          durationS: result.durationS,
          quality: result.quality,
          geometry: result.geometry,
          warning: [
            result.warning,
            '$customCount hoạt động chưa có điểm đến trên bản đồ.',
          ].whereType<String>().where((value) => value.isNotEmpty).join(' '),
        );
      }
    }
    await placeLookup;
    if (_disposed ||
        revision != _routePreviewRevision ||
        activeTrip?.id != tripId ||
        selectedTripDate != date ||
        !identical(itinerarySnapshot, itinerary)) {
      return;
    }
    routePreview = result;
    notifyListeners();
  }

  Future<void> _loadMapPlaces(Iterable<String> poiIds) async {
    final ids = poiIds
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

  Future<void> requestPlan({bool group = false}) async {
    final trip = activeTrip;
    final profile = activeProfile;
    if (trip == null || profile == null) return;
    final overrides = {
      ..._confirmedPlanningOverrides,
      'base_poi_id': ?trip.basePoiId,
    };
    final revision = _planningRevision;
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
        'constraint_overrides': overrides,
        '_idempotency_key': group
            ? 'group-plan-${trip.id}-${DateTime.now().microsecondsSinceEpoch}'
            : _planningKeys.putIfAbsent(
                '${trip.id}:${trip.version}:$overrides',
                () =>
                    'plan-${trip.id}-${DateTime.now().microsecondsSinceEpoch}',
              ),
      });
      if (_disposed || revision != _planningRevision) return;
      if (result.status == 'failed') {
        throw ApiException(
          result.failureCode ?? 'PLANNING_FAILED',
          'Không thể lập lịch với dữ liệu hiện tại. Hãy kiểm tra ràng buộc chuyến đi.',
        );
      }
      if (result.items.isEmpty) {
        throw const ApiException(
          'NO_FEASIBLE_PLAN',
          'Chưa tìm được lịch phù hợp. Hãy điều chỉnh thời gian hoặc ngân sách rồi thử lại.',
        );
      }
      planAlternatives = result.items;
      activeAlternative = result.items.first;
      acceptance = null;
      currentPlanningRequestId = result.requestId;
      demoSource = DemoSource.live;
      plannerMessage = group
          ? 'Đã gửi ${result.items.length} phương án để cả nhóm xem và góp ý.'
          : 'Đã tìm được ${result.items.length} lịch gợi ý.';
      _confirmedPlanningOverrides = const {};
    } catch (error) {
      if (_disposed || revision != _planningRevision) return;
      demoSource = planAlternatives.isEmpty
          ? DemoSource.seeded
          : DemoSource.stale;
      if (planAlternatives.isEmpty) {
        if (isDemoManagement) planAlternatives = PlanAlternative.seeded();
      }
      plannerMessage = 'Chưa tải được lịch gợi ý. Bạn có thể thử lại.';
      errorMessage = _message(error);
    } finally {
      if (!_disposed && revision == _planningRevision) {
        isPlanning = false;
        notifyListeners();
      }
    }
  }

  Future<void> interpretPlanningRequest(String text) async {
    final trip = activeTrip;
    final repository = planningRepository;
    if (trip == null || repository is! AiPlanningRepository) {
      aiMessage = 'Trợ lý AI không có trong chế độ demo này.';
      notifyListeners();
      return;
    }
    final aiRepository = repository as AiPlanningRepository;
    final revision = ++_aiRequestRevision;
    isInterpreting = true;
    aiMessage = null;
    aiProposal = null;
    notifyListeners();
    try {
      final readiness = await aiRepository.aiReadiness();
      if (revision != _aiRequestRevision) return;
      aiReadiness = readiness;
      if (readiness['available'] != true ||
          (readiness['capabilities'] as Map?)?['interpretation'] != true) {
        throw const ApiException(
          'LLM_DISABLED',
          'Trợ lý AI chưa được cấu hình; bạn vẫn có thể tạo lịch trực tiếp.',
        );
      }
      final proposal = await aiRepository.interpret(trip.id, text);
      if (revision != _aiRequestRevision) return;
      aiProposal = proposal;
      aiMessage = proposal.placeResolutions.isNotEmpty
          ? 'Hãy chọn hoặc bỏ các địa điểm chưa xác định trong bước kiểm tra.'
          : proposal.unresolved.isEmpty
          ? 'Hãy kiểm tra đề xuất trước khi xác nhận.'
          : 'Có ${proposal.unresolved.length} giá trị chưa xác minh; chúng sẽ không được dùng.';
    } catch (error) {
      if (revision == _aiRequestRevision) {
        aiMessage = _message(error);
      }
    } finally {
      if (revision == _aiRequestRevision) {
        isInterpreting = false;
        notifyListeners();
      }
    }
  }

  Future<void> confirmAiProposalAndPlan({
    Map<String, dynamic>? corrections,
    bool group = false,
  }) async {
    final proposal = aiProposal;
    if (proposal == null) return;
    if (proposal.placeResolutions.isNotEmpty &&
        (corrections == null ||
            !corrections.containsKey('must_visit') ||
            !corrections.containsKey('avoid'))) {
      aiMessage =
          'Hãy kiểm tra và chọn hoặc bỏ các địa điểm trước khi lập lịch.';
      notifyListeners();
      return;
    }
    final confirmed = Map<String, dynamic>.from(proposal.confirmedOverrides);
    if (corrections != null) {
      for (final entry in corrections.entries) {
        if (entry.value == null) {
          confirmed.remove(entry.key);
        } else {
          confirmed[entry.key] = entry.value;
        }
      }
    }
    if (group) {
      for (final key in [
        'traveler_count',
        'indicative_budget',
        'day_start',
        'day_end',
      ]) {
        confirmed.remove(key);
      }
    }
    final mustVisit = List<String>.from(confirmed['must_visit'] as List? ?? []);
    final avoid = List<String>.from(confirmed['avoid'] as List? ?? []);
    if (mustVisit.toSet().intersection(avoid.toSet()).isNotEmpty) {
      aiMessage = 'Một địa điểm không thể vừa muốn ghé vừa muốn tránh.';
      notifyListeners();
      return;
    }
    _confirmedPlanningOverrides = confirmed;
    aiProposal = null;
    aiMessage = null;
    notifyListeners();
    await requestPlan(group: group);
  }

  void skipAiProposal() {
    _aiRequestRevision += 1;
    isInterpreting = false;
    isExplaining = false;
    planExplanation = null;
    aiProposal = null;
    aiMessage = null;
    _confirmedPlanningOverrides = const {};
    notifyListeners();
  }

  Future<void> explainPlan(PlanAlternative alternative) async {
    final repository = planningRepository;
    if (repository is! AiPlanningRepository) return;
    final aiRepository = repository as AiPlanningRepository;
    final revision = _aiRequestRevision;
    isExplaining = true;
    planExplanation = null;
    notifyListeners();
    try {
      final explanation = await aiRepository.explain(alternative.id);
      if (revision != _aiRequestRevision) return;
      planExplanation = explanation;
    } catch (error) {
      if (revision == _aiRequestRevision) aiMessage = _message(error);
    } finally {
      if (revision == _aiRequestRevision) {
        isExplaining = false;
        notifyListeners();
      }
    }
  }

  Future<void> acceptAlternative(PlanAlternative alternative) async {
    final tripId = activeTrip?.id;
    if (!isDemoManagement && demoSource != DemoSource.live) return;
    if (!alternative.gatePassed ||
        !planAlternatives.any((item) => item.id == alternative.id)) {
      return;
    }
    final revision = _planningRevision;
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
        final result = await planningRepository.accept(alternative.id, key);
        if (_disposed || revision != _planningRevision) return;
        acceptance = result;
        try {
          if (tripId != null) await _loadTripDetail(tripId);
        } catch (error) {
          errorMessage = 'Đã lưu lịch trình, nhưng chưa tải lại được. Hãy làm mới chuyến đi.';
        }
        if (isDemoManagement) await loadItineraryHistory();
        final planDate = _savedItineraryPlan?.date ?? activeTrip?.startDate;
        if (tripDates.contains(planDate)) selectedTripDate = planDate;
        plannerMessage =
            'Đã chốt và lưu acceptance ${acceptance!.id.substring(0, 8)}.';
      } else {
        plannerMessage =
            'Đã chọn cục bộ để demo; chưa tạo acceptance trên server.';
      }
    } catch (error) {
      if (_disposed || revision != _planningRevision) return;
      errorMessage = _message(error);
      plannerMessage =
          'Chưa thể chốt trên server; lựa chọn chỉ hiển thị cục bộ.';
    } finally {
      if (!_disposed && revision == _planningRevision) {
        isPlanning = false;
        notifyListeners();
      }
    }
  }

  Future<void> loadItineraryHistory() async {
    final trip = activeTrip;
    if (trip == null || planningRepository is! ItineraryLifecycleRepository) {
      return;
    }
    await _loadItineraryVersions(trip.id);
    if (!_disposed) notifyListeners();
  }

  Future<void> _loadItineraryVersions(String tripId) async {
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    final revision = _planningRevision;
    final versions = await lifecycle.history(tripId);
    if (_disposed || revision != _planningRevision) return;
    itineraryVersions = versions;
    final version = versions.where((item) => item.active).firstOrNull;
    final reader = planningRepository;
    if (version == null || reader is! ItineraryPlanReader) {
      _savedItineraryPlan = null;
      return;
    }
    if (_savedItineraryPlan?.versionId == version.id) return;
    _savedItineraryPlan = null;
    try {
      final saved = await (reader as ItineraryPlanReader).readVersion(
        version.id,
      );
      await _loadMapPlaces(
        saved.plan.activities.map((item) => item['poi_id']).whereType<String>(),
      );
      if (!_disposed &&
          revision == _planningRevision &&
          activeTrip?.id == tripId &&
          itineraryVersions.any(
            (item) => item.active && item.id == saved.versionId,
          )) {
        _savedItineraryPlan = saved;
      }
    } catch (_) {
      // Manual activities remain available when the saved snapshot cannot load.
    }
  }

  Future<void> activateItineraryVersion(ItineraryVersionSummary version) async {
    if (planningRepository is! ItineraryLifecycleRepository || version.active) {
      return;
    }
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    final revision = _planningRevision;
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      final key = _activationKeys.putIfAbsent(
        version.id,
        () => 'activate-${activeTrip?.id ?? 'trip'}-${version.id}',
      );
      await lifecycle.activateVersion(version.id, key);
      if (_disposed || revision != _planningRevision) return;
      final tripId = activeTrip?.id;
      if (tripId != null) await _loadTripDetail(tripId);
      if (isDemoManagement) await loadItineraryHistory();
      plannerMessage = 'Đã dùng lại lịch ${version.ordinal}.';
    } catch (error) {
      if (_disposed || revision != _planningRevision) return;
      errorMessage = _message(error);
    } finally {
      if (!_disposed && revision == _planningRevision) {
        isPlanning = false;
        notifyListeners();
      }
    }
  }

  Future<void> requestReplan({
    String? sourceVersionId,
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
    String? currentPoiId,
    String? remainingFrom,
    bool includeCurrentStop = false,
  }) async {
    final trip = activeTrip;
    final source =
        sourceVersionId ??
        itineraryVersions.where((item) => item.active).firstOrNull?.id;
    if (trip == null ||
        planningRepository is! ItineraryLifecycleRepository ||
        source == null) {
      return;
    }
    final lifecycle = planningRepository as ItineraryLifecycleRepository;
    final revision = _planningRevision;
    isPlanning = true;
    errorMessage = null;
    notifyListeners();
    try {
      final key = sourceVersionId != null
          ? 'group-replan-${trip.id}-${DateTime.now().microsecondsSinceEpoch}'
          : _replanKeys.putIfAbsent(
              '$source:${trip.version}',
              () => 'replan-${trip.id}-$source-${trip.version}',
            );
      final result = await lifecycle.replan(
        trip.id,
        source,
        key,
        completedActivityIds: completedActivityIds,
        skippedActivityIds: skippedActivityIds,
        currentPoiId: currentPoiId,
        remainingFrom: remainingFrom,
        includeCurrentStop: includeCurrentStop,
      );
      if (_disposed || revision != _planningRevision) return;
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
      if (_disposed || revision != _planningRevision) return;
      errorMessage = _message(error);
      plannerMessage = 'Chưa thể lập lại phần chuyến đi còn lại.';
    } finally {
      if (!_disposed && revision == _planningRevision) {
        isPlanning = false;
        notifyListeners();
      }
    }
  }

  void resetDemoPlanning() {
    demoSource = DemoSource.seeded;
    planAlternatives = PlanAlternative.seeded();
    activeAlternative = null;
    acceptance = null;
    currentPlanningRequestId = null;
    itineraryVersions = [];
    aiReadiness = null;
    aiProposal = null;
    planExplanation = null;
    aiMessage = null;
    _confirmedPlanningOverrides = const {};
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
