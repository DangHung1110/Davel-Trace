import 'package:geolocator/geolocator.dart';

class MapLocation {
  const MapLocation({required this.latitude, required this.longitude});

  final double latitude;
  final double longitude;
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
}

class GeolocatorMapLocationProvider implements MapLocationProvider {
  const GeolocatorMapLocationProvider();

  @override
  Future<MapLocationResult> currentLocation() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        return const MapLocationResult(MapLocationStatus.serviceDisabled);
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return const MapLocationResult(MapLocationStatus.permissionDenied);
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 12),
        ),
      );
      return MapLocationResult(
        MapLocationStatus.located,
        location: MapLocation(
          latitude: position.latitude,
          longitude: position.longitude,
        ),
      );
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
