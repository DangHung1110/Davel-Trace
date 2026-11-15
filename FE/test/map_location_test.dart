import 'package:davel_trace/features/map/map.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('390x844 map keeps stops and reports location outcomes', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    const outcomes = {
      MapLocationStatus.permissionDenied: 'Chưa được cấp quyền vị trí.',
      MapLocationStatus.serviceDisabled: 'Dịch vụ vị trí đang tắt.',
      MapLocationStatus.unsupported: 'Thiết bị không hỗ trợ định vị.',
      MapLocationStatus.unavailable: 'Không lấy được vị trí.',
    };

    for (final outcome in outcomes.entries) {
      await tester.pumpWidget(
        MaterialApp(
          home: MapScreen(
            stops: const [],
            planRevision: 0,
            onOpenItinerary: () {},
            locationProvider: _FixedLocationProvider(
              MapLocationResult(outcome.key),
            ),
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('locate-user-button')));
      await tester.pumpAndSettle();
      expect(find.text(outcome.value), findsOneWidget);
    }

    await tester.pumpWidget(
      MaterialApp(
        home: MapScreen(
          stops: const [],
          planRevision: 0,
          onOpenItinerary: () {},
          locationProvider: _FixedLocationProvider(
            const MapLocationResult(
              MapLocationStatus.located,
              location: MapLocation(latitude: 16.05, longitude: 108.2),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.byKey(const Key('locate-user-button')));
    await tester.pumpAndSettle();
    expect(find.text('Không lấy được vị trí.'), findsNothing);
    expect(find.byKey(const Key('locate-user-button')), findsOneWidget);
  });
}

class _FixedLocationProvider implements MapLocationProvider {
  const _FixedLocationProvider(this.result);

  final MapLocationResult result;

  @override
  Future<MapLocationResult> currentLocation() async => result;
}
