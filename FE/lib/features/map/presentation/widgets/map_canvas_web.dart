import 'dart:async';
import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

import '../../../../core/config/api_config.dart';

import '../../../management/domain/models.dart';
import '../../domain/location_state.dart';
import '../map_stop.dart';
import 'map_bridge_controller.dart';

class MapCanvas extends StatefulWidget {
  const MapCanvas({
    super.key,
    required this.stops,
    required this.routeRevision,
    required this.playRequest,
    required this.pauseRequest,
    required this.resetRequest,
    required this.locateRequest,
    required this.userLocation,
    required this.routePreview,
    this.followUser = false,
    this.onUserPan,
    this.reloadRequest = 0,
    this.onMapError,
    this.onMapReady,
    this.onCoverageChanged,
  });

  final List<MapStop> stops;
  final int routeRevision,
      playRequest,
      pauseRequest,
      resetRequest,
      locateRequest,
      reloadRequest;
  final MapLocation? userLocation;
  final RoutePreviewData? routePreview;
  final bool followUser;
  final VoidCallback? onUserPan, onMapReady;
  final ValueChanged<String>? onMapError;
  final ValueChanged<bool>? onCoverageChanged;

  @override
  State<MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<MapCanvas> {
  late final String _viewType;
  late final web.HTMLIFrameElement _iframe;
  late final MapBridgeController _bridge;
  late final JSFunction _messageListener;
  StreamSubscription<web.Event>? _loadSubscription;
  Timer? _loadTimeout;

  String _frameUrl([int retry = 0]) => Uri(
    path: 'map_embed.html',
    queryParameters: {
      'api': ApiConfig.baseUrl,
      if (retry > 0) 'retry': '$retry',
    },
  ).toString();

  void _watchLoading() {
    _loadTimeout?.cancel();
    if (_bridge.ready) return;
    _loadTimeout = Timer(const Duration(seconds: 20), () {
      if (mounted && !_bridge.ready) {
        widget.onMapError?.call(
          'Bản đồ chưa tải được. Kiểm tra kết nối rồi thử lại.',
        );
      }
    });
  }

  @override
  void initState() {
    super.initState();
    _viewType = 'davel-local-pmtiles-${identityHashCode(this)}';
    _iframe = web.HTMLIFrameElement()
      ..src = _frameUrl()
      ..title = 'Bản đồ 3D Đà Nẵng'
      ..setAttribute('allow', 'geolocation')
      ..style.border = '0'
      ..style.width = '100%'
      ..style.height = '100%';
    _bridge = MapBridgeController((message) {
      _iframe.contentWindow?.postMessage(
        jsonEncode(message).toJS,
        web.window.location.origin.toJS,
      );
    });
    _bridge.updateTrip(widget.stops, widget.routeRevision, widget.routePreview);
    _bridge.updateLocation(
      widget.userLocation,
      follow: widget.followUser,
      recenter: widget.followUser,
    );
    _loadSubscription = _iframe.onLoad.listen((_) => _watchLoading());
    _messageListener = ((web.MessageEvent event) {
      if (event.origin != web.window.location.origin ||
          !event.source.strictEquals(_iframe.contentWindow).toDart) {
        return;
      }
      try {
        final raw = event.data.dartify();
        final data = raw is String ? jsonDecode(raw) : raw;
        if (data is! Map) return;
        switch (data['type']) {
          case 'mapReady':
            _loadTimeout?.cancel();
            _bridge.markReady();
            widget.onMapReady?.call();
          case 'mapError':
            _loadTimeout?.cancel();
            widget.onMapError?.call(
              'Không tải được bản đồ. Kiểm tra kết nối rồi thử lại.',
            );
          case 'mapCoverage':
            widget.onCoverageChanged?.call(data['inside'] == true);
          case 'mapUserPan':
            widget.onUserPan?.call();
        }
      } catch (_) {
        /* Ignore unrelated frame messages. */
      }
    }).toJS;
    web.window.addEventListener('message', _messageListener);
    ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) => _iframe);
    _watchLoading();
  }

  @override
  void didUpdateWidget(covariant MapCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.reloadRequest != oldWidget.reloadRequest) {
      _bridge.ready = false;
      _iframe.src = _frameUrl(widget.reloadRequest);
      _watchLoading();
    }
    _bridge.updateTrip(widget.stops, widget.routeRevision, widget.routePreview);
    if (widget.playRequest != oldWidget.playRequest) {
      _bridge.command('playRoute');
    }
    if (widget.pauseRequest != oldWidget.pauseRequest) {
      _bridge.command('pauseRoute');
    }
    if (widget.resetRequest != oldWidget.resetRequest) {
      _bridge.command('resetRoute');
    }
    if (widget.locateRequest != oldWidget.locateRequest ||
        widget.userLocation != oldWidget.userLocation ||
        widget.followUser != oldWidget.followUser) {
      _bridge.updateLocation(
        widget.userLocation,
        follow: widget.followUser,
        recenter: widget.locateRequest != oldWidget.locateRequest,
      );
    }
  }

  @override
  void dispose() {
    _loadTimeout?.cancel();
    unawaited(_loadSubscription?.cancel());
    web.window.removeEventListener('message', _messageListener);
    _iframe.remove();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => HtmlElementView(viewType: _viewType);
}
