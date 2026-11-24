import 'package:davel_trace/features/map/domain/location_state.dart';
import 'package:davel_trace/features/map/presentation/map_stop.dart';
import 'package:davel_trace/features/map/presentation/widgets/map_bridge_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

List<MapStop> _stops([String title = 'Cầu Rồng']) => [
  MapStop(
    id: 'bridge',
    title: title,
    subtitle: '',
    time: '09:00',
    durationMinutes: 30,
    latitude: 16.06,
    longitude: 108.22,
    icon: Icons.place,
    color: Colors.teal,
  ),
];

void main() {
  test(
    'fresh equivalent stop lists and GPS updates do not reset the route',
    () {
      final sent = <Map<String, dynamic>>[];
      final bridge = MapBridgeController(sent.add);
      bridge.updateTrip(_stops(), 1, null);
      bridge.markReady();
      bridge.command('playRoute');
      for (var i = 0; i < 100; i++) {
        bridge.updateTrip(_stops(), 1, null);
        bridge.updateLocation(
          MapLocation(latitude: 16.06 + i / 100000, longitude: 108.22),
          follow: true,
        );
      }
      expect(
        sent.where((message) => message['type'] == 'setRoute'),
        hasLength(1),
      );
      expect(
        sent.where((message) => message['type'] == 'setUserLocation'),
        hasLength(100),
      );
      expect(
        sent.where((message) => message['type'] == 'playRoute'),
        hasLength(1),
      );
      expect(sent.where((message) => message['type'] == 'resetRoute'), isEmpty);
      bridge.updateTrip(_stops('Chợ Hàn'), 2, null);
      expect(
        sent.where((message) => message['type'] == 'setRoute'),
        hasLength(2),
      );
    },
  );

  test('latest trip and fix wait for readiness and survive explicit retry', () {
    final sent = <Map<String, dynamic>>[];
    final bridge = MapBridgeController(sent.add);
    bridge.updateTrip(_stops(), 1, null);
    bridge.updateLocation(
      const MapLocation(latitude: 16.05, longitude: 108.2),
      follow: true,
      recenter: true,
    );
    bridge.updateLocation(
      const MapLocation(latitude: 16.06, longitude: 108.21),
      follow: true,
    );
    expect(sent, isEmpty);
    bridge.markReady();
    expect(sent.last['latitude'], 16.06);
    bridge.ready = false;
    bridge.updateTrip([], 2, null);
    bridge.updateLocation(null, follow: false);
    bridge.markReady();
    expect(sent[sent.length - 2]['stops'], isEmpty);
    expect(sent.last['type'], 'clearUserLocation');
  });
}
