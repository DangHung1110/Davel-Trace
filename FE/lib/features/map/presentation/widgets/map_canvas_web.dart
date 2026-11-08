import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

import '../../../management/domain/models.dart';
import '../../domain/location_state.dart';
import '../map_stop.dart';

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
  });

  final List<MapStop> stops;
  final int routeRevision;
  final int playRequest;
  final int pauseRequest;
  final int resetRequest;
  final int locateRequest;
  final MapLocation? userLocation;
  final RoutePreviewData? routePreview;

  @override
  State<MapCanvas> createState() => _MapCanvasState();
}

class _MapCanvasState extends State<MapCanvas> {
  late final String _viewType;
  late final web.HTMLIFrameElement _iframe;

  List<Map<String, Object>> get _serializedStops => widget.stops
      .map(
        (stop) => <String, Object>{
          'id': stop.id,
          'title': stop.title,
          'subtitle': stop.subtitle,
          'latitude': stop.latitude,
          'longitude': stop.longitude,
        },
      )
      .toList();

  String _mapUrl({required bool autoPlay}) {
    return Uri(
      path: 'map_embed.html',
      queryParameters: {
        'stops': jsonEncode(_serializedStops),
        'autoplay': autoPlay.toString(),
        'route': jsonEncode(widget.routePreview?.toJson()),
      },
    ).toString();
  }

  void _send(String type, {bool autoPlay = false}) {
    final message = jsonEncode({
      'type': type,
      'stops': _serializedStops,
      'route': widget.routePreview?.toJson(),
      'autoPlay': autoPlay,
    });
    _iframe.contentWindow?.postMessage(
      message.toJS,
      web.window.location.origin.toJS,
    );
  }

  @override
  void initState() {
    super.initState();
    _viewType = 'davel-local-pmtiles-${identityHashCode(this)}';
    _iframe = web.HTMLIFrameElement()
      ..src = _mapUrl(autoPlay: false)
      ..title = 'Bản đồ 3D Đà Nẵng'
      ..setAttribute('allow', 'geolocation')
      ..setAttribute('allowfullscreen', 'true')
      ..style.border = '0'
      ..style.width = '100%'
      ..style.height = '100%';

    ui_web.platformViewRegistry.registerViewFactory(_viewType, (int viewId) {
      return _iframe;
    });
  }

  @override
  void didUpdateWidget(covariant MapCanvas oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.routeRevision != oldWidget.routeRevision ||
        widget.routePreview != oldWidget.routePreview ||
        widget.stops != oldWidget.stops) {
      _iframe.src = _mapUrl(autoPlay: false);
    } else if (widget.playRequest != oldWidget.playRequest) {
      _send('playRoute');
    } else if (widget.pauseRequest != oldWidget.pauseRequest) {
      _send('pauseRoute');
    }
    if (widget.resetRequest != oldWidget.resetRequest) _send('resetRoute');
    if (widget.locateRequest != oldWidget.locateRequest) {
      final location = widget.userLocation;
      if (location != null) {
        _iframe.contentWindow?.postMessage(
          jsonEncode({
            'type': 'setUserLocation',
            'latitude': location.latitude,
            'longitude': location.longitude,
          }).toJS,
          web.window.location.origin.toJS,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }
}
