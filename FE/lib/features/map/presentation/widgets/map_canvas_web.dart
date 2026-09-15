import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

import '../../../itinerary/domain/demo_trip.dart';

class MapCanvas extends StatefulWidget {
  const MapCanvas({
    super.key,
    required this.stops,
    required this.routeRevision,
    required this.playRequest,
  });

  final List<TripStop> stops;
  final int routeRevision;
  final int playRequest;

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
      },
    ).toString();
  }

  void _send(String type, {bool autoPlay = false}) {
    final message = jsonEncode({
      'type': type,
      'stops': _serializedStops,
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
      ..src = _mapUrl(autoPlay: widget.routeRevision > 0)
      ..title = 'Bản đồ 3D Đà Nẵng'
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
    if (widget.routeRevision != oldWidget.routeRevision) {
      _iframe.src = _mapUrl(autoPlay: true);
    } else if (widget.playRequest != oldWidget.playRequest) {
      _send('playRoute');
    }
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }
}
