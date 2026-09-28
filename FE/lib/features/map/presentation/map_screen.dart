import 'package:flutter/material.dart';

import '../../../shared/widgets/app_header.dart';
import '../../../theme/app_theme.dart';
import '../../itinerary/domain/demo_trip.dart';
import 'widgets/map_canvas.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({
    super.key,
    required this.stops,
    required this.planRevision,
    required this.onOpenPoi,
    required this.onOpenReplan,
  });

  final List<TripStop> stops;
  final int planRevision;
  final VoidCallback onOpenPoi;
  final VoidCallback onOpenReplan;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  int _playRequest = 0;
  int _pauseRequest = 0;
  int _locateRequest = 0;
  bool _isPlaying = false;

  void _play() => setState(() {
    _playRequest++;
    _isPlaying = true;
  });

  void _pause() => setState(() {
    _pauseRequest++;
    _isPlaying = false;
  });

  void _locate() => setState(() => _locateRequest++);

  @override
  void didUpdateWidget(covariant MapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.planRevision != widget.planRevision) _isPlaying = true;
  }

  @override
  Widget build(BuildContext context) {
    final nextStop = widget.stops.length > 1 ? widget.stops[1] : null;
    return Column(
      children: [
        AppHeader(
          compact: true,
          section: 'Chuyến đi đang diễn ra',
          trailing: IconButton(
            key: const Key('open-map-replan-button'),
            tooltip: 'Điều chỉnh lịch trình',
            onPressed: widget.onOpenReplan,
            icon: const Icon(Icons.tune_rounded),
          ),
        ),
        Expanded(
          child: Stack(
            children: [
              Positioned.fill(
                child: MapCanvas(
                  stops: widget.stops,
                  routeRevision: widget.planRevision,
                  playRequest: _playRequest,
                  pauseRequest: _pauseRequest,
                  locateRequest: _locateRequest,
                ),
              ),
              Positioned(
                top: 12,
                left: 12,
                right: 12,
                child: Row(
                  children: [
                    const _MapPill(
                      icon: Icons.cloud_off_outlined,
                      label: 'Offline · 08:30',
                    ),
                    const Spacer(),
                    _RoundMapButton(
                      key: const Key('locate-user-button'),
                      icon: Icons.my_location_rounded,
                      tooltip: 'Vị trí hiện tại',
                      onPressed: _locate,
                    ),
                  ],
                ),
              ),
              Positioned(
                top: 58,
                right: 12,
                child: Column(
                  children: [
                    _RoundMapButton(
                      icon: Icons.add_rounded,
                      tooltip: 'Phóng to',
                      onPressed: () {},
                    ),
                    const SizedBox(height: 7),
                    _RoundMapButton(
                      icon: Icons.remove_rounded,
                      tooltip: 'Thu nhỏ',
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
              Positioned(
                left: 12,
                right: 12,
                bottom: 12,
                child: _ActiveTripCard(
                  nextStop: nextStop,
                  stopCount: widget.stops.isEmpty ? 0 : widget.stops.length - 1,
                  isPlaying: _isPlaying,
                  onPlay: widget.stops.length > 1 ? _play : null,
                  onPause: _isPlaying ? _pause : null,
                  onOpenPoi: widget.onOpenPoi,
                ),
              ),
            ],
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
    required this.onOpenPoi,
  });

  final TripStop? nextStop;
  final int stopCount;
  final bool isPlaying;
  final VoidCallback? onPlay;
  final VoidCallback? onPause;
  final VoidCallback onOpenPoi;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: AppColors.outline),
      boxShadow: const [
        BoxShadow(
          color: Color(0x26173C35),
          blurRadius: 24,
          offset: Offset(0, 8),
        ),
      ],
    ),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text(
              'ĐANG ĐI · 2/4',
              style: TextStyle(
                color: AppColors.accent,
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: .8,
              ),
            ),
            Spacer(),
            Icon(Icons.wb_sunny_outlined, color: AppColors.warning, size: 15),
            SizedBox(width: 4),
            Text(
              '28°C',
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
                    nextStop?.title ?? 'Chưa có điểm đến',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const Text(
                    '12 phút · 3,2 km',
                    style: TextStyle(fontSize: 11),
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
              const _TripMetric(value: '750k', label: 'còn lại'),
              const _Divider(),
              const _TripMetric(value: '18:15', label: 'kết thúc'),
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
                icon: Icon(
                  isPlaying
                      ? Icons.directions_car_filled_rounded
                      : Icons.play_arrow_rounded,
                  size: 18,
                ),
                label: Text(isPlaying ? 'Đang di chuyển' : 'Mô phỏng tuyến'),
              ),
            ),
            const SizedBox(width: 7),
            IconButton.filledTonal(
              tooltip: 'Tạm dừng',
              onPressed: onPause,
              icon: const Icon(Icons.pause_rounded),
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
