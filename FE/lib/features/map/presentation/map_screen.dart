import 'package:flutter/material.dart';

import '../../../shared/widgets/app_header.dart';
import '../../../theme/app_theme.dart';
import '../../itinerary/domain/demo_trip.dart';
import 'widgets/map_canvas.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key, required this.stops, required this.planRevision});
  final List<TripStop> stops;
  final int planRevision;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  int _playRequest = 0;
  int _pauseRequest = 0;
  bool _isPlaying = false;

  int get _activityCount => widget.stops.isEmpty ? 0 : widget.stops.length - 1;
  int get _visitMinutes =>
      widget.stops.fold(0, (total, stop) => total + stop.durationMinutes);

  String get _durationLabel {
    final hours = _visitMinutes ~/ 60;
    final minutes = _visitMinutes % 60;
    return minutes == 0 ? '$hours giờ' : '$hours giờ $minutes phút';
  }

  void _playCar() => setState(() {
    _playRequest++;
    _isPlaying = true;
  });

  void _pauseCar() => setState(() {
    _pauseRequest++;
    _isPlaying = false;
  });

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
        const AppHeader(),
        Expanded(
          child: Stack(
            children: [
              Positioned.fill(
                child: MapCanvas(
                  stops: widget.stops,
                  routeRevision: widget.planRevision,
                  playRequest: _playRequest,
                  pauseRequest: _pauseRequest,
                ),
              ),
              Positioned(
                top: 10,
                left: 12,
                right: 12,
                child: Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(14),
                  elevation: 3,
                  shadowColor: const Color(0x22121B2E),
                  child: TextField(
                    readOnly: true,
                    onTap: () => _showStops(context),
                    style: const TextStyle(fontSize: 11),
                    decoration: const InputDecoration(
                      hintText: 'Tìm địa điểm ở Đà Nẵng...',
                      prefixIcon: Icon(Icons.search_rounded, size: 20),
                      suffixIcon: Icon(Icons.tune_rounded, size: 19),
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                    ),
                  ),
                ),
              ),
              const Positioned(
                top: 66,
                left: 12,
                child: _MapPill(
                  icon: Icons.wb_sunny_outlined,
                  label: '26°C · Nắng nhẹ',
                ),
              ),
              Positioned(
                top: 66,
                right: 12,
                child: _MapPill(
                  icon: Icons.view_in_ar_outlined,
                  label: '3D',
                  onTap: () {},
                ),
              ),
              Positioned(
                left: 12,
                right: 12,
                bottom: 176,
                child: Row(
                  children: [
                    const _RouteState(label: 'Đang tải route'),
                    const SizedBox(width: 5),
                    const _RouteState(label: 'Đã tạo lộ trình'),
                    const SizedBox(width: 5),
                    _RouteState(
                      label: _isPlaying ? 'Xe đang chạy' : 'Sẵn sàng',
                      active: _isPlaying,
                    ),
                  ],
                ),
              ),
              Positioned(
                left: 12,
                right: 12,
                bottom: 10,
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x29121B2E),
                        blurRadius: 25,
                        offset: Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        children: [
                          const Text(
                            'LỘ TRÌNH NGÀY 1',
                            style: TextStyle(
                              fontSize: 8,
                              color: AppColors.blue,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(width: 5),
                          Container(
                            width: 5,
                            height: 5,
                            decoration: const BoxDecoration(
                              color: AppColors.success,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const Spacer(),
                          const Icon(
                            Icons.navigation_rounded,
                            size: 12,
                            color: AppColors.blue,
                          ),
                          const SizedBox(width: 3),
                          const Text(
                            'GPS Tốt',
                            style: TextStyle(
                              fontSize: 8,
                              color: AppColors.blue,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Hành trình demo',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.softSurface,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            _Metric(
                              icon: Icons.pin_drop_outlined,
                              label: 'Điểm dừng',
                              value: '$_activityCount điểm',
                            ),
                            const _MetricDivider(),
                            const _Metric(
                              icon: Icons.route_outlined,
                              label: 'Quãng đường',
                              value: '12,4 km',
                            ),
                            const _MetricDivider(),
                            _Metric(
                              icon: Icons.schedule_outlined,
                              label: 'Thời gian',
                              value: _durationLabel,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 7),
                      Row(
                        children: [
                          const Icon(
                            Icons.near_me_rounded,
                            size: 13,
                            color: AppColors.blue,
                          ),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              nextStop == null
                                  ? 'Chưa có điểm đến'
                                  : 'Điểm tiếp theo: ${nextStop.title}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 9,
                                color: AppColors.deepBlue,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const Text(
                            '2,4 km',
                            style: TextStyle(
                              fontSize: 9,
                              color: AppColors.blue,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton.icon(
                              key: const Key('play-car-button'),
                              onPressed: widget.stops.length > 1
                                  ? _playCar
                                  : null,
                              style: FilledButton.styleFrom(
                                backgroundColor: AppColors.success,
                              ),
                              icon: Icon(
                                _isPlaying
                                    ? Icons.directions_car_filled_rounded
                                    : Icons.play_arrow_rounded,
                                size: 17,
                              ),
                              label: Text(_isPlaying ? 'Đang chạy' : 'Chạy xe'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton.filledTonal(
                            tooltip: 'Tạm dừng',
                            onPressed: _isPlaying ? _pauseCar : null,
                            icon: const Icon(Icons.pause_rounded, size: 18),
                          ),
                          const SizedBox(width: 4),
                          IconButton.filledTonal(
                            tooltip: 'Chạy lại',
                            onPressed: widget.stops.length > 1
                                ? _playCar
                                : null,
                            icon: const Icon(Icons.replay_rounded, size: 18),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _showStops(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Các điểm trên tuyến',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              ...widget.stops.indexed.map(
                (entry) => ListTile(
                  dense: true,
                  leading: CircleAvatar(
                    backgroundColor: entry.$2.color.withValues(alpha: .12),
                    child: Text(
                      entry.$1 == 0 ? 'A' : '${entry.$1}',
                      style: TextStyle(
                        color: entry.$2.color,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  title: Text(entry.$2.title),
                  subtitle: Text(entry.$2.subtitle),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MapPill extends StatelessWidget {
  const _MapPill({required this.icon, required this.label, this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Material(
    color: Colors.white,
    borderRadius: BorderRadius.circular(20),
    elevation: 2,
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
        child: Row(
          children: [
            Icon(icon, size: 13, color: AppColors.blue),
            const SizedBox(width: 4),
            Text(
              label,
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    ),
  );
}

class _RouteState extends StatelessWidget {
  const _RouteState({required this.label, this.active = false});
  final String label;
  final bool active;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: active
            ? AppColors.deepBlue
            : Colors.white.withValues(alpha: .94),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: TextStyle(
          color: active ? Colors.white : AppColors.muted,
          fontSize: 7,
          fontWeight: FontWeight.w700,
        ),
      ),
    ),
  );
}

class _Metric extends StatelessWidget {
  const _Metric({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Row(
      children: [
        Icon(icon, size: 15, color: AppColors.blue),
        const SizedBox(width: 5),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(fontSize: 7, color: AppColors.muted),
              ),
              Text(
                value,
                style: const TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                ),
                maxLines: 1,
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _MetricDivider extends StatelessWidget {
  const _MetricDivider();
  @override
  Widget build(BuildContext context) => Container(
    width: 1,
    height: 26,
    margin: const EdgeInsets.symmetric(horizontal: 5),
    color: AppColors.outline,
  );
}
