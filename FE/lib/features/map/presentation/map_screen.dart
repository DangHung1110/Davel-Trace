import 'dart:async';

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
    this.isActive = true,
    this.isDraft = false,
  });

  final List<MapStop> stops;
  final int planRevision;
  final VoidCallback onOpenItinerary;
  final String? tripTitle;
  final RoutePreviewData? routePreview;
  final MapLocationProvider locationProvider;
  final bool isActive;
  final bool isDraft;

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> with WidgetsBindingObserver {
  int _playRequest = 0;
  int _pauseRequest = 0;
  int _resetRequest = 0;
  int _locateRequest = 0;
  int _reloadMapRequest = 0;
  String? _mapError;
  bool _outsideMapCoverage = false;
  bool _isPlaying = false;
  MapLocation? _userLocation;
  String? _locationMessage;
  bool _trackingRequested = false;
  bool _followUser = false;
  bool _appResumed = true;
  int _trackingGeneration = 0;
  StreamSubscription<MapLocationResult>? _positions;
  Future<void> _cancellation = Future<void>.value();
  late RoutePreviewData? _displayRoute = _routeForDisplay();

  RoutePreviewData? _routeForDisplay() {
    final route = widget.routePreview;
    if (route == null ||
        widget.stops.length < 2 ||
        route.geometry.length >= 2) {
      return route;
    }
    return RoutePreviewData(
      source: route.source,
      quality: route.quality == 'matrix_estimate'
          ? 'matrix_estimate'
          : 'interpolated',
      isRealRoute: false,
      distanceM: route.distanceM,
      durationS: route.durationS,
      geometry: [
        for (final stop in widget.stops) [stop.longitude, stop.latitude],
      ],
      warning: [
        if (route.warning case final warning? when warning.isNotEmpty) warning,
        'Đường nét đứt chỉ minh họa thứ tự điểm dừng.',
      ].join(' '),
    );
  }

  bool get _canTrack => widget.isActive && _appResumed && _trackingRequested;

  String get _gpsLabel {
    final accuracy = _userLocation?.accuracyMeters;
    return accuracy != null && accuracy.isFinite && accuracy >= 0
        ? 'GPS trực tiếp · ±${accuracy.round()} m'
        : 'GPS trực tiếp';
  }

  @override
  void initState() {
    super.initState();
    _appResumed =
        WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addObserver(this);
  }

  void _cancelPositions() {
    _trackingGeneration++;
    final old = _positions;
    _positions = null;
    if (old == null) return;
    _cancellation = _cancellation.then((_) async {
      try {
        await old.cancel();
      } catch (_) {
        /* Already released by platform. */
      }
    });
  }

  Future<void> _startTracking() async {
    _cancelPositions();
    final generation = _trackingGeneration;
    if (!mounted || !_canTrack) return;
    setState(() {
      _userLocation = null;
      _locationMessage = 'Đang xác định vị trí…';
    });
    await _cancellation;
    if (!mounted || !_canTrack || generation != _trackingGeneration) return;
    final provider = widget.locationProvider;

    bool isCurrent() =>
        mounted && _canTrack && generation == _trackingGeneration;

    void applyFix(MapLocation location) {
      if (!isCurrent() || !location.isValid) return;
      final previous = _userLocation;
      if (previous?.timestamp != null &&
          location.timestamp != null &&
          !location.timestamp!.isAfter(previous!.timestamp!)) {
        return;
      }
      setState(() {
        _userLocation = location;
        _locationMessage = null;
        if (previous == null && _followUser) _locateRequest++;
      });
    }

    try {
      _positions = provider.watchLocation().listen(
        (result) {
          if (!isCurrent()) return;
          final location = result.location;
          if (result.status != MapLocationStatus.located || location == null) {
            _endTracking(
              mapLocationMessage(
                result.status == MapLocationStatus.located
                    ? MapLocationStatus.unavailable
                    : result.status,
              ),
            );
            return;
          }
          applyFix(location);
        },
        onError: (Object error, StackTrace stack) {
          if (mounted && generation == _trackingGeneration) {
            _endTracking(mapLocationMessage(MapLocationStatus.unavailable));
          }
        },
        onDone: () {
          if (mounted && generation == _trackingGeneration && _canTrack) {
            _endTracking('GPS đã dừng. Bấm vị trí để thử lại.');
          }
        },
      );
      // A new watch can wait for movement. Ask for one fix in parallel so
      // restarting GPS can restore the marker while the traveler is still.
      unawaited(
        Future.sync(provider.currentLocation).then((result) {
          if (result.status == MapLocationStatus.located &&
              result.location != null &&
              _userLocation == null) {
            applyFix(result.location!);
          }
        }, onError: (Object _) {}),
      );
    } catch (_) {
      if (mounted && generation == _trackingGeneration) {
        _endTracking(mapLocationMessage(MapLocationStatus.unavailable));
      }
    }
  }

  void _endTracking(String message) {
    _cancelPositions();
    setState(() {
      _trackingRequested = false;
      _followUser = false;
      _userLocation = null;
      _locationMessage = message;
      _outsideMapCoverage = false;
    });
  }

  void _toggleTracking() {
    if (_trackingRequested) {
      _endTracking('Đã tắt GPS trực tiếp.');
    } else {
      setState(() {
        _trackingRequested = true;
        _followUser = true;
      });
      unawaited(_startTracking());
    }
  }

  void _recenter() {
    if (_userLocation == null) return;
    setState(() {
      _followUser = true;
      _locateRequest++;
    });
  }

  void _releaseCamera() {
    if (_followUser && mounted) setState(() => _followUser = false);
  }

  void _suspendTracking() {
    _cancelPositions();
    _userLocation = null;
    if (_trackingRequested) _locationMessage = 'GPS tạm dừng.';
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _appResumed = state == AppLifecycleState.resumed;
    if (_canTrack) {
      unawaited(_startTracking());
    } else {
      setState(_suspendTracking);
    }
  }

  void _play() => setState(() {
    _playRequest++;
    _isPlaying = true;
  });

  void _pause() => setState(() {
    _pauseRequest++;
    _isPlaying = false;
  });

  void _reset() => setState(() {
    _isPlaying = false;
    _resetRequest++;
  });

  @override
  void didUpdateWidget(covariant MapScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.routePreview != widget.routePreview ||
        !listEquals(oldWidget.stops, widget.stops)) {
      _displayRoute = _routeForDisplay();
      _isPlaying = false;
    }
    if (oldWidget.isActive != widget.isActive ||
        oldWidget.locationProvider != widget.locationProvider) {
      if (_canTrack) {
        unawaited(_startTracking());
      } else {
        _suspendTracking();
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cancelPositions();
    super.dispose();
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
            routePreview: _displayRoute,
            followUser: _followUser,
            onUserPan: _releaseCamera,
            reloadRequest: _reloadMapRequest,
            onMapError: (message) {
              if (mounted && _mapError != message) {
                setState(() => _mapError = message);
              }
            },
            onMapReady: () {
              if (mounted && _mapError != null) {
                setState(() => _mapError = null);
              }
            },
            onCoverageChanged: (inside) {
              if (mounted && _outsideMapCoverage == inside) {
                setState(() => _outsideMapCoverage = !inside);
              }
            },
          ),
        ),
        Positioned(
          top: 12,
          left: 12,
          right: 12,
          child: PointerInterceptor(
            child: Material(
              color: AppColors.surface.withValues(alpha: .96),
              elevation: 1,
              borderRadius: BorderRadius.circular(12),
              child: InkWell(
                key: const Key('open-map-replan-button'),
                borderRadius: BorderRadius.circular(12),
                onTap: widget.onOpenItinerary,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  child: Row(
                    children: [
                      const CircleAvatar(
                        radius: 16,
                        backgroundColor: AppColors.sand,
                        child: Icon(
                          Icons.arrow_back_rounded,
                          color: AppColors.primary,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          widget.tripTitle ??
                              'Chọn chuyến đi để xem lịch trình',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.ink,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        Positioned(
          top: 68,
          left: 12,
          right: 12,
          child: Column(
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (widget.stops.length > 1)
                          _MapPill(
                            icon: switch (_displayRoute?.quality) {
                              'road_route' => Icons.route_rounded,
                              'matrix_estimate' => Icons.straighten_rounded,
                              'interpolated' => Icons.linear_scale_rounded,
                              _ => Icons.offline_bolt_outlined,
                            },
                            label: switch (_displayRoute?.quality) {
                              'road_route' =>
                                'OSRM ${(_displayRoute!.distanceM / 1000).toStringAsFixed(1)} km',
                              'matrix_estimate' => 'Ước tính ma trận',
                              'interpolated' => 'Nội suy minh họa',
                              _ => 'Chưa có tuyến',
                            },
                          ),
                        if (_locationMessage != null || _userLocation != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Semantics(
                              liveRegion: true,
                              child: _MapPill(
                                icon: _userLocation == null
                                    ? Icons.location_disabled_outlined
                                    : Icons.gps_fixed,
                                label: _locationMessage ?? _gpsLabel,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (!widget.isDraft)
                    PointerInterceptor(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          SizedBox(
                            width: 132,
                            child: Tooltip(
                              message: _trackingRequested
                                  ? 'Tắt GPS trực tiếp'
                                  : 'Bật GPS trực tiếp',
                              child: FilledButton.icon(
                                key: const Key('locate-user-button'),
                                icon: Icon(
                                  _trackingRequested
                                      ? Icons.gps_off_rounded
                                      : Icons.my_location_rounded,
                                  size: 18,
                                ),
                                label: Text(
                                  _trackingRequested ? 'Tắt GPS' : 'Bật GPS',
                                ),
                                onPressed: _toggleTracking,
                              ),
                            ),
                          ),
                          const SizedBox(height: 4),
                          _RoundMapButton(
                            key: const Key('follow-user-button'),
                            icon: _followUser
                                ? Icons.gps_fixed_rounded
                                : Icons.gps_not_fixed_rounded,
                            tooltip: 'Về vị trí của tôi',
                            onPressed: _userLocation == null ? null : _recenter,
                          ),
                        ],
                      ),
                    ),
                ],
              ),
              if (_mapError != null || _outsideMapCoverage) ...[
                const SizedBox(height: 6),
                PointerInterceptor(
                  child: Material(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(18),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _mapError ?? 'Vị trí GPS nằm ngoài vùng bản đồ Đà Nẵng. Bản đồ vẫn giữ ở chuyến đi của bạn.',
                          ),
                          if (_mapError != null)
                            TextButton.icon(
                              key: const Key('retry-map-button'),
                              onPressed: () => setState(() {
                                _mapError = null;
                                _reloadMapRequest++;
                              }),
                              icon: const Icon(Icons.refresh),
                              label: const Text('Tải lại bản đồ'),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ],
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
              onPlay: (_displayRoute?.geometry.length ?? 0) >= 2 ? _play : null,
              onPause: _isPlaying ? _pause : null,
              onReset: _reset,
              routeSource: switch (_displayRoute?.quality) {
                'road_route' => 'OSRM',
                'matrix_estimate' => 'Ma trận',
                'interpolated' => 'Nội suy',
                _ => 'Không có',
              },
              mapSource: kIsWeb ? 'PMTiles' : 'OSM',
              onOpenPoi: widget.onOpenItinerary,
              isDraft: widget.isDraft,
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
    required this.isDraft,
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
  final bool isDraft;

  @override
  Widget build(BuildContext context) => Container(
    constraints: BoxConstraints(
      maxHeight: MediaQuery.sizeOf(context).height * .42,
    ),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: AppColors.outline),
      boxShadow: const [
        BoxShadow(
          color: Color(0x18193F33),
          blurRadius: 14,
          offset: Offset(0, 4),
        ),
      ],
    ),
    child: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (stopCount == 0) ...[
            Text(
              isDraft
                  ? 'Phương án chưa có điểm xác định vị trí'
                  : 'Chuyến đi chưa có địa điểm',
              key: const Key('empty-map-message'),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 4),
            Text(
              isDraft
                  ? 'Quay lại để xem danh sách điểm và thử phương án khác.'
                  : 'Mở Lập lịch để xem phương án dự kiến hoặc thêm điểm vào lịch.',
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                key: const Key('empty-map-open-itinerary'),
                onPressed: onOpenPoi,
                icon: const Icon(Icons.add_location_alt_outlined),
                label: Text(isDraft ? 'Quay lại phương án' : 'Về lịch trình'),
              ),
            ),
          ] else ...[
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
                    Icons.location_on_outlined,
                    color: AppColors.primary,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isDraft
                            ? 'Điểm xuất phát trong phương án'
                            : 'Điểm đầu tiên',
                        style: const TextStyle(
                          fontSize: 10,
                          color: AppColors.muted,
                        ),
                      ),
                      Text(
                        nextStop?.title ?? 'Chưa có điểm dừng trên bản đồ',
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
                  tooltip: isDraft ? 'Quay lại phương án' : 'Xem chuyến đi',
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
                    label: Text(isPlaying ? 'Đang mô phỏng' : 'Mô phỏng tuyến'),
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
              ],
            ),
          ],
        ],
      ),
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
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: AppColors.primary, size: 14),
        const SizedBox(width: 5),
        Flexible(
          child: Text(
            label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 10,
              fontWeight: FontWeight.w800,
            ),
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
  final VoidCallback? onPressed;
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
