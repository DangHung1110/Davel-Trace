import 'dart:convert';

import '../../../management/domain/models.dart';
import '../../domain/location_state.dart';
import '../map_stop.dart';

/// Keeps the frame alive while route data and GPS fixes change independently.
class MapBridgeController {
  MapBridgeController(this.send);
  final void Function(Map<String, dynamic>) send;
  bool ready = false;
  String? _tripSignature;
  Map<String, dynamic>? _trip;
  Map<String, dynamic> _location = {'type': 'clearUserLocation'};

  void updateTrip(List<MapStop> stops, int revision, RoutePreviewData? route) {
    final trip = <String, dynamic>{
      'type': 'setRoute',
      'stops': stops
          .map(
            (stop) => {
              'id': stop.id,
              'title': stop.title,
              'subtitle': stop.subtitle,
              'latitude': stop.latitude,
              'longitude': stop.longitude,
            },
          )
          .toList(),
      'route': route?.toJson(),
      'autoPlay': false,
    };
    final signature = jsonEncode([revision, trip]);
    if (signature == _tripSignature) return;
    _tripSignature = signature;
    _trip = trip;
    if (ready) send(trip);
  }

  void updateLocation(
    MapLocation? location, {
    required bool follow,
    bool recenter = false,
  }) {
    _location = location == null
        ? {'type': 'clearUserLocation'}
        : {
            'type': 'setUserLocation',
            'latitude': location.latitude,
            'longitude': location.longitude,
            'follow': follow,
            'recenter': recenter,
          };
    if (ready) {
      send(_location);
      _location = {..._location, 'recenter': false};
    }
  }

  void markReady() {
    ready = true;
    if (_trip case final trip?) send(trip);
    send(_location);
    _location = {..._location, 'recenter': false};
  }

  void command(String type) {
    if (ready) send({'type': type});
  }
}
