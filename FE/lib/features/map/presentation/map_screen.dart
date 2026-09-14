import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../../theme/app_theme.dart';

class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  static const _route = [
    LatLng(16.1066, 108.2770),
    LatLng(16.0958, 108.2492),
    LatLng(16.0836, 108.2340),
    LatLng(16.0680, 108.2441),
  ];

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        FlutterMap(
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
            MarkerLayer(
              markers: const [
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
              attributions: [
                TextSourceAttribution('OpenStreetMap contributors'),
              ],
            ),
          ],
        ),
        Positioned(
          top: 16,
          left: 16,
          right: 16,
          child: Material(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            elevation: 3,
            shadowColor: const Color(0x2212213A),
            child: const TextField(
              decoration: InputDecoration(
                hintText: 'Tìm địa điểm ở Đà Nẵng',
                prefixIcon: Icon(Icons.search),
                suffixIcon: Icon(Icons.tune),
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
              ),
            ),
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 18,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x2412213A),
                  blurRadius: 24,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: const Row(
              children: [
                CircleAvatar(
                  backgroundColor: AppColors.sky,
                  child: Icon(Icons.route, color: AppColors.blue),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'Hành trình hôm nay',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      SizedBox(height: 3),
                      Text('3 điểm · 24 km · khoảng 7 giờ'),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right),
              ],
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
