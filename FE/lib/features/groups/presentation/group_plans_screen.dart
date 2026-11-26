import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/errors/api_exception.dart';
import '../../management/domain/models.dart';
import '../../map/presentation/map_screen.dart';
import '../../map/presentation/map_stop.dart';
import '../data/group_repository.dart';
import 'group_shared.dart';

const _profiles = {
  'fast': 'Đi được nhiều điểm',
  'balanced': 'Cân bằng',
  'relaxed': 'Thư thả',
  'relax': 'Thư thả',
  'family': 'Phù hợp gia đình',
  'budget': 'Tiết kiệm',
  'economy': 'Tiết kiệm',
  'savings': 'Tiết kiệm',
};

class GroupPlansScreen extends StatefulWidget {
  const GroupPlansScreen({
    super.key,
    required this.group,
    required this.onOpenPlanning,
  });
  final GroupState group;
  final Future<void> Function() onOpenPlanning;

  @override
  State<GroupPlansScreen> createState() => _GroupPlansScreenState();
}

class _GroupPlansScreenState extends State<GroupPlansScreen> {
  GroupState get group => widget.group;
  Json? _plans;
  bool _loading = false;
  bool _busy = false;
  String? _failure;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
  }

  Future<void> _refresh() async {
    if (_loading || _busy) return;
    _loading = true;
    try {
      final result = await group.repository.get(group.tripId, '/plans');
      if (mounted) {
        setState(() {
          _plans = result;
          _failure = null;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          if (error is ApiException &&
              {401, 403, 404}.contains(error.statusCode)) {
            _plans = null;
          }
          _failure = groupError(error);
        });
      }
    } finally {
      _loading = false;
    }
  }

  Future<void> _choose(Json round, Json alternative, bool selected) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final result = await group.repository.put(
        group.tripId,
        '/plans/${round['id']}/vote',
        {'alternative_id': selected ? null : alternative['id']},
      );
      if (mounted) {
        setState(() {
          _plans = result;
          _failure = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _accept(Json alternative) async {
    final agreed = await confirmGroupAction(
      context,
      title: 'Chốt lịch cho cả nhóm?',
      description:
          'Cả nhóm sẽ xem lịch mới và nhận cập nhật trong cuộc trò chuyện.',
      action: 'Chốt lịch',
    );
    if (!agreed || !mounted || _busy) return;
    setState(() => _busy = true);
    try {
      await group.repository.acceptPlan(textField(alternative, 'id'));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Đã chốt lịch cho cả nhóm.')),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        await _refresh();
      }
    }
  }

  Future<void> _openPlanner() async {
    try {
      await widget.onOpenPlanning();
      if (mounted) await _refresh();
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    }
  }

  void _details(Json plan, {required String title, required bool active}) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _GroupPlanDetail(
          group: group,
          plan: plan,
          title: title,
          active: active,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final current = jsonObject(_plans?['active']);
    final round = jsonObject(_plans?['round']);
    final alternatives = jsonObjects(round['alternatives']);
    final chosen = round['my_vote'];
    final isLeader = group.isLeader && group.canEdit;
    return GroupPolling(
      onRefresh: _refresh,
      child: Scaffold(
        appBar: AppBar(title: const Text('Lịch của nhóm')),
        body: SafeArea(
          bottom: false,
          child: _plans == null && _failure == null
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                    children: [
                      if (_failure case String failure)
                        GroupProblem(message: failure, onRetry: _refresh),
                      Text(
                        'Lịch đang dùng',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      if (current.isEmpty)
                        const Text('Nhóm trưởng chưa chốt lịch cho chuyến này.')
                      else
                        ListTile(
                          key: const Key('open-group-active-plan'),
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.event_available_outlined),
                          title: const Text('Lịch đã chốt'),
                          subtitle: Text(
                            '${jsonObjects(current['activities']).length} hoạt động',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => _details(
                            current,
                            title: 'Lịch đã chốt',
                            active: true,
                          ),
                        ),
                      if (alternatives.isNotEmpty) ...[
                        const SizedBox(height: 24),
                        Text(
                          'Phương án để góp ý',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Mỗi người có một lượt chọn. Nhóm trưởng chốt lịch sau khi xem góp ý.',
                        ),
                        for (final alternative in alternatives) ...[
                          const SizedBox(height: 12),
                          const Divider(height: 1),
                          _PlanOption(
                            plan: alternative,
                            chosen: alternative['id'] == chosen,
                            onOpen: () => _details(
                              alternative,
                              title: _planName(alternative),
                              active: false,
                            ),
                            onVote: _busy || !group.canEdit
                                ? null
                                : () => _choose(
                                    round,
                                    alternative,
                                    alternative['id'] == chosen,
                                  ),
                            onAccept: !isLeader || _busy
                                ? null
                                : () => _accept(alternative),
                          ),
                        ],
                      ] else if (round['status'] == 'running') ...[
                        const SizedBox(height: 24),
                        const LinearProgressIndicator(),
                        const SizedBox(height: 8),
                        const Text('Đang tạo phương án cho cả nhóm…'),
                      ] else if (round['status'] == 'failed') ...[
                        const SizedBox(height: 24),
                        const GroupStatus(
                          icon: Icons.info_outline,
                          text: 'Chưa có phương án phù hợp. Nhóm trưởng có thể điều chỉnh điều kiện hoặc giờ đi rồi thử lại.',
                        ),
                      ],
                    ],
                  ),
                ),
        ),
        bottomNavigationBar: !isLeader
            ? null
            : GroupActions(
                children: [
                  FilledButton.icon(
                    key: const Key('open-group-planner'),
                    onPressed: _busy ? null : _openPlanner,
                    icon: Icon(
                      current.isEmpty
                          ? Icons.calendar_month_outlined
                          : Icons.edit_calendar_outlined,
                    ),
                    label: Text(
                      current.isEmpty ? 'Lập lịch cho nhóm' : 'Đổi kế hoạch',
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

String _planName(Json plan) {
  final profile = textField(plan, 'profile');
  final rank = integerField(plan, 'rank');
  return _profiles[profile] ??
      (rank > 0 ? 'Phương án $rank' : 'Phương án gợi ý');
}

class _PlanOption extends StatelessWidget {
  const _PlanOption({
    required this.plan,
    required this.chosen,
    required this.onOpen,
    this.onVote,
    this.onAccept,
  });
  final Json plan;
  final bool chosen;
  final VoidCallback onOpen;
  final VoidCallback? onVote;
  final VoidCallback? onAccept;

  @override
  Widget build(BuildContext context) {
    final id = textField(plan, 'id');
    final count = integerField(plan, 'vote_count');
    final activities = jsonObjects(plan['activities']);
    final costs = integerField(plan, 'total_cost_vnd');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            key: ValueKey('open-group-alternative-$id'),
            contentPadding: EdgeInsets.zero,
            title: Text(
              _planName(plan),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            subtitle: Text(
              '${activities.length} hoạt động · Dự kiến ${moneyVnd(costs)}',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: onOpen,
          ),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              OutlinedButton.icon(
                key: ValueKey('vote-group-alternative-$id'),
                onPressed: onVote,
                icon: Icon(
                  chosen ? Icons.check_circle : Icons.how_to_vote_outlined,
                  size: 18,
                ),
                label: Text(chosen ? 'Đã chọn · $count' : 'Bình chọn · $count'),
              ),
              if (onAccept != null)
                TextButton(
                  key: ValueKey('accept-group-alternative-$id'),
                  onPressed: onAccept,
                  child: const Text('Chốt lịch này'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _GroupPlanDetail extends StatelessWidget {
  const _GroupPlanDetail({
    required this.group,
    required this.plan,
    required this.title,
    required this.active,
  });
  final GroupState group;
  final Json plan;
  final String title;
  final bool active;

  Future<void> _onMap(BuildContext context, int day, List<Json> points) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _GroupRouteScreen(
          group: group,
          title: title,
          id: textField(plan, 'id'),
          day: day,
          points: points,
          active: active,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final activities = jsonObjects(plan['activities']);
    final days = <int, List<Json>>{};
    for (final activity in activities) {
      days.putIfAbsent(integerField(activity, 'day'), () => []).add(activity);
    }
    final dated = days.keys.toList()..sort();
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            Text(
              '${activities.length} hoạt động',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (!active)
              Text('Dự kiến ${moneyVnd(integerField(plan, 'total_cost_vnd'))}'),
            const SizedBox(height: 12),
            for (final (index, day) in dated.indexed) ...[
              const SizedBox(height: 12),
              Text(
                'Ngày ${index + 1}${textField(days[day]!.first, 'date').isEmpty ? '' : ' · ${groupDate(textField(days[day]!.first, 'date'))}'}',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              for (final activity in days[day]!)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(switch (activity['status']) {
                    'completed' => Icons.check_circle_outline,
                    'skipped' => Icons.do_not_disturb_on_outlined,
                    _ => Icons.place_outlined,
                  }),
                  title: Text(textField(activity, 'name')),
                  subtitle: Text(
                    '${groupClock(textField(activity, 'start'))} – ${groupClock(textField(activity, 'end'))}${switch (activity['status']) {
                      'completed' => ' · Đã đi',
                      'skipped' => ' · Đã bỏ qua',
                      _ => '',
                    }}',
                  ),
                ),
              if (days[day]!
                  .where((point) => point['status'] != 'skipped')
                  .any(
                    (point) =>
                        point['poi_id'] != null ||
                        (point['lat'] != null && point['lon'] != null),
                  ))
                OutlinedButton.icon(
                  key: ValueKey('open-group-route-$day'),
                  onPressed: () => _onMap(context, day, days[day]!),
                  icon: const Icon(Icons.map_outlined),
                  label: const Text('Xem trên bản đồ'),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _GroupRouteScreen extends StatefulWidget {
  const _GroupRouteScreen({
    required this.group,
    required this.title,
    required this.id,
    required this.day,
    required this.points,
    required this.active,
  });

  final GroupState group;
  final String title;
  final String id;
  final int day;
  final List<Json> points;
  final bool active;

  @override
  State<_GroupRouteScreen> createState() => _GroupRouteScreenState();
}

class _GroupRouteScreenState extends State<_GroupRouteScreen> {
  late final _map = _load();

  int _minutes(String value) {
    final parts = value.split(':');
    if (parts.length < 2) return 0;
    return (int.tryParse(parts[0]) ?? 0) * 60 + (int.tryParse(parts[1]) ?? 0);
  }

  Future<MapStop?> _point(Json point, int index) async {
    final poi = textField(point, 'poi_id');
    final start = groupClock(textField(point, 'start'));
    final end = groupClock(textField(point, 'end'));
    var lat = (point['lat'] as num?)?.toDouble();
    var lon = (point['lon'] as num?)?.toDouble();
    var name = textField(point, 'name');
    if ((lat == null || lon == null) && poi.isNotEmpty) {
      try {
        final place = await widget.group.repository.place(poi);
        lat = place.latitude;
        lon = place.longitude;
        if (name.isEmpty) name = place.name;
      } catch (_) {
        return null;
      }
    }
    if (lat == null || lon == null) return null;
    final stop = MapStop(
      id: textField(point, 'id').isEmpty
          ? 'group-stop-$index'
          : textField(point, 'id'),
      title: name,
      subtitle: '',
      time: start,
      durationMinutes: math.max(0, _minutes(end) - _minutes(start)),
      latitude: lat,
      longitude: lon,
      icon: Icons.place_outlined,
      color: Colors.blue,
    );
    return stop.hasLocation ? stop : null;
  }

  Future<(List<MapStop>, RoutePreviewData)> _load() async {
    final group = widget.group;
    final actionable = widget.points
        .where((point) => point['status'] != 'skipped')
        .toList();
    final stops = (await Future.wait(
      actionable.indexed.map((entry) => _point(entry.$2, entry.$1)),
    )).whereType<MapStop>().toList();
    if (stops.length >= 2) {
      try {
        final map = await group.repository.post(group.tripId, '/plans/route', {
          'plan_id': widget.id,
          'day': widget.day,
        });
        final preview = RoutePreviewData.fromJson(map);
        if (preview.geometry.isNotEmpty) return (stops, preview);
      } catch (_) {
        // The known points still support a visibly approximate connection.
      }
    }
    return (
      stops,
      RoutePreviewData(
        source: 'catalog',
        isRealRoute: false,
        distanceM: 0,
        durationS: 0,
        quality: stops.length < 2 ? 'unavailable' : 'interpolated',
        geometry: stops.length < 2
            ? const []
            : [
                for (final stop in stops) [stop.longitude, stop.latitude],
              ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: FutureBuilder<(List<MapStop>, RoutePreviewData)>(
        future: _map,
        builder: (context, snapshot) {
          if (snapshot.data case final map?) {
            return MapScreen(
              stops: map.$1,
              planRevision: 0,
              routePreview: map.$2,
              tripTitle: widget.title,
              isDraft: !widget.active,
              onOpenItinerary: () => Navigator.pop(context),
            );
          }
          return Column(
            children: [
              AppBar(title: Text(widget.title)),
              Expanded(
                child: Center(
                  child: snapshot.hasError
                      ? const Text('Chưa tải được bản đồ.')
                      : const CircularProgressIndicator(
                          semanticsLabel: 'Đang tải bản đồ',
                        ),
                ),
              ),
            ],
          );
        },
      ),
    ),
  );
}
