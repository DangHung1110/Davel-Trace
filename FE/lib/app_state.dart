import 'package:flutter/foundation.dart';

import 'api/api_exception.dart';
import 'features/management/data/management_repository.dart';
import 'features/management/domain/models.dart';
import 'local_preferences.dart';

class AppState extends ChangeNotifier {
  AppState(this.repository, {LocalPreferences? preferences})
    : preferences = preferences ?? const LocalPreferences();

  final ManagementRepository repository;
  final LocalPreferences preferences;

  bool isLoading = true;
  bool isMutating = false;
  String? errorMessage;
  List<UserProfile> profiles = [];
  UserProfile? activeProfile;
  List<Trip> trips = [];
  Trip? activeTrip;
  ItineraryData? itinerary;
  List<ExpenseItem> expenses = [];
  ExpenseSummaryData expenseSummary = ExpenseSummaryData.empty;
  List<PoiItem> pois = [];
  RoutePreviewData? routePreview;

  Future<void> initialize() async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
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
    Trip? selected;
    final wanted = selectId ?? activeTrip?.id;
    if (wanted != null) {
      for (final trip in trips) {
        if (trip.id == wanted) selected = trip;
      }
    }
    selected ??= selectFirst ? trips.firstOrNull : null;
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
    final expenseData = await repository.listExpenses(id);
    expenses = expenseData.$1;
    expenseSummary = expenseData.$2;
    routePreview = null;
  }

  void _clearTripData({bool keepTrips = false}) {
    if (!keepTrips) trips = [];
    activeTrip = null;
    itinerary = null;
    expenses = [];
    expenseSummary = ExpenseSummaryData.empty;
    routePreview = null;
  }

  Future<void> refresh() => initialize();

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
    await _loadTrips(selectId: created.id);
  });

  Future<void> updateActiveTrip(Map<String, dynamic> data) => _mutate(() async {
    final trip = activeTrip!;
    final updated = await repository.updateTrip(trip.id, {
      ...data,
      'version': trip.version,
    });
    activeTrip = updated;
    trips = [for (final item in trips) item.id == updated.id ? updated : item];
  });

  Future<void> selectTrip(Trip trip) => _mutate(() => _loadTripDetail(trip.id));

  Future<void> deleteActiveTrip() => _mutate(() async {
    final trip = activeTrip!;
    await repository.deleteTrip(trip);
    trips = trips.where((item) => item.id != trip.id).toList();
    final next = trips.firstOrNull;
    if (next == null) {
      _clearTripData(keepTrips: true);
    } else {
      await _loadTripDetail(next.id);
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
            'version': existing.version,
            'itinerary_version': current.version,
          });
    routePreview = null;
  });

  Future<void> deleteActivity(ActivityItem activity) => _mutate(() async {
    itinerary = await repository.deleteActivity(activity, itinerary!.version);
    routePreview = null;
  });

  Future<void> moveActivity(int from, int to) => _mutate(() async {
    final current = itinerary!;
    final activities = [...current.activities];
    final item = activities.removeAt(from);
    activities.insert(to, item);
    itinerary = await repository.reorderActivities(
      activeTrip!.id,
      activities.map((activity) => activity.id).toList(),
      current.version,
    );
    routePreview = null;
  });

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

  Future<void> loadRoutePreview() async {
    final activities = itinerary?.activities ?? const <ActivityItem>[];
    if (activeTrip == null || activities.length < 2) {
      routePreview = null;
      notifyListeners();
      return;
    }
    try {
      routePreview = await repository.previewRoute(
        activeTrip!.id,
        activities.map((item) => item.id).toList(),
      );
    } catch (_) {
      routePreview = null;
    }
    notifyListeners();
  }

  String _message(Object error) => error is ApiException
      ? error.message
      : 'Có lỗi không mong muốn. Hãy thử lại.';
}

extension _FirstOrNull<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
