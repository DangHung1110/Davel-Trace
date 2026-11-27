import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../management/data/management_repository.dart';
import '../../management/domain/models.dart';
import '../../planning/domain/models.dart';
import 'map_screen.dart';
import 'map_stop.dart';

class PlannedRouteMap extends StatefulWidget {
  const PlannedRouteMap({
    super.key,
    required this.plan,
    required this.tripId,
    required this.repository,
    required this.title,
    required this.onBack,
    this.resolvePlace,
    this.isDraft = false,
    this.isActive = true,
  });

  final PlanAlternative plan;
  final String tripId;
  final ManagementRepository repository;
  final String title;
  final VoidCallback onBack;
  final Future<PoiItem?> Function(String)? resolvePlace;
  final bool isDraft;
  final bool isActive;

  @override
  State<PlannedRouteMap> createState() => _PlannedRouteMapState();
}

class _PlannedRouteMapState extends State<PlannedRouteMap> {
  late final _preview = _loadPreview();

  Future<PoiItem?> _place(String id) async {
    try {
      final resolve = widget.resolvePlace;
      return await (resolve != null
          ? resolve(id)
          : widget.repository.getPoiDetails(id));
    } catch (_) {
      return null;
    }
  }

  Future<(List<MapStop>, RoutePreviewData)> _loadPreview() async {
    final activities = widget.plan.activities;
    final resolved = await Future.wait(
      activities.indexed.map((entry) async {
        final (index, activity) = entry;
        final id = activity['poi_id']?.toString();
        if (id == null || id.isEmpty) return null;
        final place = await _place(id);
        if (place == null) return null;
        final start = (activity['start'] ?? activity['start_time'] ?? '')
            .toString();
        final end = (activity['end'] ?? activity['end_time'] ?? '').toString();
        final category = place.type;
        final stop = MapStop(
          id: 'draft-$index',
          title: (activity['name'] ?? activity['title'] ?? place.name)
              .toString(),
          subtitle: place.type,
          time: start,
          durationMinutes: math.max(0, _minutes(end) - _minutes(start)),
          latitude: place.latitude,
          longitude: place.longitude,
          icon: categoryIcon(category),
          color: categoryColor(category),
        );
        return stop.hasLocation ? (id, stop) : null;
      }),
    );
    final places = resolved.whereType<(String, MapStop)>().toList();
    final stops = places.map((entry) => entry.$2).toList();
    final skipped = activities.length - stops.length;
    final repository = widget.repository;
    RoutePreviewData? route;
    if (stops.length >= 2 && repository is DraftRouteRepository) {
      try {
        route = await (repository as DraftRouteRepository).previewDraftRoute(
          widget.tripId,
          places.map((entry) => entry.$1).toList(),
        );
      } catch (_) {
        // Catalog coordinates are enough for an explicitly approximate line.
      }
    }
    return (
      stops,
      RoutePreviewData(
        source: route?.source ?? 'none',
        quality: route?.quality ?? 'unavailable',
        isRealRoute: route?.isRealRoute ?? false,
        distanceM: route?.distanceM ?? 0,
        durationS: route?.durationS ?? 0,
        geometry: route?.geometry ?? const [],
        warning: [
          ?route?.warning,
          if (skipped > 0) 'Thiếu vị trí của $skipped điểm dừng.',
          if (stops.length == 1) 'Cần ít nhất hai điểm có vị trí để vẽ tuyến.',
        ].join(' '),
      ),
    );
  }

  int _minutes(String time) {
    final parts = time.split(':');
    if (parts.length < 2) return 0;
    return (int.tryParse(parts[0]) ?? 0) * 60 + (int.tryParse(parts[1]) ?? 0);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: FutureBuilder(
        future: _preview,
        builder: (context, snapshot) {
          if (snapshot.data case final preview?) {
            return MapScreen(
              stops: preview.$1,
              planRevision: 0,
              tripTitle: widget.title,
              routePreview: preview.$2,
              isDraft: widget.isDraft,
              isActive: widget.isActive,
              onOpenItinerary: widget.onBack,
            );
          }
          return Scaffold(
            appBar: AppBar(
              title: Text(widget.title),
              leading: BackButton(onPressed: widget.onBack),
            ),
            body: Center(
              child: snapshot.hasError
                  ? const Text('Chưa tải được lộ trình.')
                  : const CircularProgressIndicator(
                      semanticsLabel: 'Đang tải lộ trình',
                    ),
            ),
          );
        },
      ),
    ),
  );
}
