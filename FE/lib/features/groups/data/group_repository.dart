import '../../../core/networking/api_client.dart';
import '../../management/domain/models.dart';

typedef Json = Map<String, dynamic>;

Json jsonObject(Object? value) => value is Map ? Json.from(value) : {};
List<Json> jsonObjects(Object? value) =>
    value is List ? value.whereType<Map>().map(Json.from).toList() : [];
String textField(Json value, String key) => value[key]?.toString() ?? '';
int integerField(Json value, String key) => (value[key] as num?)?.round() ?? 0;

class GroupRepository {
  const GroupRepository(this.api);

  final ApiClient api;

  static const _base = '/v1/trip-groups';

  Future<List<Json>> list() async =>
      jsonObjects(jsonObject(await api.get(_base))['items']);

  Future<Json> enable(String trip) async =>
      jsonObject(await api.put('$_base/$trip'));

  Future<Json> join(String code, String displayName) async => jsonObject(
    await api.post(
      '$_base/join',
      body: {
        'code': code,
        if (displayName.isNotEmpty) 'display_name': displayName,
      },
    ),
  );

  Future<Json> get(String trip, [String path = '']) async =>
      jsonObject(await api.get('$_base/$trip$path'));

  Future<void> acceptPlan(String alternativeId) async {
    await api.post(
      '/v1/itinerary-alternatives/$alternativeId/accept',
      headers: {'Idempotency-Key': 'group-accept-$alternativeId'},
    );
  }

  Future<Json> post(String trip, String path, [Json? body]) async =>
      jsonObject(await api.post('$_base/$trip$path', body: body));

  Future<Json> put(String trip, String path, Json body) async =>
      jsonObject(await api.put('$_base/$trip$path', body: body));

  Future<Json> patch(String trip, String path, Json body) async =>
      jsonObject(await api.patch('$_base/$trip$path', body: body));

  Future<Json> createExpense(String trip, Json body, String key) async =>
      jsonObject(
        await api.post(
          '$_base/$trip/expenses',
          body: body,
          headers: {'Idempotency-Key': key},
        ),
      );

  Future<Json> delete(String trip, String path) async =>
      jsonObject(await api.delete('$_base/$trip$path'));

  Future<Json> chat(String trip, {String? before}) async => jsonObject(
    await api.get(
      '$_base/$trip/chat',
      query: {'limit': '30', 'before': ?before},
    ),
  );

  Future<List<PoiItem>> places(String query) async {
    final response = jsonObject(
      await api.get('/v1/pois', query: {'q': query, 'limit': '15'}),
    );
    return jsonObjects(response['items']).map(PoiItem.fromJson).toList();
  }

  Future<PoiItem> place(String id) async => PoiItem.fromJson(
    jsonObject(await api.get('/v1/pois/${Uri.encodeComponent(id)}')),
  );
}
