import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';

class TripStop {
  const TripStop({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.time,
    required this.durationMinutes,
    required this.latitude,
    required this.longitude,
    required this.interest,
    required this.icon,
    required this.color,
  });

  final String id;
  final String title;
  final String subtitle;
  final String time;
  final int durationMinutes;
  final double latitude;
  final double longitude;
  final String interest;
  final IconData icon;
  final Color color;

  String get durationLabel {
    final hours = durationMinutes ~/ 60;
    final minutes = durationMinutes % 60;
    if (hours == 0) return '$minutes phút';
    if (minutes == 0) return '$hours giờ';
    return '$hours giờ $minutes';
  }
}

abstract final class DemoTripData {
  static const defaultOrigin = TripStop(
    id: 'dragon-bridge',
    title: 'Cầu Rồng',
    subtitle: 'Điểm xuất phát',
    time: '07:00',
    durationMinutes: 0,
    latitude: 16.0611,
    longitude: 108.2274,
    interest: 'Xuất phát',
    icon: Icons.location_on_outlined,
    color: AppColors.coral,
  );

  static const origins = [
    defaultOrigin,
    TripStop(
      id: 'danang-airport',
      title: 'Sân bay Đà Nẵng',
      subtitle: 'Điểm xuất phát',
      time: '07:00',
      durationMinutes: 0,
      latitude: 16.0439,
      longitude: 108.2022,
      interest: 'Xuất phát',
      icon: Icons.flight_land_outlined,
      color: AppColors.coral,
    ),
    TripStop(
      id: 'han-market',
      title: 'Chợ Hàn',
      subtitle: 'Điểm xuất phát',
      time: '07:00',
      durationMinutes: 0,
      latitude: 16.0680,
      longitude: 108.2244,
      interest: 'Xuất phát',
      icon: Icons.storefront_outlined,
      color: AppColors.coral,
    ),
  ];

  static const activities = [
    TripStop(
      id: 'son-tra',
      title: 'Bán đảo Sơn Trà',
      subtitle: 'Leo núi nhẹ · Ngắm cảnh',
      time: '07:30',
      durationMinutes: 180,
      latitude: 16.1066,
      longitude: 108.2770,
      interest: 'Thiên nhiên',
      icon: Icons.landscape_outlined,
      color: AppColors.success,
    ),
    TripStop(
      id: 'mi-quang-ba-mua',
      title: 'Mì Quảng Bà Mua',
      subtitle: 'Ăn trưa · 4.5 ★',
      time: '11:30',
      durationMinutes: 60,
      latitude: 16.0667,
      longitude: 108.2159,
      interest: 'Ẩm thực',
      icon: Icons.restaurant_outlined,
      color: AppColors.amber,
    ),
    TripStop(
      id: 'cham-museum',
      title: 'Bảo tàng Điêu khắc Chăm',
      subtitle: 'Văn hóa · Lịch sử Đà Nẵng',
      time: '13:15',
      durationMinutes: 90,
      latitude: 16.0603,
      longitude: 108.2230,
      interest: 'Văn hóa',
      icon: Icons.museum_outlined,
      color: AppColors.coral,
    ),
    TripStop(
      id: 'my-khe',
      title: 'Bãi biển Mỹ Khê',
      subtitle: 'Tắm biển · Ngắm hoàng hôn',
      time: '15:30',
      durationMinutes: 150,
      latitude: 16.0610,
      longitude: 108.2470,
      interest: 'Biển',
      icon: Icons.beach_access_outlined,
      color: AppColors.blue,
    ),
  ];

  static const defaultRoute = [defaultOrigin, ...activities];
}
