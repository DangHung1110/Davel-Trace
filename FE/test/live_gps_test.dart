import 'dart:async';
import 'dart:io';

import 'package:davel_trace/features/map/map.dart';
import 'package:davel_trace/features/map/presentation/widgets/map_canvas.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:davel_trace/theme/app_theme.dart';

class _StreamingLocation implements MapLocationProvider {
  _StreamingLocation() {
    fixes = StreamController<MapLocationResult>.broadcast(
      onListen: () => listeners++,
      onCancel: () => listeners--,
    );
  }
  late final StreamController<MapLocationResult> fixes;
  int listeners = 0;
  int watches = 0;
  @override
  Future<MapLocationResult> currentLocation() async =>
      throw StateError('Use the live stream');
  @override
  Stream<MapLocationResult> watchLocation() {
    watches++;
    return fixes.stream;
  }

  void emit(double latitude, {int second = 0}) => fixes.add(
    MapLocationResult(
      MapLocationStatus.located,
      location: MapLocation(
        latitude: latitude,
        longitude: 108.2,
        accuracyMeters: 8,
        timestamp: DateTime.utc(2026, 11, 15).add(Duration(seconds: second)),
      ),
    ),
  );
}

Widget _screen(MapLocationProvider provider, {bool active = true}) =>
    MaterialApp(
      home: MapScreen(
        stops: const [],
        planRevision: 0,
        onOpenItinerary: () {},
        locationProvider: provider,
        isActive: active,
      ),
    );

MapCanvas _canvas(WidgetTester tester) =>
    tester.widget<MapCanvas>(find.byType(MapCanvas));

Future<void> _pumpGPS(WidgetTester tester) async {
  // Cancellation can finish in a platform/event-loop turn without scheduling a frame.
  await tester.runAsync(() => Future<void>.delayed(Duration.zero));
  await tester.pumpAndSettle();
}

Future<void> _start(WidgetTester tester, _StreamingLocation provider) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
  await tester.pumpWidget(_screen(provider));
  await _pumpGPS(tester);
  expect(provider.watches, 0);
  await tester.tap(find.byKey(const Key('locate-user-button')));
  await _pumpGPS(tester);
  await _pumpGPS(tester);
  expect(provider.listeners, 1);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('map retry and coverage notices do not restart the GPS watch', (
    tester,
  ) async {
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    await _start(tester, provider);
    provider.emit(16.06);
    await _pumpGPS(tester);
    _canvas(tester).onMapError!('Không tải được bản đồ');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('retry-map-button')), findsOneWidget);
    await tester.tap(find.byKey(const Key('retry-map-button')));
    await tester.pumpAndSettle();
    expect(_canvas(tester).reloadRequest, 1);
    expect(provider.watches, 1);
    expect(_canvas(tester).userLocation?.latitude, 16.06);
    _canvas(tester).onCoverageChanged!(false);
    await tester.pumpAndSettle();
    expect(find.textContaining('ngoài vùng bản đồ Đà Nẵng'), findsOneWidget);
    _canvas(tester).onCoverageChanged!(true);
    await tester.pumpAndSettle();
    expect(find.textContaining('ngoài vùng bản đồ Đà Nẵng'), findsNothing);
    expect(provider.watches, 1);
    expect(tester.takeException(), isNull);
  });
  const cacheChannel = MethodChannel('plugins.flutter.io/path_provider');
  setUpAll(() async {
    await (FontLoader('Be Vietnam Pro')
          ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-Regular.ttf'))
          ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-SemiBold.ttf')))
        .load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          cacheChannel,
          (call) async => call.method == 'getApplicationCacheDirectory'
              ? Directory.current.uri
                    .resolve('build/live_gps_tile_cache')
                    .toFilePath()
              : null,
        );
  });
  tearDownAll(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(cacheChannel, null);
  });
  testWidgets('empty itinerary explains markers and keeps live GPS available', (
    tester,
  ) async {
    var openedItinerary = 0;
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: MapScreen(
          stops: const [],
          planRevision: 0,
          locationProvider: provider,
          onOpenItinerary: () => openedItinerary++,
        ),
      ),
    );
    await _pumpGPS(tester);
    expect(find.byKey(const Key('empty-map-message')), findsOneWidget);
    expect(find.byKey(const Key('play-car-button')), findsNothing);
    expect(find.text('Bật GPS'), findsOneWidget);
    final recenter = find.descendant(
      of: find.byKey(const Key('follow-user-button')),
      matching: find.byType(IconButton),
    );
    expect(tester.widget<IconButton>(recenter).onPressed, isNull);
    await tester.tap(find.byKey(const Key('locate-user-button')));
    await _pumpGPS(tester);
    provider.emit(16.05);
    await _pumpGPS(tester);
    expect(find.text('Tắt GPS'), findsOneWidget);
    expect(_canvas(tester).userLocation?.latitude, 16.05);
    expect(tester.widget<IconButton>(recenter).onPressed, isNotNull);
    provider.emit(16.051, second: 1);
    await _pumpGPS(tester);
    expect(_canvas(tester).userLocation?.latitude, 16.051);
    await tester.ensureVisible(
      find.byKey(const Key('empty-map-open-itinerary')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('empty-map-open-itinerary')));
    await tester.pump();
    expect(openedItinerary, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('empty map controls fit a narrow viewport with large text', (
    tester,
  ) async {
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: MapScreen(
          stops: const [],
          planRevision: 0,
          locationProvider: provider,
          onOpenItinerary: () {},
        ),
      ),
    );
    await _pumpGPS(tester);
    await tester.tap(find.byKey(const Key('locate-user-button')));
    await _pumpGPS(tester);
    expect(provider.watches, 1);
    final button = find.byKey(const Key('empty-map-open-itinerary'));
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    expect(button.hitTestable(), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('panning before first fix keeps the camera free until recenter', (
    tester,
  ) async {
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    await _start(tester, provider);
    final map = tester.widget<FlutterMap>(find.byType(FlutterMap));
    final center = map.mapController!.camera.center;
    map.options.onPositionChanged!(map.mapController!.camera, true);
    await _pumpGPS(tester);
    provider.emit(16.05);
    await _pumpGPS(tester);
    expect(_canvas(tester).userLocation!.latitude, 16.05);
    expect(_canvas(tester).followUser, isFalse);
    expect(map.mapController!.camera.center, center);
    await tester.tap(find.byKey(const Key('follow-user-button')));
    await _pumpGPS(tester);
    expect(map.mapController!.camera.center.latitude, closeTo(16.05, 0.000001));
  });
  testWidgets(
    'movement updates marker and camera, pan releases follow, recenter restores it',
    (tester) async {
      final provider = _StreamingLocation();
      addTearDown(provider.fixes.close);
      addTearDown(
        () => tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        ),
      );
      await _start(tester, provider);
      provider.emit(16.05);
      await _pumpGPS(tester);
      expect(_canvas(tester).userLocation!.latitude, 16.05);
      expect(find.byKey(const Key('user-location-marker')), findsOneWidget);
      expect(_canvas(tester).followUser, isTrue);
      provider.emit(16.0502, second: 1);
      await _pumpGPS(tester);
      expect(_canvas(tester).userLocation!.latitude, 16.0502);
      var map = tester.widget<FlutterMap>(find.byType(FlutterMap));
      expect(
        map.mapController!.camera.center.latitude,
        closeTo(16.0502, 0.000001),
      );
      map.options.onPositionChanged!(map.mapController!.camera, true);
      await _pumpGPS(tester);
      expect(_canvas(tester).followUser, isFalse);
      final camera = map.mapController!.camera.center;
      provider.emit(16.0503, second: 2);
      await _pumpGPS(tester);
      expect(_canvas(tester).userLocation!.latitude, 16.0503);
      expect(map.mapController!.camera.center, camera);
      await tester.tap(find.byKey(const Key('follow-user-button')));
      await _pumpGPS(tester);
      expect(_canvas(tester).followUser, isTrue);
      expect(
        map.mapController!.camera.center.latitude,
        closeTo(16.0503, 0.000001),
      );
      expect(find.text('GPS trực tiếp · ±8 m'), findsOneWidget);
      await tester.tap(find.byKey(const Key('locate-user-button')));
      await _pumpGPS(tester);
      expect(provider.listeners, 0);
      expect(_canvas(tester).userLocation, isNull);
      expect(find.byKey(const Key('user-location-marker')), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('invalid and older fixes cannot rewind the displayed position', (
    tester,
  ) async {
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    await _start(tester, provider);
    provider.emit(16.05, second: 2);
    await _pumpGPS(tester);
    provider.emit(16.04, second: 1);
    provider.emit(double.nan, second: 3);
    provider.emit(91, second: 4);
    await _pumpGPS(tester);
    expect(_canvas(tester).userLocation!.latitude, 16.05);
    provider.fixes.addError(StateError('Location provider disconnected'));
    await _pumpGPS(tester);
    expect(_canvas(tester).userLocation, isNull);
    expect(provider.listeners, 0);
    expect(find.text('Không lấy được vị trí.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'background and hidden tab release GPS and resume only a requested session',
    (tester) async {
      final provider = _StreamingLocation();
      addTearDown(provider.fixes.close);
      await _start(tester, provider);
      provider.emit(16.05);
      await _pumpGPS(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await _pumpGPS(tester);
      expect(provider.listeners, 0);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await _pumpGPS(tester);
      await _pumpGPS(tester);
      expect(provider.listeners, 1);
      expect(_canvas(tester).userLocation, isNull);
      expect(provider.watches, 2);
      await tester.pumpWidget(_screen(provider, active: false));
      await _pumpGPS(tester);
      expect(provider.listeners, 0);
      await tester.pumpWidget(_screen(provider));
      await _pumpGPS(tester);
      expect(provider.listeners, 1);
      await tester.tap(find.byKey(const Key('locate-user-button')));
      await _pumpGPS(tester);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await _pumpGPS(tester);
      expect(provider.listeners, 0);
      await tester.pumpWidget(const SizedBox.shrink());
      await _pumpGPS(tester);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'provider replacement and dispose cancel old streams and ignore late fixes',
    (tester) async {
      final first = _StreamingLocation(), second = _StreamingLocation();
      addTearDown(first.fixes.close);
      addTearDown(second.fixes.close);
      await _start(tester, first);
      await tester.pumpWidget(_screen(second));
      await _pumpGPS(tester);
      expect(first.listeners, 0);
      expect(second.listeners, 1);
      first.emit(17);
      second.emit(16.05);
      await _pumpGPS(tester);
      expect(_canvas(tester).userLocation!.latitude, 16.05);
      await tester.pumpWidget(const SizedBox.shrink());
      await _pumpGPS(tester);
      expect(second.listeners, 0);
      second.emit(16.1, second: 1);
      await _pumpGPS(tester);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('quick start and stop does not leave an active watch', (
    tester,
  ) async {
    final provider = _StreamingLocation();
    addTearDown(provider.fixes.close);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(_screen(provider));
    await tester.tap(find.byKey(const Key('locate-user-button')));
    await tester.tap(find.byKey(const Key('locate-user-button')));
    await _pumpGPS(tester);
    expect(provider.listeners, 0);
    expect(_canvas(tester).userLocation, isNull);
  });

  group('geolocator watch adapter', () {
    late GeolocatorPlatform original;
    late _FakeGeolocator platform;
    setUp(() {
      original = GeolocatorPlatform.instance;
      platform = _FakeGeolocator();
      GeolocatorPlatform.instance = platform;
    });
    tearDown(() async {
      GeolocatorPlatform.instance = original;
      await platform.positions.close();
    });
    test(
      'streams device fixes with navigation accuracy and cancels the OS stream',
      () async {
        final results = <MapLocationResult>[];
        final subscription = const GeolocatorMapLocationProvider()
            .watchLocation()
            .listen(results.add);
        await Future<void>.delayed(Duration.zero);
        expect(platform.settings!.accuracy, LocationAccuracy.bestForNavigation);
        expect(platform.settings!.timeLimit, isNull);
        expect(platform.settings!.distanceFilter, 2);
        platform.positions.add(
          Position(
            latitude: 16.05,
            longitude: 108.2,
            timestamp: DateTime.now(),
            accuracy: 5,
            altitude: 0,
            altitudeAccuracy: 0,
            heading: 0,
            headingAccuracy: 0,
            speed: 0,
            speedAccuracy: 0,
          ),
        );
        await Future<void>.delayed(Duration.zero);
        expect(results.single.location!.latitude, 16.05);
        expect(results.single.location!.accuracyMeters, 5);
        await subscription.cancel();
        expect(platform.positions.hasListener, isFalse);
      },
    );
    test(
      'denied permission and disabled service do not open a position stream',
      () async {
        platform.permission = LocationPermission.deniedForever;
        expect(
          (await const GeolocatorMapLocationProvider().watchLocation().toList())
              .single
              .status,
          MapLocationStatus.permissionDenied,
        );
        expect(platform.settings, isNull);
        platform.enabled = false;
        expect(
          (await const GeolocatorMapLocationProvider().watchLocation().toList())
              .single
              .status,
          MapLocationStatus.serviceDisabled,
        );
      },
    );
  });
}

class _FakeGeolocator extends GeolocatorPlatform {
  bool enabled = true;
  LocationPermission permission = LocationPermission.whileInUse;
  LocationSettings? settings;
  final positions = StreamController<Position>.broadcast();
  @override
  Future<bool> isLocationServiceEnabled() async => enabled;
  @override
  Future<LocationPermission> checkPermission() async => permission;
  @override
  Future<LocationPermission> requestPermission() async => permission;
  @override
  Stream<Position> getPositionStream({LocationSettings? locationSettings}) {
    settings = locationSettings;
    return positions.stream;
  }
}
