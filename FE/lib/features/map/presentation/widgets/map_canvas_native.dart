import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../../../theme/app_theme.dart';

class MapCanvas extends StatelessWidget {
  const MapCanvas({super.key});

  static const _route = [
    LatLng(16.1066, 108.2770),
    LatLng(16.0958, 108.2492),
    LatLng(16.0836, 108.2340),
    LatLng(16.0680, 108.2441),
  ];

  @override
  Widget build(BuildContext context) {
    return FlutterMap(
      options: const MapOptions(
        initialCenter: LatLng(16.0784, 108.2420),
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
            Polyline(points: _route, color: AppColors.blue, strokeWidth: 5),
          ],
        ),
        const MarkerLayer(
          markers: [
            Marker(
              point: LatLng(16.1066, 108.2770),
              width: 46,
              height: 46,
              child: _PlaceMarker(
                icon: Icons.landscape,
                color: AppColors.success,
              ),
            ),
            Marker(
              point: LatLng(16.0836, 108.2340),
              width: 46,
              height: 46,
              child: _PlaceMarker(
                icon: Icons.restaurant,
                color: AppColors.amber,
              ),
            ),
            Marker(
              point: LatLng(16.0680, 108.2441),
              width: 46,
              height: 46,
              child: _PlaceMarker(
                icon: Icons.beach_access,
                color: AppColors.blue,
              ),
            ),
          ],
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
