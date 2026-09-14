import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';
import 'widgets/map_canvas.dart';

class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const Positioned.fill(child: MapCanvas()),
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
