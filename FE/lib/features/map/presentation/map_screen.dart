import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';

import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../domain/location_state.dart';
import 'map_stop.dart';
import 'widgets/map_canvas.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({
    super.key,
    required this.stops,
    required this.planRevision,
    required this.onOpenItinerary,
    this.tripTitle,
    this.routePreview,
    this.locationProvider = const GeolocatorMapLocationProvider(),
  });

  final List<MapStop> stops;
  final int planRevision;
  final VoidCallback onOpenItinerary;
  final String? tripTitle;
  final RoutePreviewData? routePreview;
  final MapLocationProvider locationProvider;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  int _playRequest = 0;
  int _pauseRequest = 0;
  int _resetRequest = 0;
  int _locateRequest = 0;
  bool _isPlaying = false;
  MapLocation? _userLocation;
  String? _locationMessage;

  void _play() => setState(() {
    _playRequest++;
    _isPlaying = true;
  });

  void _pause() => setState(() {
    _pauseRequest++;
    _isPlaying = false;
  });

  Future<void> _locate() async {
    setState(() => _locationMessage = 'Đang xác định vị trí…');
    final result = await widget.locationProvider.currentLocation();
    if (!mounted) return;
    if (result.status != MapLocationStatus.located || result.location == null) {
      setState(() => _locationMessage = mapLocationMessage(result.status));
      return;
    }
    setState(() {
      _userLocation = result.location;
      _locationMessage = null;
      _locateRequest++;
    });
  }

  void _reset() => setState(() {
    _isPlaying = false;
    _resetRequest++;
  });

  @override
  void didUpdateWidget(covariant MapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
  }

  @override
  Widget build(BuildContext context) {
    final nextStop = widget.stops.isNotEmpty ? widget.stops.first : null;
    return Stack(
      children: [
        Positioned.fill(
          child: MapCanvas(
            stops: widget.stops,
            routeRevision: widget.planRevision,
            playRequest: _playRequest,
            pauseRequest: _pauseRequest,
            resetRequest: _resetRequest,
            locateRequest: _locateRequest,
            userLocation: _userLocation,
            routePreview: widget.routePreview,
          ),
        ),
        Positioned(
          top: 12,
          left: 12,
          right: 12,
          child: PointerInterceptor(
            child: Material(
              color: AppColors.surface.withValues(alpha: .96),
              elevation: 3,
              shadowColor: const Color(0x22006A6A),
              borderRadius: BorderRadius.circular(99),
              child: InkWell(
                key: const Key('open-map-replan-button'),
                borderRadius: BorderRadius.circular(99),
                onTap: widget.onOpenItinerary,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 7,
                  ),
                  child: Row(
                    children: [
                      const CircleAvatar(
                        radius: 15,
                        backgroundColor: AppColors.surfaceLow,
                        child: Icon(
                          Icons.arrow_back_rounded,
                          color: AppColors.primary,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Icon(Icons.search_rounded, size: 18),
                      const SizedBox(width: 7),
                      Expanded(
                        child: Text(
                          widget.tripTitle ?? 'Sơn Trà & Mỹ Khê',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.ink,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const Icon(
                        Icons.mic_none_rounded,
                        color: AppColors.primary,
                        size: 19,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        Positioned(
          top: 66,
          left: 12,
          right: 12,
          child: PointerInterceptor(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  const _MapPill(
                    icon: Icons.wb_sunny_outlined,
                    label: '28°C · Gió biển',
                  ),
                  const SizedBox(width: 6),
                  _MapPill(
                    icon: switch (widget.routePreview?.quality) {
                      'road_route' => Icons.route_rounded,
                      'matrix_estimate' => Icons.straighten_rounded,
                      'interpolated' => Icons.linear_scale_rounded,
                      _ => Icons.offline_bolt_outlined,
                    },
                    label: switch (widget.routePreview?.quality) {
                      'road_route' =>
                        'OSRM ${(widget.routePreview!.distanceM / 1000).toStringAsFixed(1)} km',
                      'matrix_estimate' => 'Ước tính ma trận',
                      'interpolated' => 'Nội suy minh họa',
                      _ => 'Chưa có tuyến',
                    },
                  ),
                  const SizedBox(width: 6),
                  const _MapPill(icon: Icons.waves_rounded, label: 'Sóng êm'),
                ],
              ),
            ),
          ),
        ),
        if (_locationMessage != null)
          Positioned(
            top: 110,
            left: 12,
            child: PointerInterceptor(
              child: _MapPill(
                icon: Icons.location_disabled_outlined,
                label: _locationMessage!,
              ),
            ),
          ),
        Positioned(
          top: 112,
          right: 12,
          child: PointerInterceptor(
            child: Column(
              children: [
                _RoundMapButton(
                  key: const Key('locate-user-button'),
                  icon: Icons.my_location_rounded,
                  tooltip: 'Vị trí hiện tại',
                  onPressed: _locate,
                ),
                const SizedBox(height: 7),
                _RoundMapButton(
                  icon: Icons.explore_outlined,
                  tooltip: 'Hướng bản đồ',
                  onPressed: () {},
                ),
                const SizedBox(height: 7),
                _RoundMapButton(
                  icon: Icons.view_in_ar_outlined,
                  tooltip: 'Bản đồ 3D',
                  onPressed: () {},
                ),
              ],
            ),
          ),
        ),
        Positioned(
          left: 8,
          right: 8,
          bottom: 8,
          child: PointerInterceptor(
            child: _ActiveTripCard(
              nextStop: nextStop,
              stopCount: widget.stops.length,
              isPlaying: _isPlaying,
              onPlay: widget.stops.length > 1 ? _play : null,
              onPause: _isPlaying ? _pause : null,
              onReset: _reset,
              routeSource: switch (widget.routePreview?.quality) {
                'road_route' => 'OSRM',
                'matrix_estimate' => 'Ma trận',
                'interpolated' => 'Nội suy',
                _ => 'Không có',
              },
              mapSource: kIsWeb ? 'PMTiles' : 'OSM',
              onOpenPoi: widget.onOpenItinerary,
            ),
          ),
        ),
      ],
    );
  }
}

class _ActiveTripCard extends StatelessWidget {
  const _ActiveTripCard({
    required this.nextStop,
    required this.stopCount,
    required this.isPlaying,
    required this.onPlay,
    required this.onPause,
    required this.onReset,
    required this.routeSource,
    required this.mapSource,
    required this.onOpenPoi,
  });

  final MapStop? nextStop;
  final int stopCount;
  final bool isPlaying;
  final VoidCallback? onPlay;
  final VoidCallback? onPause;
  final VoidCallback onReset;
  final String routeSource;
  final String mapSource;
  final VoidCallback onOpenPoi;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(28),
      boxShadow: const [
        BoxShadow(
          color: Color(0x24006A6A),
          blurRadius: 28,
          offset: Offset(0, 10),
        ),
      ],
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              '✦ LỘ TRÌNH ĐẶC SẮC',
              style: const TextStyle(
                color: AppColors.accent,
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: .8,
              ),
            ),
            const Spacer(),
            const Icon(Icons.map_outlined, color: AppColors.warning, size: 15),
            const SizedBox(width: 4),
            const Text(
              'Đà Nẵng',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Container(
              width: 43,
              height: 43,
              decoration: BoxDecoration(
                color: AppColors.softSurface,
                borderRadius: BorderRadius.circular(13),
              ),
              child: const Icon(
                Icons.restaurant_menu_rounded,
                color: AppColors.primary,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Điểm tiếp theo',
                    style: TextStyle(fontSize: 10, color: AppColors.muted),
                  ),
                  Text(
                    nextStop?.title ?? 'Ngày 1 · Trung tâm & Biển Mỹ Khê',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    nextStop == null
                        ? '$stopCount điểm dừng trong lịch trình'
                        : '${nextStop!.time} · dừng ${nextStop!.durationMinutes} phút',
                    style: const TextStyle(fontSize: 11),
                  ),
                ],
              ),
            ),
            IconButton(
              onPressed: onOpenPoi,
              icon: const Icon(Icons.chevron_right_rounded),
            ),
          ],
        ),
        const SizedBox(height: 9),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.softSurface,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              _TripMetric(value: '$stopCount điểm', label: 'lịch trình'),
              const _Divider(),
              _TripMetric(value: routeSource, label: 'tuyến'),
              const _Divider(),
              _TripMetric(value: mapSource, label: 'bản đồ'),
            ],
          ),
        ),
        const SizedBox(height: 9),
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                key: const Key('play-car-button'),
                onPressed: onPlay,
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.secondary,
                  foregroundColor: Colors.white,
                ),
                icon: Icon(
                  isPlaying
                      ? Icons.directions_car_filled_rounded
                      : Icons.play_arrow_rounded,
                  size: 18,
                ),
                label: Text(isPlaying ? 'Đang dẫn đường' : 'Bắt đầu đi'),
              ),
            ),
            const SizedBox(width: 7),
            IconButton.filledTonal(
              tooltip: 'Tạm dừng',
              onPressed: onPause,
              icon: const Icon(Icons.pause_rounded),
            ),
            IconButton.filledTonal(
              tooltip: 'Đặt lại mô phỏng',
              onPressed: onReset,
              icon: const Icon(Icons.restart_alt_rounded),
            ),
            const SizedBox(width: 5),
            IconButton.filledTonal(
              tooltip: 'Chi tiết địa điểm',
              onPressed: onOpenPoi,
              icon: const Icon(Icons.info_outline_rounded),
            ),
          ],
        ),
      ],
    ),
  );
}

class _MapPill extends StatelessWidget {
  const _MapPill({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
    decoration: BoxDecoration(
      color: AppColors.surface.withValues(alpha: .94),
      borderRadius: BorderRadius.circular(20),
      boxShadow: const [BoxShadow(color: Color(0x18173C35), blurRadius: 8)],
    ),
    child: Row(
      children: [
        Icon(icon, color: AppColors.primary, size: 14),
        const SizedBox(width: 5),
        Text(
          label,
          style: const TextStyle(
            color: AppColors.ink,
            fontSize: 10,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    ),
  );
}

class _RoundMapButton extends StatelessWidget {
  const _RoundMapButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });
  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;
  @override
  Widget build(BuildContext context) => IconButton.filled(
    tooltip: tooltip,
    onPressed: onPressed,
    style: IconButton.styleFrom(
      backgroundColor: AppColors.surface,
      foregroundColor: AppColors.primary,
      shadowColor: const Color(0x28173C35),
      elevation: 3,
    ),
    icon: Icon(icon, size: 19),
  );
}

class _TripMetric extends StatelessWidget {
  const _TripMetric({required this.value, required this.label});
  final String value;
  final String label;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            color: AppColors.ink,
            fontSize: 11,
            fontWeight: FontWeight.w800,
          ),
        ),
        Text(label, style: const TextStyle(fontSize: 9)),
      ],
    ),
  );
}

class _Divider extends StatelessWidget {
  const _Divider();
  @override
  Widget build(BuildContext context) =>
      Container(width: 1, height: 24, color: AppColors.outline);
}
