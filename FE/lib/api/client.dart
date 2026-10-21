import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Base URL of the FastAPI backend (`.../v1`).
///
/// Override at build/run time with:
/// `--dart-define=API_BASE_URL=https://api.example.com/v1`.
const String _defaultApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000/v1',
);

/// Error returned by the API contract: `{ "error": "<code>", "message": "<vi>" }`.
class ApiException implements Exception {
  const ApiException({
    required this.statusCode,
    required this.code,
    required this.message,
  });

  /// HTTP status, or `0` when the request never produced a response.
  final int statusCode;

  /// Stable machine-readable code (`error` in the contract envelope).
  final String code;

  /// Human-readable (Vietnamese) message.
  final String message;

  bool get isNetworkError => statusCode == 0;

  @override
  String toString() => 'ApiException($statusCode, $code): $message';
}

/// Typed client for all ten BE <-> Flutter v1 operations.
class ApiClient {
  ApiClient({
    http.Client? httpClient,
    String? baseUrl,
    this.timeout = const Duration(seconds: 20),
  }) : _http = httpClient ?? http.Client(),
       baseUrl = _normalizeBaseUrl(baseUrl ?? _defaultApiBaseUrl);

  static const String defaultBaseUrl = _defaultApiBaseUrl;

  final http.Client _http;
  final String baseUrl;
  final Duration timeout;

  static String _normalizeBaseUrl(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return _defaultApiBaseUrl;
    return trimmed.endsWith('/')
        ? trimmed.substring(0, trimmed.length - 1)
        : trimmed;
  }

  /// Close the underlying HTTP client when this client is no longer needed.
  void close() => _http.close();

  // ---------------------------------------------------------------------------
  // 1. POST /parse
  // ---------------------------------------------------------------------------

  /// Natural language -> [TripRequest], or a clarification request.
  Future<ParseResult> parse(String text, {String? userId}) async {
    final body = <String, Object?>{'text': text};
    if (userId != null) {
      body['user_id'] = userId;
    }
    final json = await _post('/parse', body);
    return ParseResult.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 2. POST /itinerary
  // ---------------------------------------------------------------------------

  /// Build one plan per profile (default: savings/balanced/experience).
  Future<PlanList> createItinerary({
    required TripRequest trip,
    List<String> profiles = const <String>['savings', 'balanced', 'experience'],
  }) async {
    final json = await _post('/itinerary', <String, Object?>{
      'trip': trip.toJson(),
      'profiles': profiles,
    });
    return PlanList.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 3. POST /itinerary/select
  // ---------------------------------------------------------------------------

  /// Confirm a plan as the active itinerary.
  Future<SelectResult> selectItinerary(String itineraryId) async {
    final json = await _post('/itinerary/select', <String, Object?>{
      'itinerary_id': itineraryId,
    });
    return SelectResult.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 4. POST /replan
  // ---------------------------------------------------------------------------

  /// Replan around a dynamic event. [event] is the flexible `DynamicEvent`
  /// payload from the contract (type/at/delta/...).
  Future<ReplanResult> replan({
    required String itineraryId,
    required Map<String, Object?> event,
  }) async {
    final json = await _post('/replan', <String, Object?>{
      'itinerary_id': itineraryId,
      'event': event,
    });
    return ReplanResult.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 5. GET /itinerary/{id}
  // ---------------------------------------------------------------------------

  /// Read a stored itinerary (offline cache key).
  Future<Itinerary> getItinerary(String itineraryId) async {
    final json = await _get('/itinerary/${Uri.encodeComponent(itineraryId)}');
    return Itinerary.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 6. POST /expenses
  // ---------------------------------------------------------------------------

  /// Log an expense entry. [kind] is one of `food|ticket|transport|other`.
  Future<ExpenseEntry> addExpense({
    required String tripId,
    required String label,
    required int amount,
    String kind = 'other',
  }) async {
    final json = await _post('/expenses', <String, Object?>{
      'trip_id': tripId,
      'label': label,
      'amount': amount,
      'kind': kind,
    });
    return ExpenseEntry.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 7. GET /expenses/summary?trip_id=
  // ---------------------------------------------------------------------------

  Future<ExpenseSummary> getExpenseSummary(String tripId) async {
    final json = await _get(
      '/expenses/summary',
      query: <String, String>{'trip_id': tripId},
    );
    return ExpenseSummary.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 8. GET /weather?lat=&lon=
  // ---------------------------------------------------------------------------

  Future<WeatherSnapshot> getWeather({
    required double lat,
    required double lon,
  }) async {
    final json = await _get(
      '/weather',
      query: <String, String>{'lat': '$lat', 'lon': '$lon'},
    );
    return WeatherSnapshot.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 9. POST /evaluate
  // ---------------------------------------------------------------------------

  Future<EvaluateResult> evaluate({
    required Itinerary itinerary,
    required TripRequest trip,
  }) async {
    final json = await _post('/evaluate', <String, Object?>{
      'itinerary': itinerary.toJson(),
      'trip': trip.toJson(),
    });
    return EvaluateResult.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // 10. POST /score-transition
  // ---------------------------------------------------------------------------

  /// PATM pre-check for a POI transition. `a`, `b` and `user` are the
  /// contract's flexible `poi+ctx` / user payloads.
  Future<TransitionScore> scoreTransition({
    required Map<String, Object?> a,
    required Map<String, Object?> b,
    required Map<String, Object?> user,
  }) async {
    final json = await _post('/score-transition', <String, Object?>{
      'a': a,
      'b': b,
      'user': user,
    });
    return TransitionScore.fromJson(json);
  }

  // ---------------------------------------------------------------------------
  // Transport
  // ---------------------------------------------------------------------------

  Future<Map<String, Object?>> _get(String path, {Map<String, String>? query}) {
    return _send('GET', path, query: query);
  }

  Future<Map<String, Object?>> _post(String path, Object? body) {
    return _send('POST', path, body: body);
  }

  Future<Map<String, Object?>> _send(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
  }) async {
    final request = http.Request(method, _uri(path, query))
      ..headers.addAll(const <String, String>{
        'accept': 'application/json',
        'content-type': 'application/json',
      });
    if (body != null) {
      request.body = jsonEncode(body);
    }

    final http.Response response;
    try {
      final streamed = await _http.send(request).timeout(timeout);
      response = await http.Response.fromStream(streamed).timeout(timeout);
    } on TimeoutException {
      throw const ApiException(
        statusCode: 0,
        code: 'TIMEOUT',
        message: 'May chu khong phan hoi kip.',
      );
    } on http.ClientException catch (error) {
      throw ApiException(
        statusCode: 0,
        code: 'NETWORK_ERROR',
        message: error.message,
      );
    }

    final decoded = _tryDecodeObject(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        statusCode: response.statusCode,
        code: decoded == null
            ? 'HTTP_${response.statusCode}'
            : _asString(decoded['error'], 'HTTP_${response.statusCode}'),
        message: decoded == null
            ? _truncate(response.body, response.reasonPhrase ?? '')
            : _asString(
                decoded['message'],
                response.reasonPhrase ?? 'Yeu cau that bai.',
              ),
      );
    }
    if (decoded == null) {
      throw ApiException(
        statusCode: response.statusCode,
        code: 'INVALID_RESPONSE',
        message: 'Phan hoi khong phai JSON object.',
      );
    }
    return decoded;
  }

  Uri _uri(String path, Map<String, String>? query) {
    final uri = Uri.parse('$baseUrl$path');
    if (query == null || query.isEmpty) return uri;
    return uri.replace(
      queryParameters: <String, String>{...uri.queryParameters, ...query},
    );
  }
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

Map<String, Object?>? _tryDecodeObject(String body) {
  if (body.trim().isEmpty) return const <String, Object?>{};
  try {
    final value = jsonDecode(body);
    if (value is Map<String, Object?>) return value;
    if (value is Map) {
      return value.map((key, item) => MapEntry(key.toString(), item));
    }
    return null;
  } on FormatException {
    return null;
  }
}

Map<String, Object?> _asMap(Object? value) {
  if (value is Map<String, Object?>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const <String, Object?>{};
}

List<Object?> _asList(Object? value) {
  if (value is List) return value;
  return const <Object?>[];
}

String _asString(Object? value, [String fallback = '']) {
  if (value is String) return value;
  if (value == null) return fallback;
  return value.toString();
}

String? _asNullableString(Object? value) {
  if (value == null) return null;
  final text = _asString(value);
  return text.isEmpty ? null : text;
}

int _asInt(Object? value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? fallback;
  return fallback;
}

double _asDouble(Object? value, [double fallback = 0]) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? fallback;
  return fallback;
}

bool _asBool(Object? value, [bool fallback = false]) {
  if (value is bool) return value;
  if (value is String) return value.toLowerCase() == 'true';
  if (value is num) return value != 0;
  return fallback;
}

List<String> _asStringList(Object? value) {
  return _asList(value).map((item) => _asString(item)).toList(growable: false);
}

List<List<String>> _asStringMatrix(Object? value) {
  return _asList(value)
      .map((row) => _asStringList(row))
      .toList(growable: false);
}

Map<String, Object?> _asObjectMap(Object? value) {
  return _asMap(value).map((key, item) => MapEntry(key, item));
}

Map<String, double> _asDoubleMap(Object? value) {
  return _asMap(value).map((key, item) => MapEntry(key, _asDouble(item)));
}

String _truncate(String value, String fallback) {
  final trimmed = value.trim();
  if (trimmed.isEmpty) return fallback;
  return trimmed.length <= 200 ? trimmed : '${trimmed.substring(0, 200)}...';
}

// -----------------------------------------------------------------------------
// Request DTOs
// -----------------------------------------------------------------------------

class TripOrigin {
  const TripOrigin({required this.lat, required this.lon, this.label = ''});

  factory TripOrigin.fromJson(Map<String, Object?> json) {
    return TripOrigin(
      lat: _asDouble(json['lat']),
      lon: _asDouble(json['lon']),
      label: _asString(json['label']),
    );
  }

  final double lat;
  final double lon;
  final String label;

  Map<String, Object?> toJson() => <String, Object?>{
    'lat': lat,
    'lon': lon,
    'label': label,
  };
}

/// `TripRequest` from the BE contract.
class TripRequest {
  TripRequest({
    this.tripId = 't1',
    this.userId = 'u1',
    this.origin,
    this.city = 'da-nang',
    this.date = '',
    this.startTime = '07:00',
    this.endTime = '18:00',
    this.days = 1,
    this.travelers = 2,
    this.budget = 3000000,
    List<String>? transport,
    List<String>? mustVisit,
    List<String>? avoid,
    List<String>? activities,
    List<String>? foodPrefs,
    List<List<String>>? orderPrefs,
  }) : transport = List<String>.unmodifiable(
         transport ?? const <String>['motorbike'],
       ),
       mustVisit = List<String>.unmodifiable(mustVisit ?? const <String>[]),
       avoid = List<String>.unmodifiable(avoid ?? const <String>[]),
       activities = List<String>.unmodifiable(activities ?? const <String>[]),
       foodPrefs = List<String>.unmodifiable(foodPrefs ?? const <String>[]),
       orderPrefs = List<List<String>>.unmodifiable(
         orderPrefs ?? const <List<String>>[],
       );

  factory TripRequest.fromJson(Map<String, Object?> json) {
    return TripRequest(
      tripId: _asString(json['trip_id'], 't1'),
      userId: _asString(json['user_id'], 'u1'),
      origin: json['origin'] == null
          ? null
          : TripOrigin.fromJson(_asMap(json['origin'])),
      city: _asString(json['city'], 'da-nang'),
      date: _asString(json['date']),
      startTime: _asString(json['start_time'], '07:00'),
      endTime: _asString(json['end_time'], '18:00'),
      days: _asInt(json['days'], 1),
      travelers: _asInt(json['travelers'], 2),
      budget: _asInt(json['budget'], 3000000),
      transport: _asStringList(json['transport']),
      mustVisit: _asStringList(json['must_visit']),
      avoid: _asStringList(json['avoid']),
      activities: _asStringList(json['activities']),
      foodPrefs: _asStringList(json['food_prefs']),
      orderPrefs: _asStringMatrix(json['order_prefs']),
    );
  }

  final String tripId;
  final String userId;
  final TripOrigin? origin;
  final String city;
  final String date;
  final String startTime;
  final String endTime;
  final int days;
  final int travelers;
  final int budget;
  final List<String> transport;
  final List<String> mustVisit;
  final List<String> avoid;
  final List<String> activities;
  final List<String> foodPrefs;
  final List<List<String>> orderPrefs;

  Map<String, Object?> toJson() => <String, Object?>{
    'trip_id': tripId,
    'user_id': userId,
    if (origin != null) 'origin': origin!.toJson(),
    'city': city,
    'date': date,
    'start_time': startTime,
    'end_time': endTime,
    'days': days,
    'travelers': travelers,
    'budget': budget,
    'transport': transport,
    'must_visit': mustVisit,
    'avoid': avoid,
    'activities': activities,
    'food_prefs': foodPrefs,
    'order_prefs': orderPrefs,
  };
}

// -----------------------------------------------------------------------------
// Response DTOs
// -----------------------------------------------------------------------------

class Activity {
  const Activity({
    required this.poiId,
    this.kind = 'visit',
    this.start = '',
    this.end = '',
    this.intensity = 2,
    this.visitMin = 0,
    this.bufferMin = 0,
    this.status = 'planned',
    this.explanation,
  });

  factory Activity.fromJson(Map<String, Object?> json) {
    return Activity(
      poiId: _asString(json['poi_id']),
      kind: _asString(json['kind'], 'visit'),
      start: _asString(json['start']),
      end: _asString(json['end']),
      intensity: _asInt(json['intensity'], 2),
      visitMin: _asInt(json['visit_min']),
      bufferMin: _asInt(json['buffer_min']),
      status: _asString(json['status'], 'planned'),
      explanation: json['explanation'] == null
          ? null
          : Explanation.fromJson(_asMap(json['explanation'])),
    );
  }

  final String poiId;
  final String kind;
  final String start;
  final String end;
  final int intensity;
  final int visitMin;
  final int bufferMin;
  final String status;
  final Explanation? explanation;

  Map<String, Object?> toJson() => <String, Object?>{
    'poi_id': poiId,
    'kind': kind,
    'start': start,
    'end': end,
    'intensity': intensity,
    'visit_min': visitMin,
    'buffer_min': bufferMin,
    'status': status,
    if (explanation != null) 'explanation': explanation!.toJson(),
  };
}

class RouteSegment {
  const RouteSegment({
    required this.fromId,
    required this.toId,
    this.mode = 'motorbike',
    this.km = 0,
    this.minutes = 0,
    this.source = 'cache',
    this.confidence = 'medium',
    this.at = '',
  });

  factory RouteSegment.fromJson(Map<String, Object?> json) {
    return RouteSegment(
      fromId: _asString(json['from_id']),
      toId: _asString(json['to_id']),
      mode: _asString(json['mode'], 'motorbike'),
      km: _asDouble(json['km']),
      minutes: _asInt(json['minutes']),
      source: _asString(json['source'], 'cache'),
      confidence: _asString(json['confidence'], 'medium'),
      at: _asString(json['at']),
    );
  }

  final String fromId;
  final String toId;
  final String mode;
  final double km;
  final int minutes;
  final String source;
  final String confidence;
  final String at;

  Map<String, Object?> toJson() => <String, Object?>{
    'from_id': fromId,
    'to_id': toId,
    'mode': mode,
    'km': km,
    'minutes': minutes,
    'source': source,
    'confidence': confidence,
    'at': at,
  };
}

class Explanation {
  const Explanation({
    required this.claim,
    this.evidence = const <String>[],
    this.inference = '',
    this.source = '',
  });

  factory Explanation.fromJson(Map<String, Object?> json) {
    return Explanation(
      claim: _asString(json['claim']),
      evidence: _asStringList(json['evidence']),
      inference: _asString(json['inference']),
      source: _asString(json['source']),
    );
  }

  final String claim;
  final List<String> evidence;
  final String inference;
  final String source;

  Map<String, Object?> toJson() => <String, Object?>{
    'claim': claim,
    'evidence': evidence,
    'inference': inference,
    'source': source,
  };
}

/// `Itinerary` plus the profile-plan decorations the BE attaches.
class Itinerary {
  Itinerary({
    this.itineraryId = '',
    this.tripId = 't1',
    this.version = 1,
    List<Activity>? activities,
    List<RouteSegment>? segments,
    this.totalCost = 0,
    this.totalKm = 0,
    this.totalMin = 0,
    Map<String, Object?>? constraintStatus,
    this.preferenceScore = 0,
    List<Explanation>? explanation,
    this.createdAt = '',
    this.profile = '',
    this.reason = '',
    Map<String, Object?>? scores,
  }) : activities = List<Activity>.unmodifiable(
         activities ?? const <Activity>[],
       ),
       segments = List<RouteSegment>.unmodifiable(
         segments ?? const <RouteSegment>[],
       ),
       constraintStatus = Map<String, Object?>.unmodifiable(
         constraintStatus ?? const <String, Object?>{},
       ),
       explanation = List<Explanation>.unmodifiable(
         explanation ?? const <Explanation>[],
       ),
       scores = Map<String, Object?>.unmodifiable(
         scores ?? const <String, Object?>{},
       );

  factory Itinerary.fromJson(Map<String, Object?> json) {
    // `GET /itinerary/{id}` returns the itinerary at the top level, while a
    // plan entry may nest it under `itinerary`. Flatten the nested form and
    // let top-level fields win.
    var source = json;
    final nested = _asMap(json['itinerary']);
    if (nested.isNotEmpty) {
      source = <String, Object?>{...nested};
      for (final entry in json.entries) {
        if (entry.key != 'itinerary' && entry.value != null) {
          source[entry.key] = entry.value;
        }
      }
    }

    return Itinerary(
      itineraryId: _asString(source['itinerary_id']),
      tripId: _asString(source['trip_id'], 't1'),
      version: _asInt(source['version'], 1),
      activities: _asList(source['activities'])
          .map((item) => Activity.fromJson(_asMap(item)))
          .toList(growable: false),
      segments: _asList(source['segments'])
          .map((item) => RouteSegment.fromJson(_asMap(item)))
          .toList(growable: false),
      totalCost: _asInt(source['total_cost']),
      totalKm: _asDouble(source['total_km']),
      totalMin: _asInt(source['total_min']),
      constraintStatus: _asObjectMap(source['constraint_status']),
      preferenceScore: _asDouble(
        source['preference'] ?? source['preference_score'],
      ),
      explanation: _asList(source['explanation'])
          .map((item) => Explanation.fromJson(_asMap(item)))
          .toList(growable: false),
      createdAt: _asString(source['created_at']),
      profile: _asString(source['profile']),
      reason: _asString(source['reason']),
      scores: _asObjectMap(source['scores']),
    );
  }

  final String itineraryId;
  final String tripId;
  final int version;
  final List<Activity> activities;
  final List<RouteSegment> segments;
  final int totalCost;
  final double totalKm;
  final int totalMin;
  final Map<String, Object?> constraintStatus;
  final double preferenceScore;
  final List<Explanation> explanation;
  final String createdAt;
  final String profile;
  final String reason;
  final Map<String, Object?> scores;

  Map<String, Object?> toJson() => <String, Object?>{
    'itinerary_id': itineraryId,
    'trip_id': tripId,
    'version': version,
    'activities': activities
        .map((activity) => activity.toJson())
        .toList(growable: false),
    'segments': segments
        .map((segment) => segment.toJson())
        .toList(growable: false),
    'total_cost': totalCost,
    'total_km': totalKm,
    'total_min': totalMin,
    'constraint_status': constraintStatus,
    'preference_score': preferenceScore,
    'explanation': explanation
        .map((item) => item.toJson())
        .toList(growable: false),
    'created_at': createdAt,
    if (profile.isNotEmpty) 'profile': profile,
    if (reason.isNotEmpty) 'reason': reason,
    if (scores.isNotEmpty) 'scores': scores,
  };
}

class ParseResult {
  const ParseResult({
    this.trip,
    this.needsClarification = const <String>[],
    this.assumptions = const <String>[],
    this.softPrefs = const <String>[],
    this.hardConstraints = const <String>[],
    this.uncertainties = const <String>[],
  });

  factory ParseResult.fromJson(Map<String, Object?> json) {
    return ParseResult(
      trip: json.containsKey('needs_clarification')
          ? null
          : TripRequest.fromJson(json),
      needsClarification: _asStringList(json['needs_clarification']),
      assumptions: _asStringList(json['assumptions']),
      softPrefs: _asStringList(json['soft_prefs']),
      hardConstraints: _asStringList(json['hard_constraints']),
      uncertainties: _asStringList(json['uncertainties']),
    );
  }

  final TripRequest? trip;
  final List<String> needsClarification;
  final List<String> assumptions;
  final List<String> softPrefs;
  final List<String> hardConstraints;
  final List<String> uncertainties;

  bool get requiresClarification => trip == null;
}

class PlanList {
  const PlanList({
    this.plans = const <Itinerary>[],
    this.selected,
    this.dropped = const <Map<String, Object?>>[],
  });

  factory PlanList.fromJson(Map<String, Object?> json) {
    return PlanList(
      plans: _asList(json['plans'])
          .map((item) => Itinerary.fromJson(_asMap(item)))
          .toList(growable: false),
      selected: _asNullableString(json['selected']),
      dropped: _asList(json['dropped'])
          .map((item) => _asObjectMap(item))
          .toList(growable: false),
    );
  }

  final List<Itinerary> plans;
  final String? selected;
  final List<Map<String, Object?>> dropped;
}

class SelectResult {
  const SelectResult({required this.activeId});

  factory SelectResult.fromJson(Map<String, Object?> json) {
    return SelectResult(activeId: _asString(json['active_id']));
  }

  final String activeId;
}

class ReplanChange {
  const ReplanChange({
    required this.action,
    required this.poiId,
    this.reason = '',
  });

  factory ReplanChange.fromJson(Map<String, Object?> json) {
    return ReplanChange(
      action: _asString(json['action']),
      poiId: _asString(json['poi_id']),
      reason: _asString(json['reason']),
    );
  }

  final String action;
  final String poiId;
  final String reason;

  Map<String, Object?> toJson() => <String, Object?>{
    'action': action,
    'poi_id': poiId,
    if (reason.isNotEmpty) 'reason': reason,
  };
}

class ReplanResult {
  const ReplanResult({
    this.itinerary,
    required this.mode,
    this.changes = const <ReplanChange>[],
    this.reason,
    this.preservedCompleted = const <String>[],
    this.version = 0,
  });

  factory ReplanResult.fromJson(Map<String, Object?> json) {
    final rawItinerary = _asMap(json['itinerary']);
    return ReplanResult(
      itinerary: rawItinerary.isEmpty ? null : Itinerary.fromJson(rawItinerary),
      mode: _asString(json['mode'], 'plan'),
      changes: _asList(json['changes'])
          .map((item) => ReplanChange.fromJson(_asMap(item)))
          .toList(growable: false),
      reason: _asNullableString(json['reason']),
      preservedCompleted: _asStringList(json['preserved_completed']),
      version: _asInt(json['version']),
    );
  }

  final Itinerary? itinerary;
  final String mode;
  final List<ReplanChange> changes;
  final String? reason;
  final List<String> preservedCompleted;
  final int version;
}

class ExpenseEntry {
  const ExpenseEntry({
    required this.tripId,
    required this.label,
    required this.amount,
    required this.kind,
    this.at = '',
  });

  factory ExpenseEntry.fromJson(Map<String, Object?> json) {
    return ExpenseEntry(
      tripId: _asString(json['trip_id']),
      label: _asString(json['label']),
      amount: _asInt(json['amount']),
      kind: _asString(json['kind'], 'other'),
      at: _asString(json['at']),
    );
  }

  final String tripId;
  final String label;
  final int amount;
  final String kind;
  final String at;

  Map<String, Object?> toJson() => <String, Object?>{
    'trip_id': tripId,
    'label': label,
    'amount': amount,
    'kind': kind,
    'at': at,
  };
}

class ExpenseSummary {
  const ExpenseSummary({
    required this.budget,
    required this.spent,
    required this.left,
    this.alert = '',
  });

  factory ExpenseSummary.fromJson(Map<String, Object?> json) {
    return ExpenseSummary(
      budget: _asInt(json['budget'], 3000000),
      spent: _asInt(json['spent']),
      left: _asInt(json['left']),
      alert: _asString(json['alert']),
    );
  }

  final int budget;
  final int spent;
  final int left;
  final String alert;
}

class WeatherHour {
  const WeatherHour({
    required this.at,
    required this.tempC,
    required this.rainProb,
  });

  factory WeatherHour.fromJson(Map<String, Object?> json) {
    return WeatherHour(
      at: _asString(json['at']),
      tempC: _asDouble(json['temp_c']),
      rainProb: _asDouble(json['rain_prob']),
    );
  }

  final String at;
  final double tempC;
  final double rainProb;

  Map<String, Object?> toJson() => <String, Object?>{
    'at': at,
    'temp_c': tempC,
    'rain_prob': rainProb,
  };
}

class WeatherSnapshot {
  WeatherSnapshot({
    this.fetchedAt = '',
    List<WeatherHour>? hourly,
    this.source = '',
    this.stale = false,
    this.staleReason,
  }) : hourly = List<WeatherHour>.unmodifiable(hourly ?? const <WeatherHour>[]);

  factory WeatherSnapshot.fromJson(Map<String, Object?> json) {
    return WeatherSnapshot(
      fetchedAt: _asString(json['fetched_at']),
      hourly: _asList(json['hourly'])
          .map((item) => WeatherHour.fromJson(_asMap(item)))
          .toList(growable: false),
      source: _asString(json['source']),
      stale: _asBool(json['stale']),
      staleReason: _asNullableString(json['stale_reason']),
    );
  }

  final String fetchedAt;
  final List<WeatherHour> hourly;
  final String source;
  final bool stale;
  final String? staleReason;

  Map<String, Object?> toJson() => <String, Object?>{
    'fetched_at': fetchedAt,
    'hourly': hourly.map((hour) => hour.toJson()).toList(growable: false),
    'source': source,
    'stale': stale,
    if (staleReason != null) 'stale_reason': staleReason,
  };
}

class GateReport {
  const GateReport({required this.passed, this.violations = const <String>[]});

  factory GateReport.fromJson(Map<String, Object?> json) {
    return GateReport(
      passed: _asBool(json['passed']),
      violations: _asStringList(json['violations']),
    );
  }

  final bool passed;
  final List<String> violations;
}

class EvaluateResult {
  const EvaluateResult({
    required this.gate,
    this.soft = const <String, double>{},
    this.reward = 0,
  });

  factory EvaluateResult.fromJson(Map<String, Object?> json) {
    return EvaluateResult(
      gate: GateReport.fromJson(_asMap(json['gate'])),
      soft: _asDoubleMap(json['soft']),
      reward: _asDouble(json['reward']),
    );
  }

  final GateReport gate;
  final Map<String, double> soft;
  final double reward;
}

class TransitionScore {
  const TransitionScore({required this.score});

  factory TransitionScore.fromJson(Map<String, Object?> json) {
    return TransitionScore(score: _asDouble(json['score']));
  }

  final double score;
}
