import 'package:flutter/material.dart';

import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';

class MapStop {
  const MapStop({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.time,
    required this.durationMinutes,
    required this.latitude,
    required this.longitude,
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
  final IconData icon;
  final Color color;

  factory MapStop.fromActivity(ActivityItem activity) => MapStop(
    id: activity.id,
    title: activity.title,
    subtitle: activity.notes.isEmpty
        ? categoryLabel(activity.category)
        : activity.notes,
    time:
        '${activity.startAt.hour.toString().padLeft(2, '0')}:${activity.startAt.minute.toString().padLeft(2, '0')}',
    durationMinutes: activity.endAt.difference(activity.startAt).inMinutes,
    latitude: activity.latitude,
    longitude: activity.longitude,
    icon: categoryIcon(activity.category),
    color: categoryColor(activity.category),
  );
}

IconData categoryIcon(String category) => switch (category) {
  'food' => Icons.restaurant_outlined,
  'transport' => Icons.directions_outlined,
  'ticket' => Icons.local_activity_outlined,
  _ => Icons.place_outlined,
};

Color categoryColor(String category) => switch (category) {
  'food' => AppColors.warning,
  'transport' => AppColors.primary,
  'ticket' => AppColors.coral,
  _ => AppColors.success,
};

String categoryLabel(String category) => switch (category) {
  'food' => 'Ăn uống',
  'transport' => 'Di chuyển',
  'ticket' => 'Vé tham quan',
  _ => 'Tham quan',
};
