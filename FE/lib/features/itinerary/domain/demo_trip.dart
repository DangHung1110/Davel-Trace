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
    this.imageUrl = '',
    this.rating,
    this.tags = const [],
    this.priceLabel,
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
  final String imageUrl;
  final double? rating;
  final List<String> tags;
  final String? priceLabel;

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
      imageUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCCldAsl2eKVEJLKV1fQlWeSivHVL6egstGRP_KO1LfuoioOqTeLiQGvqBY83gyLy6X3jcTdNZeW4nstDEiuHkpIhIeGjOI_at-d4AsMzIwQ-76gczTVbNebIIki7Y6KDCs2UhJsZdF5YPHIbFr7093ZqaAhI0vpQjVe9eh9fqGk_lwG0hmf_ysQc0G8ct44FCJh0UOucUzKwvVgZfIBijzS2XcUQq71Y1jk2GKBSpKdM9oYg17M3_n',
      rating: 4.8,
      tags: ['Trekking', 'Check-in'],
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
      imageUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuB6PGW-zGFlwZZsMh0ctGycIEh_mZbfJNki6-qUj5_HVxtm3IqYiPkWXgpLolKpuI3JqpxdJkgcwWcFJnh8LNm40_WQ-2OUd3Ws7sNqm5Y2qwPx1HcVF6n8L5RRYmuAaxf2J0aUiQEGse9QaHm0b-iKupBq-KIQBEGE90nIUM8K9jFBU6zFw8vcsHefaX_7GoEehdLBi9NFtSsRPL3COnVkgwY3y7Wz0ajTj_UtTB93MFRsHL7nYSyM',
      rating: 4.5,
      tags: ['Ẩm thực xứ', 'Ăn sáng'],
      priceLabel: '45k - 65k',
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
      imageUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCXnvDeTWAK8ZNecGqHmrK5xfAIdYKUyBt2N8irdR9AfYbFgdDOVU9yvQ-tA30hW0WAaFjxjyr564RgTH3iyzAQSTGE4DrYvM-Uy5srYR2MazKi6GMqm1nosw0V9jFaH8riVAjg9o61zTsxBSkFmhCpDJBA3l0q-vpJrBE6QZ8slUtCeCzyWpleQRKjYKPZhVsKTi9CWBop8tRNUdLRnX0fH7eK94rW4hqA8n2ertg7lzDVXj6GdHHm',
      rating: 4.6,
      tags: ['Điểm tham quan', 'Vé 60k'],
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
      imageUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuB9va6fg7FE3PmxCjH5r_xZ2T4vlz__AP7FByqs5aucPGT_5amq5KuQI1gQ4WTj6HSyESWzhFesboa9s_KWn6bHBBaUj_Ni-cbFdFEtKgECweyuHETQFZ-VA8CFz6RBaHgryJE1Kwm8SOeOxugLEKTUY_uyfg414g7VvISUgiiaqQYPwifa_cSix__FFmJ0IHGK6-WxBsc6Vg8i9UlQV-GBMikCxpxS_SU0Lwjj5Pcu8xS1iXoRCkg6',
      rating: 4.7,
      tags: ['Biển', 'Miễn phí'],
    ),
  ];

  static const defaultRoute = [defaultOrigin, ...activities];
}
