import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../../../app_state.dart';
import '../../../core/errors/api_exception.dart';
import '../../../core/networking/api_client.dart';
import '../../management/domain/models.dart';
import '../../map/domain/location_state.dart';

class GroupReplanScreen extends StatefulWidget {
  const GroupReplanScreen({
    super.key,
    required this.state,
    required this.api,
    required this.trip,
    this.location = const GeolocatorMapLocationProvider(),
  });

  final AppState state;
  final ApiClient api;
  final Trip trip;
  final MapLocationProvider location;

  @override
  State<GroupReplanScreen> createState() => _GroupReplanScreenState();
}

typedef _Place = ({String id, String label, String? context});
typedef _ReplanData = ({Map<String, dynamic>? active, _Place? meeting});

class _GroupReplanScreenState extends State<GroupReplanScreen> {
  final _query = TextEditingController();
  final _progress = <String, String>{};
  late Future<_ReplanData> _active;
  late DateTime _day;
  late TimeOfDay _time;
  List<_Place> _places = [];
  _Place? _place;
  bool _looking = false;
  bool _submitting = false;
  bool _keepPlace = false;
  String? _placeMessage;

  @override
  void initState() {
    super.initState();
    final local = DateTime.now().toUtc().add(const Duration(hours: 7));
    final today = DateUtils.dateOnly(local);
    final start = DateUtils.dateOnly(widget.trip.startDate);
    final end = DateUtils.dateOnly(widget.trip.endDate);
    _day = today.isBefore(start)
        ? start
        : today.isAfter(end)
        ? end
        : today;
    final opening = widget.trip.dayStart.split(':');
    _time = _day == today
        ? TimeOfDay.fromDateTime(local)
        : TimeOfDay(hour: int.parse(opening[0]), minute: int.parse(opening[1]));
    _active = _load();
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<_ReplanData> _load() async {
    final path = '/v1/trip-groups/${widget.trip.id}';
    final results = await Future.wait([
      widget.api.get('$path/plans'),
      widget.api.get(path),
    ]);
    final plans = results[0] as Map;
    final detail = results[1] as Map;
    final meeting = detail['pinned_meeting'] as Map?;
    final meetingId = meeting?['poi_id'] as String?;
    return (
      active: (plans['active'] as Map?)?.cast<String, dynamic>(),
      meeting: meetingId == null
          ? null
          : (
              id: meetingId,
              label: meeting?['place_name'] as String? ?? 'Điểm hẹn',
              context: null,
            ),
    );
  }

  Future<void> _find({bool nearby = false}) async {
    if (_looking) return;
    final query = _query.text.trim();
    if (!nearby && query.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _looking = true;
      _placeMessage = null;
      _places = [];
    });
    try {
      if (nearby) {
        final result = await widget.location.currentLocation();
        if (!mounted) return;
        final fix = result.location;
        if (fix == null || !fix.isValid) {
          setState(
            () => _placeMessage =
                '${mapLocationMessage(result.status)} Bạn vẫn có thể tìm theo tên.',
          );
          return;
        }
        final response = await widget.api.get('/v1/pois/location-index') as Map;
        final rows = (response['items'] as List).cast<Map>();
        final nearest = [
          for (final row in rows)
            if (row['lat'] is num && row['lon'] is num)
              (
                row: row,
                meters: Geolocator.distanceBetween(
                  fix.latitude,
                  fix.longitude,
                  (row['lat'] as num).toDouble(),
                  (row['lon'] as num).toDouble(),
                ),
              ),
        ]..sort((a, b) => a.meters.compareTo(b.meters));
        if (!mounted) return;
        setState(
          () => _places = [
            for (final item
                in nearest.where((item) => item.meters <= 1500).take(6))
              (
                id: item.row['poi_id'] as String,
                label: item.row['name'] as String,
                context: 'Cách vị trí của bạn khoảng ${item.meters.round()} m',
              ),
          ],
        );
      } else {
        final places = await widget.state.searchPois(query);
        if (!mounted) return;
        setState(
          () => _places = [
            for (final item in places.take(8))
              (id: item.id, label: item.name, context: null),
          ],
        );
      }
      if (mounted && _places.isEmpty) {
        setState(
          () => _placeMessage =
              'Chưa tìm thấy điểm phù hợp. Thử tìm theo tên khác.',
        );
      }
    } catch (_) {
      if (mounted) {
        setState(() => _placeMessage = 'Chưa tải được địa điểm. Hãy thử lại.');
      }
    } finally {
      if (mounted) setState(() => _looking = false);
    }
  }

  Future<void> _submit(String source) async {
    final place = _place;
    if (place == null ||
        _submitting ||
        widget.state.activeTrip?.id != widget.trip.id) {
      return;
    }
    setState(() => _submitting = true);
    final time =
        '${_time.hour.toString().padLeft(2, '0')}:${_time.minute.toString().padLeft(2, '0')}';
    await widget.state.requestReplan(
      sourceVersionId: source,
      completedActivityIds: [
        for (final item in _progress.entries)
          if (item.value == 'completed') item.key,
      ],
      skippedActivityIds: [
        for (final item in _progress.entries)
          if (item.value == 'skipped') item.key,
      ],
      currentPoiId: place.id,
      remainingFrom: '${isoDate(_day)}T$time:00+07:00',
      includeCurrentStop: _keepPlace,
    );
    if (!mounted) return;
    if (widget.state.errorMessage == null) {
      Navigator.of(context).pop();
    } else {
      setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Đổi kế hoạch')),
    body: FutureBuilder<_ReplanData>(
      future: _active,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError || snapshot.data?.active == null) {
          final error = snapshot.error;
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                error is ApiException
                    ? error.message
                    : 'Cần có lịch đã chốt trước khi lập lại phần còn lại.',
              ),
              if (snapshot.hasError)
                TextButton(
                  onPressed: () => setState(() => _active = _load()),
                  child: const Text('Thử lại'),
                ),
            ],
          );
        }
        final data = snapshot.data!;
        final active = data.active!;
        final stops = (active['activities'] as List? ?? []).cast<Map>();
        return SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: [
              Text(
                'Cả nhóm bắt đầu từ đâu?',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 6),
              const Text(
                'Chọn nơi cả nhóm đang ở hoặc điểm hẹn. Vị trí GPS chỉ dùng trên thiết bị để tìm các điểm gần bạn.',
              ),
              const SizedBox(height: 16),
              if (data.meeting case final meeting?)
                OutlinedButton.icon(
                  onPressed: _submitting
                      ? null
                      : () => setState(() {
                          _place = meeting;
                          _keepPlace = false;
                          _places = [];
                          _placeMessage = null;
                        }),
                  icon: const Icon(Icons.flag_outlined),
                  label: Text('Dùng điểm hẹn · ${meeting.label}'),
                ),
              if (data.meeting != null) const SizedBox(height: 10),
              TextField(
                key: const Key('group-replan-place-search'),
                controller: _query,
                maxLength: 120,
                enabled: !_submitting,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _find(),
                decoration: InputDecoration(
                  labelText: 'Tên địa điểm',
                  counterText: '',
                  suffixIcon: IconButton(
                    tooltip: 'Tìm địa điểm',
                    onPressed: _looking || _submitting ? null : () => _find(),
                    icon: const Icon(Icons.search),
                  ),
                ),
              ),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  key: const Key('group-replan-near-me'),
                  onPressed: _looking || _submitting
                      ? null
                      : () => _find(nearby: true),
                  icon: const Icon(Icons.my_location_outlined),
                  label: const Text('Tìm điểm gần tôi'),
                ),
              ),
              if (_looking) const LinearProgressIndicator(),
              if (_placeMessage != null) Text(_placeMessage!),
              for (final place in _places)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(place.label),
                  subtitle: place.context == null ? null : Text(place.context!),
                  trailing: const Icon(Icons.add_location_alt_outlined),
                  onTap: _submitting
                      ? null
                      : () => setState(() {
                          _place = place;
                          _places = [];
                        }),
                ),
              if (_place case final place?)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.place_outlined),
                  title: Text(place.label),
                  subtitle: const Text('Điểm xuất phát cả nhóm đã chọn'),
                  trailing: IconButton(
                    tooltip: 'Đổi điểm xuất phát',
                    onPressed: _submitting
                        ? null
                        : () => setState(() {
                            _place = null;
                            _keepPlace = false;
                          }),
                    icon: const Icon(Icons.close),
                  ),
                ),
              if (_place != null)
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: _keepPlace,
                  onChanged: _submitting
                      ? null
                      : (value) => setState(() => _keepPlace = value ?? false),
                  title: const Text(
                    'Thêm nơi này làm điểm dừng trong lịch mới',
                  ),
                ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.calendar_today_outlined),
                title: const Text('Ngày bắt đầu lại'),
                subtitle: Text('${_day.day}/${_day.month}/${_day.year}'),
                onTap: _submitting
                    ? null
                    : () async {
                        final date = await showDatePicker(
                          context: context,
                          initialDate: _day,
                          firstDate: DateUtils.dateOnly(widget.trip.startDate),
                          lastDate: DateUtils.dateOnly(widget.trip.endDate),
                        );
                        if (mounted && date != null) {
                          setState(() => _day = date);
                        }
                      },
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.schedule_outlined),
                title: const Text('Giờ bắt đầu lại'),
                subtitle: Text(_time.format(context)),
                onTap: _submitting
                    ? null
                    : () async {
                        final time = await showTimePicker(
                          context: context,
                          initialTime: _time,
                        );
                        if (mounted && time != null) {
                          setState(() => _time = time);
                        }
                      },
              ),
              if (stops.isNotEmpty) ...[
                const SizedBox(height: 14),
                Text(
                  'Những điểm đã đi',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const Text(
                  'Đánh dấu các điểm đã ghé hoặc muốn bỏ qua trước khi tính lịch mới.',
                ),
                for (final stop in stops) _stopRow(stop),
              ],
              if (widget.state.errorMessage case final error?)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    error,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              const SizedBox(height: 12),
              FilledButton(
                key: const Key('group-replan-submit'),
                onPressed: _place == null || _submitting
                    ? null
                    : () => _submit(active['id'] as String),
                child: Text(
                  _submitting ? 'Đang tính lịch…' : 'Tạo phương án để nhóm xem',
                ),
              ),
            ],
          ),
        );
      },
    ),
  );

  Widget _stopRow(Map stop) {
    final id = stop['id'] as String;
    final saved = (stop['status'] as String?) ?? 'planned';
    final value = _progress[id] ?? saved;
    String label(String state) => switch (state) {
      'completed' => 'Đã ghé',
      'skipped' => 'Bỏ qua',
      _ => 'Còn trong lịch',
    };
    final date = DateTime.tryParse(stop['date']?.toString() ?? '');
    final start = stop['start'] as String?;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(stop['name'] as String? ?? 'Điểm dừng'),
      subtitle: Text(
        [
          if (date != null) '${date.day}/${date.month}',
          if (start != null && start.isNotEmpty) start,
          label(value),
        ].join(' · '),
      ),
      trailing: saved == 'completed' || saved == 'skipped'
          ? null
          : PopupMenuButton<String>(
              enabled: !_submitting,
              tooltip: 'Đổi trạng thái điểm dừng',
              onSelected: (value) => setState(() => _progress[id] = value),
              itemBuilder: (_) => [
                for (final state in ['planned', 'completed', 'skipped'])
                  PopupMenuItem(value: state, child: Text(label(state))),
              ],
            ),
    );
  }
}
