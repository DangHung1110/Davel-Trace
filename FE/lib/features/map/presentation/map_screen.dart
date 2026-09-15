import 'package:flutter/material.dart';

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

  int get _activityCount => widget.stops.isEmpty ? 0 : widget.stops.length - 1;

  int get _visitMinutes =>
      widget.stops.fold(0, (total, stop) => total + stop.durationMinutes);

  String get _durationLabel {
    final hours = _visitMinutes ~/ 60;
    final minutes = _visitMinutes % 60;
    if (minutes == 0) return '$hours giờ';
    return '$hours giờ $minutes phút';
  }

  void _replayCar() => setState(() => _playRequest++);

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Positioned.fill(
          child: MapCanvas(
            stops: widget.stops,
            routeRevision: widget.planRevision,
            playRequest: _playRequest,
          ),
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
            child: TextField(
              readOnly: true,
              onTap: () => _showStops(context),
              decoration: const InputDecoration(
                hintText: 'Xem các điểm trong lịch trình',
                prefixIcon: Icon(Icons.search),
                suffixIcon: Icon(Icons.route_outlined),
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
            child: Row(
              children: [
                const CircleAvatar(
                  backgroundColor: AppColors.sky,
                  child: Icon(Icons.route, color: AppColors.blue),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'Hành trình demo',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 3),
                      Text('$_activityCount điểm · tham quan $_durationLabel'),
                    ],
                  ),
                ),
                FilledButton.icon(
                  key: const Key('play-car-button'),
                  onPressed: widget.stops.length > 1 ? _replayCar : null,
                  icon: const Icon(Icons.play_arrow_rounded, size: 19),
                  label: const Text('Chạy xe'),
                ),
              ],
            ),
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
              const SizedBox(height: 10),
              ...widget.stops.indexed.map(
                (entry) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: CircleAvatar(
                    backgroundColor: entry.$2.color.withValues(alpha: 0.12),
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
