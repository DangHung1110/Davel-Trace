import 'package:geolocator/geolocator.dart';
import 'package:flutter/foundation.dart';

class MapLocation {
  const MapLocation({
    required this.latitude,
    required this.longitude,
    this.accuracyMeters,
    this.timestamp,
  });

  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final DateTime? timestamp;

  bool get isValid =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude.abs() <= 90 &&
      longitude.abs() <= 180;
}

enum MapLocationStatus {
  located,
  permissionDenied,
  serviceDisabled,
  unsupported,
  unavailable,
}

class MapLocationResult {
  const MapLocationResult(this.status, {this.location});

  final MapLocationStatus status;
  final MapLocation? location;
}

abstract interface class MapLocationProvider {
  Future<MapLocationResult> currentLocation();
  Stream<MapLocationResult> watchLocation();
}

class GeolocatorMapLocationProvider implements MapLocationProvider {
  const GeolocatorMapLocationProvider();

  Future<MapLocationStatus?> _availability() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return MapLocationStatus.serviceDisabled;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return MapLocationStatus.permissionDenied;
    }
    return null;
  }

  MapLocationResult _position(Position position) => MapLocationResult(
    MapLocationStatus.located,
    location: MapLocation(
      latitude: position.latitude,
      longitude: position.longitude,
      accuracyMeters: position.accuracy,
      timestamp: position.timestamp,
    ),
  );

  @override
  Stream<MapLocationResult> watchLocation() async* {
    try {
      final failure = await _availability();
      if (failure != null) {
        yield MapLocationResult(failure);
        return;
      }
      final LocationSettings settings = kIsWeb
          ? WebSettings(
              accuracy: LocationAccuracy.bestForNavigation,
              distanceFilter: 2,
              maximumAge: Duration.zero,
            )
          : defaultTargetPlatform == TargetPlatform.android
          ? AndroidSettings(
              accuracy: LocationAccuracy.bestForNavigation,
              distanceFilter: 2,
              intervalDuration: const Duration(seconds: 1),
            )
          : const LocationSettings(
              accuracy: LocationAccuracy.bestForNavigation,
              distanceFilter: 2,
            );
      // No stream inactivity timeout: a stationary traveler is a valid state.
      yield* Geolocator.getPositionStream(locationSettings: settings)
          .map(_position);
    } on UnsupportedError {
      yield const MapLocationResult(MapLocationStatus.unsupported);
    } on PermissionDeniedException {
      yield const MapLocationResult(MapLocationStatus.permissionDenied);
    } on LocationServiceDisabledException {
      yield const MapLocationResult(MapLocationStatus.serviceDisabled);
    } catch (_) {
      yield const MapLocationResult(MapLocationStatus.unavailable);
    }
  }

  @override
  Future<MapLocationResult> currentLocation() async {
    try {
      final failure = await _availability();
      if (failure != null) return MapLocationResult(failure);
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 12),
        ),
      );
      return _position(position);
    } on UnsupportedError {
      return const MapLocationResult(MapLocationStatus.unsupported);
    } on PermissionDeniedException {
      return const MapLocationResult(MapLocationStatus.permissionDenied);
    } on LocationServiceDisabledException {
      return const MapLocationResult(MapLocationStatus.serviceDisabled);
    } catch (_) {
      return const MapLocationResult(MapLocationStatus.unavailable);
    }
  }
}

String mapLocationMessage(MapLocationStatus status) => switch (status) {
  MapLocationStatus.located => '',
  MapLocationStatus.permissionDenied => 'Chưa được cấp quyền vị trí.',
  MapLocationStatus.serviceDisabled => 'Dịch vụ vị trí đang tắt.',
  MapLocationStatus.unsupported => 'Thiết bị không hỗ trợ định vị.',
  MapLocationStatus.unavailable => 'Không lấy được vị trí.',
};
