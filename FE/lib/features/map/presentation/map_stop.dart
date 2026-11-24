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

  bool get hasLocation =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude.abs() <= 90 &&
      longitude.abs() <= 180 &&
      (latitude != 0 || longitude != 0);

  @override
  bool operator ==(Object other) =>
      other is MapStop &&
      id == other.id &&
      title == other.title &&
      subtitle == other.subtitle &&
      time == other.time &&
      durationMinutes == other.durationMinutes &&
      latitude == other.latitude &&
      longitude == other.longitude &&
      icon == other.icon &&
      color == other.color;

  @override
  int get hashCode => Object.hash(
    id,
    title,
    subtitle,
    time,
    durationMinutes,
    latitude,
    longitude,
    icon,
    color,
  );

  factory MapStop.fromActivity(
    ActivityItem activity, {
    PoiItem? place,
  }) => MapStop(
    id: activity.id,
    title: activity.title,
    subtitle: [
      activity.notes.isEmpty
          ? categoryLabel(activity.category)
          : activity.notes,
      if (activity.poiId == null)
        'Hoạt động riêng'
      else if (place == null)
        'POI chưa khả dụng · trạng thái chưa xác minh'
      else if (place.verified)
        'POI đã xác minh'
      else
        'POI chưa xác minh',
    ].join(' · '),
    time:
        '${activity.startAt.hour.toString().padLeft(2, '0')}:${activity.startAt.minute.toString().padLeft(2, '0')}',
    durationMinutes: activity.endAt.difference(activity.startAt).inMinutes,
    latitude: place?.latitude ?? activity.latitude,
    longitude: place?.longitude ?? activity.longitude,
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
