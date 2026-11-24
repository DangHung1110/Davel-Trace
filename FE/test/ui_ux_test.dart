import 'package:davel_trace/app.dart';
import 'package:davel_trace/core/auth/auth_session_store.dart';
import 'package:davel_trace/features/auth/application/auth_controller.dart';
import 'package:davel_trace/features/itinerary/presentation/itinerary_screen.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/features/management/data/management_repository.dart';
import 'package:davel_trace/features/management/data/demo_management_repository.dart';
import 'package:davel_trace/features/itinerary/presentation/planning_request_review.dart';
import 'package:davel_trace/features/map/presentation/widgets/map_canvas.dart';
import 'package:davel_trace/shared/widgets/mobile_frame.dart';
import 'package:davel_trace/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'auth_controller_test.dart';
import 'support/fake_management_repository.dart';

class _LiveManagement extends FakeManagementRepository
    implements LiveManagementRepository {
  _LiveManagement() : super(seeded: true);
  @override
  String? activeTripId = 'trip-1';
  @override
  Future<void> setActiveTrip(Trip? trip) async => activeTripId = trip?.id;
}

Future<void> _tap(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  if (target.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      target,
      220,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

void _viewport(WidgetTester tester, Size size, {double scale = 1}) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetViewInsets);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

Future<void> _capture(WidgetTester tester, String name) async {
  if (const bool.fromEnvironment('CAPTURE_UI')) {
    await expectLater(
      find.byKey(const Key('desktop-phone-frame')),
      matchesGoldenFile('../build/ui-review/$name.png'),
    );
  }
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  setUpAll(() async {
    final font = FontLoader('Be Vietnam Pro')
      ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-Regular.ttf'))
      ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-SemiBold.ttf'));
    await font.load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    await (FontLoader('Roboto')
          ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-Regular.ttf')))
        .load();
  });

  testWidgets(
    'account uses login identity and visibly signs out without a travel profile',
    (tester) async {
      _viewport(tester, const Size(390, 844));
      final authRepo = FakeAuthRepository();
      final store = MemoryAuthSessionStore();
      final auth = AuthController(repository: authRepo, sessionStore: store);
      await auth.initialize();
      await auth.login('demo@example.com', 'test');
      await tester.pumpWidget(
        DavelTraceApp(
          repository: FakeManagementRepository(),
          authController: auth,
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('profile-name-field')), findsNothing);
      await _tap(tester, 'profile-tab');
      expect(find.text('demo@example.com'), findsOneWidget);
      expect(find.byKey(const Key('profile-name-field')), findsNothing);
      await _capture(tester, 'account-390');
      await _tap(tester, 'account-logout-button');
      expect(auth.status, AuthStatus.signedOut);
      expect(authRepo.access, isNull);
      expect(await store.readRefreshToken(), isNull);
      expect(find.text('Đăng nhập'), findsOneWidget);
      await _capture(tester, 'sign-in-390');
    },
  );

  testWidgets('sign out from security closes protected subpages', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final auth = AuthController(
      repository: FakeAuthRepository(),
      sessionStore: MemoryAuthSessionStore(),
    );
    await auth.initialize();
    await auth.login('demo@example.com', 'test');
    await tester.pumpWidget(
      DavelTraceApp(
        repository: FakeManagementRepository(seeded: true),
        authController: auth,
      ),
    );
    await tester.pumpAndSettle();
    await _tap(tester, 'profile-tab');
    await _tap(tester, 'account-security-button');
    await _tap(tester, 'security-logout-button');
    expect(find.text('Đăng nhập'), findsOneWidget);
    expect(find.byKey(const Key('security-logout-button')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'trip list opens the daily itinerary before separate planning workspace',
    (tester) async {
      _viewport(tester, const Size(390, 844));
      final repo = FakeManagementRepository(seeded: true);
      await tester.pumpWidget(DavelTraceApp(repository: repo));
      await tester.pumpAndSettle();
      await _capture(tester, 'trips-390');
      expect(find.byKey(const Key('request-plan-button')), findsNothing);
      await _tap(tester, 'open-trip-trip-1');
      expect(find.text('Lịch trình trong ngày'), findsOneWidget);
      expect(find.byKey(const Key('request-plan-button')), findsNothing);
      await _capture(tester, 'itinerary-390');
      await _tap(tester, 'open-planning-button');
      expect(find.byKey(const Key('request-plan-button')), findsOneWidget);
      expect(find.text('28°C'), findsNothing);
      await _capture(tester, 'planning-390');
      await tester.pageBack();
      await tester.pumpAndSettle();
      await _tap(tester, 'back-to-trips');
      expect(find.text('Chuyến đi của bạn'), findsOneWidget);
    },
  );

  testWidgets('previews ordered demo stops before saving any itinerary', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final repo = DemoManagementRepository()..activities.clear();
    await tester.pumpWidget(DavelTraceApp(repository: repo));
    await tester.pumpAndSettle();
    await _tap(tester, 'open-trip-trip-demo');
    await _tap(tester, 'open-trip-map-button');
    expect(find.byKey(const Key('empty-map-message')), findsOneWidget);
    await _tap(tester, 'empty-map-open-itinerary');
    await _tap(tester, 'open-planning-button');
    await _tap(tester, 'preview-plan-seeded-balanced');

    final map = tester.widget<MapCanvas>(find.byType(MapCanvas));
    expect(map.stops.map((stop) => stop.title), [
      'Bán đảo Sơn Trà',
      'Ăn trưa với mì Quảng',
      'Bảo tàng Điêu khắc Chăm',
      'Biển Mỹ Khê',
    ]);
    expect(map.routePreview?.quality, 'interpolated');
    expect(map.routePreview?.geometry, hasLength(4));
    expect(find.byKey(const Key('locate-user-button')), findsNothing);
    expect(repo.activities, isEmpty);
    await _tap(tester, 'open-map-replan-button');
    expect(
      find.byKey(const Key('preview-plan-seeded-balanced')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  for (final width in [320.0, 390.0]) {
    testWidgets('core journeys fit ${width.toInt()}px with enlarged text', (
      tester,
    ) async {
      _viewport(tester, Size(width, 640), scale: 2);
      await tester.pumpWidget(
        DavelTraceApp(repository: FakeManagementRepository(seeded: true)),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await _tap(tester, 'expenses-tab');
      await _capture(tester, 'expenses-${width.toInt()}-large');
      expect(tester.takeException(), isNull);
      await tester.drag(find.byType(ListView).first, const Offset(0, -450));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await _tap(tester, 'itinerary-tab');
      await _tap(tester, 'open-trip-trip-1');
      expect(tester.takeException(), isNull);
      await _tap(tester, 'open-planning-button');
      await tester.drag(find.byType(ListView).last, const Offset(0, -550));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.pageBack();
      await tester.pumpAndSettle();
      await _tap(tester, 'profile-tab');
      await _capture(tester, 'account-${width.toInt()}-large');
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets(
    'editor preserves multi-day trip hours and transport in submitted payload',
    (tester) async {
      _viewport(tester, const Size(1440, 900));
      Map<String, dynamic>? saved;
      final trip = Trip(
        id: 'existing',
        profileId: 'p',
        title: 'Chuyến 7 ngày',
        startDate: DateTime(2026, 11, 16),
        endDate: DateTime(2026, 11, 22),
        dayStart: '08:30:00',
        dayEnd: '18:45:00',
        travelers: 4,
        budgetVnd: 9876543,
        transport: 'mixed',
        status: 'available',
        version: 3,
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          builder: (_, child) => MobileFrame(child: child!),
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () async {
                  saved = await Navigator.of(context)
                      .push<Map<String, dynamic>>(
                        MaterialPageRoute(
                          builder: (_) => TripEditor(trip: trip),
                        ),
                      );
                },
                child: const Text('Edit'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Edit'));
      await tester.pumpAndSettle();
      expect(tester.getSize(find.byType(TripEditor)).width, 390);
      await _capture(tester, 'trip-editor-desktop');
      await _tap(tester, 'save-trip-button');
      expect(saved, containsPair('day_start', '08:30:00'));
      expect(saved, containsPair('day_end', '18:45:00'));
      expect(saved, containsPair('end_date', '2026-11-22'));
      expect(saved, containsPair('transport', 'mixed'));
      expect(saved, containsPair('budget_vnd', 9876543));
      expect(saved, containsPair('travelers', 4));
    },
  );

  testWidgets(
    'expense persistence label follows management storage before planning runs',
    (tester) async {
      _viewport(tester, const Size(390, 844));
      await tester.pumpWidget(DavelTraceApp(repository: _LiveManagement()));
      await tester.pumpAndSettle();
      await _tap(tester, 'expenses-tab');
      expect(find.text('Chi tiêu đã được lưu vào tài khoản.'), findsOneWidget);
      expect(
        find.text('Chế độ demo: khoản chi chỉ lưu trong phiên trên thiết bị.'),
        findsNothing,
      );
      await _capture(tester, 'expenses-390');
    },
  );

  testWidgets(
    'AI confirmation shows place names, keeps IDs in data and validates fields',
    (tester) async {
      _viewport(tester, const Size(390, 844));
      Map<String, dynamic>? saved;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                child: const Text('Review'),
                onPressed: () async => saved = await Navigator.of(context)
                    .push<Map<String, dynamic>>(
                      MaterialPageRoute(
                        builder: (_) => PlanningRequestReview(
                          values: const {
                            'traveler_count': 2,
                            'must_visit': ['poi-1'],
                            'day_start': '08:00',
                            'day_end': '19:00',
                          },
                          repository: FakeManagementRepository(seeded: true),
                        ),
                      ),
                    ),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('review-traveler_count')),
        '21',
      );
      await _tap(tester, 'save-planning-review');
      expect(find.text('Nhập từ 1 đến 20 người'), findsOneWidget);
      expect(find.text('poi-1'), findsNothing);
      await tester.ensureVisible(
        find.byKey(const Key('review-traveler_count')),
      );
      await tester.enterText(
        find.byKey(const Key('review-traveler_count')),
        '4',
      );
      await _tap(tester, 'save-planning-review');
      expect(saved, containsPair('must_visit', ['poi-1']));
      expect(saved, containsPair('traveler_count', 4));
    },
  );

  testWidgets(
    'trip space preference preserves the saved hotel and other overrides',
    (tester) async {
      _viewport(tester, const Size(390, 844));
      final trip = Trip.fromJson({
        'id': 'trip-test',
        'title': 'Đà Nẵng',
        'start_date': '2026-11-28',
        'end_date': '2026-11-29',
        'day_start': '07:00:00',
        'day_end': '20:00:00',
        'travelers': 2,
        'version': 1,
        'preference_overrides': {
          'base_poi_id': 'hotel-1',
          'pace': 3,
          'outdoor_bias': 1.0,
        },
      });
      Map<String, dynamic>? submitted;
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () async {
                  submitted = await Navigator.of(context)
                      .push<Map<String, dynamic>>(
                        MaterialPageRoute(
                          builder: (_) => TripEditor(trip: trip),
                        ),
                      );
                },
                child: const Text('Mở form'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Mở form'));
      await tester.pumpAndSettle();
      await _tap(tester, 'trip-outdoor-bias-field');
      expect(find.text('Ưu tiên ngoài trời'), findsWidgets);
      await tester.tap(find.text('Ưu tiên trong nhà').last);
      await tester.pumpAndSettle();
      await _tap(tester, 'save-trip-button');
      expect(submitted?['preference_overrides'], {
        'base_poi_id': 'hotel-1',
        'pace': 3,
        'outdoor_bias': -1.0,
      });
    },
  );

  testWidgets(
    'trip editor validates backend limits and stays usable with the keyboard',
    (tester) async {
      _viewport(tester, const Size(320, 640));
      await tester.pumpWidget(
        MaterialApp(theme: AppTheme.light, home: const TripEditor()),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('trip-travelers-field')));
      await tester.enterText(
        find.byKey(const Key('trip-travelers-field')),
        '21',
      );
      await _tap(tester, 'save-trip-button');
      expect(find.text('Nhập từ 1 đến 20 người'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('trip-travelers-field')),
        '2',
      );
      await tester.ensureVisible(find.byKey(const Key('trip-day-end-field')));
      await tester.enterText(
        find.byKey(const Key('trip-day-end-field')),
        '06:00',
      );
      await _tap(tester, 'save-trip-button');
      expect(find.text('Giờ kết thúc phải sau giờ bắt đầu'), findsOneWidget);
      tester.view.viewInsets = const FakeViewPadding(bottom: 280);
      await tester.pumpAndSettle();
      expect(
        tester.getBottomRight(find.byKey(const Key('save-trip-button'))).dy,
        lessThanOrEqualTo(360),
      );
      expect(tester.takeException(), isNull);
    },
  );
}
