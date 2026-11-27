import 'package:davel_trace/app.dart';
import 'package:davel_trace/app_state.dart';
import 'package:davel_trace/core/errors/api_exception.dart';
import 'package:davel_trace/features/itinerary/presentation/itinerary_screen.dart';
import 'package:davel_trace/features/itinerary/presentation/planning_request_review.dart';
import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/features/map/presentation/widgets/map_canvas.dart';
import 'package:davel_trace/features/planning/data/planning_repository.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:davel_trace/features/shell/presentation/main_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/fake_management_repository.dart';

class _LifecyclePlanningRepository
    implements
        PlanningRepository,
        ItineraryLifecycleRepository,
        ItineraryPlanReader {
  final planningKeys = <String>[];
  final acceptanceKeys = <String>[];
  final replanKeys = <String>[];
  final overrides = <Map<String, dynamic>>[];
  SavedItineraryPlan? savedPlan;

  static const alternative = PlanAlternative(
    id: 'alternative-010',
    profile: 'Cân bằng',
    activities: [],
    rank: 1,
    gatePassed: true,
    dataVersion: 'danang-v1',
    totalCost: 100000,
    totalKm: 2,
    totalMinutes: 90,
  );

  @override
  Future<PlanningResult> requestPlan(Map<String, dynamic> request) async {
    planningKeys.add(request['_idempotency_key'] as String);
    overrides.add(
      Map<String, dynamic>.from(request['constraint_overrides'] as Map),
    );
    return const PlanningResult(items: [alternative], requestId: 'request-010');
  }

  @override
  Future<AcceptanceSummary> accept(String itineraryId, String key) async {
    acceptanceKeys.add(key);
    return AcceptanceSummary(
      id: 'acceptance-010',
      versionId: 'version-010',
      selectedAt: DateTime.utc(2026, 11, 10),
    );
  }

  @override
  Future<List<ItineraryVersionSummary>> history(String tripId) async => [
    ItineraryVersionSummary(
      id: 'version-010',
      ordinal: 1,
      active: true,
      dataVersion: 'danang-v1',
      createdAt: DateTime.utc(2026, 11, 10),
      reason: 'accept',
    ),
  ];

  @override
  Future<void> activateVersion(String versionId, String key) async {}

  @override
  Future<SavedItineraryPlan> readVersion(String versionId) async => savedPlan!;

  @override
  Future<PlanningResult> replan(
    String tripId,
    String sourceVersionId,
    String key, {
    List<String> completedActivityIds = const [],
    List<String> skippedActivityIds = const [],
  }) async {
    replanKeys.add(key);
    return const PlanningResult(
      items: [alternative],
      requestId: 'replan-request-010',
    );
  }

  @override
  Future<void> logExpense(String tripId, Map<String, dynamic> expense) async {}
}

class _HotelManagement extends FakeManagementRepository
    implements LiveManagementRepository {
  _HotelManagement() : super(seeded: true);

  static const hotel = PoiItem(
    id: 'hotel-1',
    name: 'Khách sạn Biển',
    type: 'Khách sạn',
    latitude: 16.05,
    longitude: 108.22,
    verified: false,
  );

  @override
  String? activeTripId = 'trip-1';
  @override
  Future<void> setActiveTrip(Trip? trip) async => activeTripId = trip?.id;
  @override
  Future<List<PoiItem>> searchPois(String query, {String? category}) async {
    expect(category, 'lodging');
    return query == 'Biển' ? [hotel] : [];
  }

  @override
  Future<PoiItem> getPoiDetails(String id) async {
    expect(id, hotel.id);
    return hotel;
  }
}

class _PromptPlanningRepository extends _LifecyclePlanningRepository
    implements AiPlanningRepository {
  final prompts = <String>[];

  @override
  Future<Map<String, dynamic>> aiReadiness() async => {
    'available': true,
    'capabilities': {'interpretation': true},
  };

  @override
  Future<AiInterpretationProposal> interpret(String tripId, String text) async {
    prompts.add(text);
    if (prompts.length == 1) {
      throw const ApiException('LLM_UNAVAILABLE', 'AI tạm thời chưa phản hồi.');
    }
    return const AiInterpretationProposal(
      id: 'prompt-proposal',
      fields: {'traveler_count': 2, 'indicative_budget': 1500000},
      hardConstraints: {},
      softPreferences: {},
      assumptions: [],
      unresolved: [],
      provider: 'fixture',
      model: 'fixture',
      externalProcessing: false,
    );
  }

  @override
  Future<PlanExplanation> explain(String alternativeId) =>
      throw UnimplementedError();
}

class _SavedMapManagement extends _HotelManagement
    implements DraftRouteRepository {
  List<String>? routedIds;

  @override
  Future<PoiItem> getPoiDetails(String id) async =>
      id == _HotelManagement.hotel.id
      ? _HotelManagement.hotel
      : const PoiItem(
          id: 'bridge',
          name: 'Cầu Rồng',
          type: 'landmark',
          latitude: 16.0611,
          longitude: 108.2274,
          verified: true,
        );

  @override
  Future<RoutePreviewData> previewDraftRoute(
    String tripId,
    List<String> poiIds,
  ) {
    routedIds = poiIds;
    return previewRoute(tripId, const []);
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
    'the focused prompt closes safely and opens review after a retry',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final planning = _PromptPlanningRepository();
      final state = AppState(_HotelManagement(), planningRepository: planning);
      addTearDown(state.dispose);
      await state.initialize();
      await tester.pumpWidget(MaterialApp(home: PlanningScreen(state: state)));
      await tester.pumpAndSettle();

      Future<void> submitPrompt() async {
        final open = find.byKey(const Key('request-ai-interpretation'));
        await tester.ensureVisible(open);
        await tester.tap(open);
        await tester.pumpAndSettle();
        final dialog = find.byType(AlertDialog);
        final confirm = find.descendant(
          of: dialog,
          matching: find.byType(FilledButton),
        );
        expect(confirm, findsOneWidget);
        expect(
          find.descendant(of: dialog, matching: find.byType(TextButton)),
          findsNothing,
        );
        expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
        await tester.enterText(
          find.byKey(const Key('planning-ai-prompt')),
          '  Hai người đi với tổng ngân sách một triệu rưỡi.  ',
        );
        await tester.pump();
        await tester.tap(confirm);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }

      await submitPrompt();
      expect(find.text('AI tạm thời chưa phản hồi.'), findsOneWidget);
      expect(find.byType(PlanningRequestReview), findsNothing);
      await submitPrompt();
      expect(find.byType(PlanningRequestReview), findsOneWidget);
      expect(
        planning.prompts,
        List.filled(2, 'Hai người đi với tổng ngân sách một triệu rưỡi.'),
      );
      expect(planning.planningKeys, isEmpty);

      final save = find.byKey(const Key('save-planning-review'));
      await tester.scrollUntilVisible(
        save,
        180,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(save.hitTestable());
      await tester.pumpAndSettle();
      expect(planning.overrides.single['traveler_count'], 2);
      expect(planning.overrides.single['indicative_budget'], 1500000);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('reopens a saved planner route even when no manual stops exist', (
    tester,
  ) async {
    final management = _SavedMapManagement();
    final planning = _LifecyclePlanningRepository()
      ..savedPlan = SavedItineraryPlan.fromJson({
        'version_id': 'version-010',
        'trip_id': 'trip-1',
        'request': {
          'trip': {'start_date': '2026-10-17'},
        },
        'plan': {
          'activities': [
            {'poi_id': 'bridge', 'start': '08:00', 'end': '09:00'},
            {'poi_id': 'hotel-1', 'start': '09:30', 'end': '10:30'},
          ],
        },
      });
    final state = AppState(management, planningRepository: planning);
    addTearDown(state.dispose);
    await state.initialize();
    expect(state.itinerary?.activities, isEmpty);
    expect(state.savedPlanForSelectedDay?.versionId, 'version-010');
    state.selectTripDate(DateTime(2026, 10, 18));
    expect(state.savedPlanForSelectedDay, isNull);
    state.selectTripDate(DateTime(2026, 10, 17));
    await tester.pumpWidget(MaterialApp(home: MainShell(state: state)));
    await tester.tap(find.byKey(const Key('map-tab')));
    await tester.pumpAndSettle();

    final canvas = tester.widget<MapCanvas>(find.byType(MapCanvas));
    expect(canvas.stops.map((stop) => stop.title), [
      'Cầu Rồng',
      'Khách sạn Biển',
    ]);
    expect(management.routedIds, ['bridge', 'hotel-1']);
    expect(canvas.routePreview?.quality, 'road_route');
    expect(find.byKey(const Key('locate-user-button')), findsOneWidget);
  });

  testWidgets(
    'selecting, reopening and clearing a hotel changes each planning request',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final management = _HotelManagement();
      await management.updateTrip('trip-1', {
        'preference_overrides': {'outdoor_bias': -1.0},
      });
      final planning = _LifecyclePlanningRepository();
      final state = AppState(management, planningRepository: planning);
      await state.initialize();

      Future<void> tapKey(String key) async {
        final finder = find.byKey(Key(key));
        await tester.ensureVisible(finder);
        await tester.pumpAndSettle();
        await tester.tap(finder.hitTestable());
        await tester.pumpAndSettle();
      }

      await tester.pumpWidget(MaterialApp(home: PlanningScreen(state: state)));
      await tester.pumpAndSettle();
      await tapKey('planning-hotel-button');
      await tester.enterText(
        find.byKey(const Key('hotel-search-field')),
        'Biển',
      );
      await tapKey('hotel-search-button');
      await tapKey('hotel-result-hotel-1');
      expect(find.text('Khách sạn Biển'), findsOneWidget);
      expect(management.trips.single.outdoorBias, -1.0);
      await tapKey('request-plan-button');
      await tapKey('request-plan-button');
      expect(planning.overrides, [
        {'base_poi_id': 'hotel-1'},
        {'base_poi_id': 'hotel-1'},
      ]);
      state.aiProposal = AiInterpretationProposal.fromJson({
        'proposal_id': 'proposal-1',
        'fields': {'traveler_count': 3},
      });
      await state.confirmAiProposalAndPlan();
      await tester.pumpAndSettle();
      expect(planning.overrides.last, {
        'traveler_count': 3,
        'base_poi_id': 'hotel-1',
      });

      await tester.pumpWidget(const SizedBox.shrink());
      state.dispose();
      final reopened = AppState(management, planningRepository: planning);
      await reopened.initialize();
      await tester.pumpWidget(
        MaterialApp(home: PlanningScreen(state: reopened)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Khách sạn Biển'), findsOneWidget);
      await tapKey('planning-clear-hotel-button');
      await tapKey('request-plan-button');
      expect(planning.overrides.last, isEmpty);
      expect(management.trips.single.outdoorBias, -1.0);
      await tester.pumpWidget(const SizedBox.shrink());
      reopened.dispose();
    },
  );

  testWidgets('shows the phone frame and honest demo planning state', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      DavelTraceApp(repository: FakeManagementRepository(seeded: true)),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('desktop-phone-frame')), findsOneWidget);
    await tester.tap(find.byKey(const Key('open-trip-trip-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-planning-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('source-status-banner')), findsOneWidget);
    expect(find.byKey(const Key('request-plan-button')), findsNothing);
    expect(
      find.byKey(const Key('preview-plan-seeded-balanced')),
      findsOneWidget,
    );
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('map-tab')), findsOneWidget);
    expect(find.byKey(const Key('expenses-tab')), findsOneWidget);
    expect(find.byKey(const Key('profile-tab')), findsOneWidget);
  });

  test('retries reuse stable lifecycle keys', () async {
    final planning = _LifecyclePlanningRepository();
    final state = AppState(
      FakeManagementRepository(seeded: true),
      planningRepository: planning,
    );
    await state.initialize();

    await state.requestPlan();
    await state.requestPlan();
    await state.acceptAlternative(_LifecyclePlanningRepository.alternative);
    await state.acceptAlternative(_LifecyclePlanningRepository.alternative);
    await state.requestReplan();
    await state.requestReplan();

    expect(planning.planningKeys.toSet(), hasLength(1));
    expect(planning.acceptanceKeys.toSet(), hasLength(1));
    expect(planning.replanKeys.toSet(), hasLength(1));
    expect(state.currentPlanningRequestId, 'replan-request-010');
  });

  testWidgets('demo route preview fits a 390x844 viewport', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      DavelTraceApp(repository: FakeManagementRepository(seeded: true)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('open-trip-trip-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-planning-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('request-plan-button')), findsNothing);
    expect(
      find.byKey(const Key('preview-plan-seeded-balanced')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}
