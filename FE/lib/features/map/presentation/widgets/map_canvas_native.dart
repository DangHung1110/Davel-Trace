import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

import '../../../../theme/app_theme.dart';
import '../../../itinerary/domain/demo_trip.dart';

class MapCanvas extends StatefulWidget {
  const MapCanvas({
    super.key,
    required this.stops,
    required this.routeRevision,
    required this.playRequest,
    required this.pauseRequest,
    required this.locateRequest,
  });

  final List<TripStop> stops;
  final int routeRevision;
  final int playRequest;
  final int pauseRequest;
  final int locateRequest;

  @override
  State<MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<MapCanvas> {
  final _controller = MapController();
  List<LatLng> _route = const [];
  LatLng? _carPosition;
  LatLng? _userPosition;
  Timer? _animation;
  bool _routeFromOsrm = false;
  int _animationIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => _loadRoute(autoPlay: widget.routeRevision > 0),
    );
  }

  @override
  void didUpdateWidget(covariant MapCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.routeRevision != widget.routeRevision ||
        oldWidget.stops != widget.stops) {
      _loadRoute(autoPlay: true);
    } else if (oldWidget.playRequest != widget.playRequest) {
      _playRoute();
    } else if (oldWidget.pauseRequest != widget.pauseRequest) {
      _pauseRoute();
    }
    if (oldWidget.locateRequest != widget.locateRequest) _locateUser();
  }

  Future<void> _loadRoute({required bool autoPlay}) async {
    _pauseRoute();
    final fallback = widget.stops
        .map((stop) => LatLng(stop.latitude, stop.longitude))
        .toList();
    var route = fallback;
    var fromOsrm = false;

    if (widget.stops.length > 1) {
      final coordinates = widget.stops
          .map((stop) => '${stop.longitude},${stop.latitude}')
          .join(';');
      final uri = Uri.parse(
        'https://router.project-osrm.org/route/v1/driving/$coordinates'
        '?overview=full&geometries=geojson&steps=false',
      );
      final client = HttpClient()
        ..connectionTimeout = const Duration(seconds: 8);
      try {
        final request = await client.getUrl(uri);
        request.headers.set(HttpHeaders.userAgentHeader, 'DavelTrace/1.0');
        final response = await request.close().timeout(
          const Duration(seconds: 10),
        );
        final body = await response.transform(utf8.decoder).join();
        if (response.statusCode == HttpStatus.ok) {
          final payload = jsonDecode(body) as Map<String, dynamic>;
          final routes = payload['routes'] as List<dynamic>?;
          if (payload['code'] == 'Ok' && routes != null && routes.isNotEmpty) {
            final geometry = routes.first['geometry'] as Map<String, dynamic>;
            final points = geometry['coordinates'] as List<dynamic>;
            route = points.map((point) {
              final pair = point as List<dynamic>;
              return LatLng(
                (pair[1] as num).toDouble(),
                (pair[0] as num).toDouble(),
              );
            }).toList();
            fromOsrm = route.length > 1;
          }
        }
      } catch (_) {
        route = fallback;
      } finally {
        client.close(force: true);
      }
    }

    if (!mounted) return;
    setState(() {
      _route = route;
      _routeFromOsrm = fromOsrm;
      _carPosition = route.isEmpty ? null : route.first;
      _animationIndex = 0;
    });
    if (route.isNotEmpty) _controller.move(route.first, 13.2);
    if (autoPlay) _playRoute();
  }

  Future<void> _locateUser() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return;
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return;
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );
      if (!mounted) return;
      final point = LatLng(position.latitude, position.longitude);
      setState(() => _userPosition = point);
      _controller.move(point, 15.5);
    } catch (_) {
      // The map remains usable if location permission or GPS is unavailable.
    }
  }

  void _playRoute() {
    if (_route.length < 2) return;
    _animation?.cancel();
    if (_animationIndex >= _route.length - 1) _animationIndex = 0;
    final step = (_route.length / 420).ceil().clamp(1, _route.length).toInt();
    _animation = Timer.periodic(const Duration(milliseconds: 60), (timer) {
      if (!mounted || _route.isEmpty) {
        timer.cancel();
        return;
      }
      _animationIndex = (_animationIndex + step)
          .clamp(0, _route.length - 1)
          .toInt();
      setState(() => _carPosition = _route[_animationIndex]);
      if (_animationIndex >= _route.length - 1) timer.cancel();
    });
  }

  void _pauseRoute() => _animation?.cancel();

  @override
  void dispose() {
    _animation?.cancel();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fallback = widget.stops
        .map((stop) => LatLng(stop.latitude, stop.longitude))
        .toList();
    final displayRoute = _route.isEmpty ? fallback : _route;
    return Stack(
      children: [
        FlutterMap(
          mapController: _controller,
          options: MapOptions(
            initialCenter: fallback.isEmpty
                ? const LatLng(16.0784, 108.2420)
                : fallback.first,
            initialZoom: 13.2,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.daveltrace.davel_trace',
              maxNativeZoom: 19,
            ),
            PolylineLayer(
              polylines: [
                Polyline(
                  points: displayRoute,
                  color: AppColors.primary,
                  strokeWidth: 5,
                ),
              ],
            ),
            MarkerLayer(
              markers: [
                ...widget.stops.map(
                  (stop) => Marker(
                    point: LatLng(stop.latitude, stop.longitude),
                    width: 42,
                    height: 42,
                    child: _PlaceMarker(icon: stop.icon, color: stop.color),
                  ),
                ),
                if (_userPosition != null)
                  Marker(
                    point: _userPosition!,
                    width: 28,
                    height: 28,
                    child: const _UserMarker(),
                  ),
                if (_carPosition != null)
                  Marker(
                    point: _carPosition!,
                    width: 34,
                    height: 34,
                    child: const _CarMarker(),
                  ),
              ],
            ),
            const RichAttributionWidget(
              showFlutterMapAttribution: false,
              attributions: [
                TextSourceAttribution('OpenStreetMap contributors'),
              ],
            ),
          ],
        ),
        Positioned(
          left: 10,
          top: 10,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
            decoration: BoxDecoration(
              color: AppColors.surface.withValues(alpha: .92),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              _routeFromOsrm ? 'OSRM · tuyến thực' : 'Đường nối dự phòng',
              style: const TextStyle(
                color: AppColors.primary,
                fontSize: 9,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _PlaceMarker extends StatelessWidget {
  const _PlaceMarker({required this.icon, required this.color});
  final IconData icon;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: color,
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white, width: 3),
      boxShadow: const [
        BoxShadow(
          color: Color(0x33173C35),
          blurRadius: 8,
          offset: Offset(0, 3),
        ),
      ],
    ),
    child: Icon(icon, color: Colors.white, size: 19),
  );
}

class _UserMarker extends StatelessWidget {
  const _UserMarker();
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: const Color(0xFF2979FF),
      shape: BoxShape.circle,
      border: Border.all(color: Colors.white, width: 4),
      boxShadow: const [BoxShadow(color: Color(0x552979FF), blurRadius: 10)],
    ),
  );
}

class _CarMarker extends StatelessWidget {
  const _CarMarker();
  @override
  Widget build(BuildContext context) => Container(
    decoration: const BoxDecoration(
      color: AppColors.accent,
      shape: BoxShape.circle,
      boxShadow: [BoxShadow(color: Color(0x441E2926), blurRadius: 8)],
    ),
    child: const Icon(
      Icons.directions_car_filled_rounded,
      color: Colors.white,
      size: 18,
    ),
  );
}
