import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/features/map/map.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('road-route source and play pause resume reset controls work', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: MapScreen(
          stops: const [
            MapStop(
              id: 'a',
              title: 'Cầu Rồng',
              subtitle: 'Tham quan',
              time: '09:00',
              durationMinutes: 30,
              latitude: 16.0611,
              longitude: 108.2274,
              icon: Icons.place_outlined,
              color: Colors.teal,
            ),
            MapStop(
              id: 'b',
              title: 'Bảo tàng Chăm',
              subtitle: 'Tham quan',
              time: '10:00',
              durationMinutes: 45,
              latitude: 16.0602,
              longitude: 108.2235,
              icon: Icons.place_outlined,
              color: Colors.teal,
            ),
          ],
          planRevision: 0,
          routePreview: const RoutePreviewData(
            source: 'osrm',
            isRealRoute: true,
            distanceM: 1200,
            durationS: 300,
            quality: 'road_route',
            geometry: [
              [108.2274, 16.0611],
              [108.2250, 16.0610],
              [108.2235, 16.0602],
            ],
          ),
          onOpenItinerary: () {},
        ),
      ),
    );
    await tester.pump();
    expect(find.text('OSRM 1.2 km'), findsOneWidget);

    await tester.tap(find.byKey(const Key('play-car-button')));
    await tester.pump(const Duration(milliseconds: 80));
    expect(find.text('Đang dẫn đường'), findsOneWidget);

    await tester.tap(find.byTooltip('Tạm dừng'));
    await tester.pump();
    expect(find.text('Bắt đầu đi'), findsOneWidget);

    await tester.tap(find.byKey(const Key('play-car-button')));
    await tester.pump(const Duration(milliseconds: 80));
    expect(find.text('Đang dẫn đường'), findsOneWidget);

    await tester.tap(find.byTooltip('Đặt lại mô phỏng'));
    await tester.pump();
    expect(find.text('Bắt đầu đi'), findsOneWidget);
  });
}
