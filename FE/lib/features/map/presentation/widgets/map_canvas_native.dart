import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../../itinerary/domain/demo_trip.dart';
import '../../../../theme/app_theme.dart';

class MapCanvas extends StatelessWidget {
  const MapCanvas({
    super.key,
    required this.stops,
    required this.routeRevision,
    required this.playRequest,
  });

  final List<TripStop> stops;
  final int routeRevision;
  final int playRequest;

  @override
  Widget build(BuildContext context) {
    final points = stops
        .map((stop) => LatLng(stop.latitude, stop.longitude))
        .toList();
    return FlutterMap(
      options: MapOptions(
        initialCenter: points.isEmpty
            ? const LatLng(16.0784, 108.2420)
            : points.first,
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
            Polyline(points: points, color: AppColors.blue, strokeWidth: 5),
          ],
        ),
        MarkerLayer(
          markers: stops
              .map(
                (stop) => Marker(
                  point: LatLng(stop.latitude, stop.longitude),
                  width: 46,
                  height: 46,
                  child: _PlaceMarker(icon: stop.icon, color: stop.color),
                ),
              )
              .toList(),
        ),
        const RichAttributionWidget(
          showFlutterMapAttribution: false,
          attributions: [TextSourceAttribution('OpenStreetMap contributors')],
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
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 3),
        boxShadow: const [
          BoxShadow(
            color: Color(0x3312213A),
            blurRadius: 8,
            offset: Offset(0, 3),
          ),
        ],
      ),
      child: Icon(icon, color: Colors.white, size: 21),
    );
  }
}
