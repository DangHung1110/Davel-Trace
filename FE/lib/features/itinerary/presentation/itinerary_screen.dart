import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../../planning/domain/models.dart';

class ItineraryScreen extends StatelessWidget {
  const ItineraryScreen({
    super.key,
    required this.state,
    required this.onOpenMap,
  });

  final AppState state;
  final VoidCallback onOpenMap;

  Future<void> _tripEditor(BuildContext context, {Trip? trip}) async {
    final data = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => TripEditor(trip: trip),
    );
    if (data == null || !context.mounted) return;
    try {
      if (trip == null) {
        await state.createTrip(data);
      } else {
        await state.updateActiveTrip(data);
      }
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  Future<void> _activityEditor(
    BuildContext context, {
    ActivityItem? activity,
  }) async {
    final data = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => ActivityEditor(state: state, activity: activity),
    );
    if (data == null || !context.mounted) return;
    try {
      await state.saveActivity(existing: activity, data: data);
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  Future<void> _deleteTrip(BuildContext context) async {
    if (!await _confirm(
      context,
      'Xóa chuyến đi?',
      'Lịch trình và chi tiêu của chuyến này cũng sẽ bị xóa.',
    )) {
      return;
    }
    try {
      await state.deleteActiveTrip();
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final trip = state.activeTrip;
    final itinerary = state.itinerary;
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          AppHeader(
            compact: true,
            section: 'Lịch trình',
            trailing: IconButton(
              key: const Key('create-trip-button'),
              tooltip: 'Tạo chuyến đi',
              onPressed: state.isMutating ? null : () => _tripEditor(context),
              icon: const Icon(Icons.add_rounded),
            ),
          ),
          Expanded(
            child: trip == null
                ? _NoTrip(onCreate: () => _tripEditor(context))
                : RefreshIndicator(
                    onRefresh: state.refresh,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(14, 12, 14, 26),
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'ĐÀ NẴNG · HÀNH TRÌNH CỦA BẠN',
                                    style: TextStyle(
                                      color: AppColors.accent,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w800,
                                      letterSpacing: .8,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    trip.title,
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineMedium,
                                  ),
                                ],
                              ),
                            ),
                            PopupMenuButton<String>(
                              tooltip: 'Tùy chọn chuyến đi',
                              onSelected: (value) {
                                if (value == 'edit') {
                                  _tripEditor(context, trip: trip);
                                }
                                if (value == 'delete') {
                                  _deleteTrip(context);
                                }
                              },
                              itemBuilder: (_) => const [
                                PopupMenuItem(
                                  value: 'edit',
                                  child: Text('Sửa chuyến đi'),
                                ),
                                PopupMenuItem(
                                  value: 'delete',
                                  child: Text('Xóa chuyến đi'),
                                ),
                              ],
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        _TripSelector(state: state),
                        const SizedBox(height: 12),
                        _PlanningPanel(state: state),
                        const SizedBox(height: 12),
                        _TripInsightRow(
                          remainingVnd: state.expenseSummary.remainingVnd,
                        ),
                        const SizedBox(height: 12),
                        SurfaceCard(
                          color: AppColors.primary,
                          child: Row(
                            children: [
                              const Icon(
                                Icons.calendar_month_outlined,
                                color: Colors.white,
                              ),
                              const SizedBox(width: 11),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${_shortDate(trip.startDate)} → ${_shortDate(trip.endDate)}',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                    Text(
                                      '${trip.dayStart.substring(0, 5)}–${trip.dayEnd.substring(0, 5)} · ${trip.travelers} người · ${moneyVnd(trip.budgetVnd)}',
                                      style: const TextStyle(
                                        color: Color(0xFFDDE9E4),
                                        fontSize: 11,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                key: const Key('open-trip-map-button'),
                                tooltip: 'Mở bản đồ',
                                onPressed: onOpenMap,
                                icon: const Icon(
                                  Icons.map_outlined,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (itinerary != null &&
                            itinerary.warnings.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          ...itinerary.warnings.map(
                            (warning) => Padding(
                              padding: const EdgeInsets.only(bottom: 6),
                              child: SurfaceCard(
                                color: const Color(0xFFFFF1E3),
                                child: Row(
                                  children: [
                                    const Icon(
                                      Icons.warning_amber_rounded,
                                      color: AppColors.warning,
                                    ),
                                    const SizedBox(width: 9),
                                    Expanded(
                                      child: Text(
                                        warning,
                                        style: const TextStyle(fontSize: 12),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 18),
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                'Điểm nhấn trong ngày',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                            ),
                            Text(
                              'v${itinerary?.version ?? 1}',
                              style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 9),
                        if (itinerary == null || itinerary.activities.isEmpty)
                          const _EmptyActivities()
                        else
                          ...itinerary.activities.indexed.map(
                            (entry) => _ActivityTile(
                              activity: entry.$2,
                              index: entry.$1,
                              busy: state.isMutating,
                              onEdit: () =>
                                  _activityEditor(context, activity: entry.$2),
                              onDelete: () async {
                                if (!await _confirm(
                                  context,
                                  'Xóa hoạt động?',
                                  entry.$2.title,
                                )) {
                                  return;
                                }
                                try {
                                  await state.deleteActivity(entry.$2);
                                } catch (_) {
                                  if (context.mounted) {
                                    _error(context, state.errorMessage);
                                  }
                                }
                              },
                              onMoveUp: entry.$1 == 0
                                  ? null
                                  : () => state.moveActivity(
                                      entry.$1,
                                      entry.$1 - 1,
                                    ),
                              onMoveDown:
                                  entry.$1 == itinerary.activities.length - 1
                                  ? null
                                  : () => state.moveActivity(
                                      entry.$1,
                                      entry.$1 + 1,
                                    ),
                            ),
                          ),
                        const SizedBox(height: 12),
                        FilledButton.icon(
                          key: const Key('add-activity-button'),
                          onPressed: state.isMutating
                              ? null
                              : () => _activityEditor(context),
                          icon: const Icon(Icons.add_location_alt_outlined),
                          label: const Text('Thêm hoạt động thủ công'),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _PlanningPanel extends StatelessWidget {
  const _PlanningPanel({required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) {
    final live = state.demoSource == DemoSource.live;
    final stale = state.demoSource == DemoSource.stale;
    final color = live
        ? const Color(0xFFE6F6F2)
        : stale
        ? const Color(0xFFFFF1E3)
        : const Color(0xFFF2F5F4);
    final title = live
        ? 'Planner trực tiếp · FastAPI'
        : stale
        ? 'Dữ liệu gần nhất · mất kết nối'
        : 'Dữ liệu demo trên thiết bị';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SurfaceCard(
          key: const Key('source-status-banner'),
          color: color,
          padding: const EdgeInsets.all(12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                live ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                color: live ? AppColors.primary : AppColors.warning,
                size: 20,
              ),
              const SizedBox(width: 9),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      state.plannerMessage,
                      style: const TextStyle(fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 9),
        FilledButton.icon(
          key: const Key('request-plan-button'),
          onPressed: state.isPlanning ? null : state.requestPlan,
          icon: Icon(
            state.isPlanning ? Icons.hourglass_top : Icons.alt_route_rounded,
          ),
          label: Text(
            state.isPlanning
                ? 'Đang lập phương án…'
                : 'Tạo 5 phương án khả thi',
          ),
        ),
        const SizedBox(height: 10),
        Text('Phương án', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 6),
        ...state.planAlternatives.map(
          (plan) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _AlternativeCard(
              plan: plan,
              selected: state.activeAlternative?.id == plan.id,
              accepted:
                  state.activeAlternative?.id == plan.id &&
                  state.acceptance != null,
              isLive: live,
              busy: state.isPlanning,
              onSelect: () => state.acceptAlternative(plan),
            ),
          ),
        ),
        if (state.planningReadiness != null)
          Text(
            'Dữ liệu học: ${state.planningReadiness!['pairwise_judgments'] ?? 0}/150 so sánh · '
            '${state.planningReadiness!['accepted_complete_days'] ?? 0}/40 ngày đã chốt',
            style: const TextStyle(color: AppColors.muted, fontSize: 10),
          ),
      ],
    );
  }
}

class _AlternativeCard extends StatelessWidget {
  const _AlternativeCard({
    required this.plan,
    required this.selected,
    required this.accepted,
    required this.isLive,
    required this.busy,
    required this.onSelect,
  });

  final PlanAlternative plan;
  final bool selected;
  final bool accepted;
  final bool isLive;
  final bool busy;
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) => SurfaceCard(
    key: Key('alternative-${plan.id}'),
    color: selected ? const Color(0xFFEAF8F6) : Colors.white,
    padding: const EdgeInsets.all(12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            CircleAvatar(
              radius: 14,
              backgroundColor: AppColors.primary,
              child: Text(
                '${plan.rank}',
                style: const TextStyle(color: Colors.white, fontSize: 11),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                plan.profile,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
            Icon(
              Icons.verified_user_outlined,
              size: 18,
              color: plan.gatePassed ? AppColors.primary : AppColors.error,
            ),
          ],
        ),
        const SizedBox(height: 7),
        Text(
          '${plan.activities.length} điểm · ${plan.totalKm.toStringAsFixed(1)} km · ${moneyVnd(plan.totalCost)}',
          style: const TextStyle(fontSize: 11, color: AppColors.muted),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            key: Key('accept-plan-${plan.id}'),
            onPressed: busy ? null : onSelect,
            child: Text(
              accepted
                  ? 'Đã lưu lựa chọn'
                  : selected && !isLive
                  ? 'Đã chọn cục bộ'
                  : 'Chọn phương án',
            ),
          ),
        ),
      ],
    ),
  );
}

class _NoTrip extends StatelessWidget {
  const _NoTrip({required this.onCreate});
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.luggage_outlined,
            color: AppColors.primary,
            size: 54,
          ),
          const SizedBox(height: 16),
          Text(
            'Chưa có chuyến đi',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 6),
          const Text(
            'Tạo chuyến Đà Nẵng một hoặc hai ngày, sau đó tự thêm hoạt động.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            key: const Key('empty-create-trip-button'),
            onPressed: onCreate,
            icon: const Icon(Icons.add_rounded),
            label: const Text('Tạo chuyến đầu tiên'),
          ),
        ],
      ),
    ),
  );
}

class _TripSelector extends StatelessWidget {
  const _TripSelector({required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => DropdownButtonFormField<String>(
    key: const Key('trip-switcher'),
    isExpanded: true,
    initialValue: state.activeTrip!.id,
    decoration: const InputDecoration(
      labelText: 'Chuyến đi đang quản lý',
      prefixIcon: Icon(Icons.route_outlined),
    ),
    items: state.trips
        .map(
          (trip) => DropdownMenuItem(value: trip.id, child: Text(trip.title)),
        )
        .toList(),
    onChanged: state.isMutating
        ? null
        : (id) {
            if (id == null || id == state.activeTrip!.id) return;
            state.selectTrip(state.trips.firstWhere((trip) => trip.id == id));
          },
  );
}

class _TripInsightRow extends StatelessWidget {
  const _TripInsightRow({required this.remainingVnd});

  final int remainingVnd;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      const Expanded(
        child: _InsightPill(
          icon: Icons.wb_sunny_outlined,
          iconColor: AppColors.secondary,
          title: '28°C',
          subtitle: 'Trời ấm, có gió',
        ),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _InsightPill(
          icon: Icons.account_balance_wallet_outlined,
          iconColor: AppColors.primary,
          title: moneyVnd(remainingVnd),
          subtitle: 'Ngân sách còn lại',
        ),
      ),
    ],
  );
}

class _InsightPill extends StatelessWidget {
  const _InsightPill({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(18),
      boxShadow: const [
        BoxShadow(
          color: Color(0x0D006A6A),
          blurRadius: 12,
          offset: Offset(0, 4),
        ),
      ],
    ),
    child: Row(
      children: [
        Icon(icon, size: 19, color: iconColor),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 9),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _EmptyActivities extends StatelessWidget {
  const _EmptyActivities();

  @override
  Widget build(BuildContext context) => const SurfaceCard(
    color: AppColors.softSurface,
    child: Row(
      children: [
        Icon(Icons.edit_calendar_outlined, color: AppColors.primary),
        SizedBox(width: 12),
        Expanded(
          child: Text(
            'Lịch đang trống. Bạn có thể chọn POI trong catalog hoặc nhập địa điểm riêng.',
          ),
        ),
      ],
    ),
  );
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({
    required this.activity,
    required this.index,
    required this.busy,
    required this.onEdit,
    required this.onDelete,
    required this.onMoveUp,
    required this.onMoveDown,
  });

  final ActivityItem activity;
  final int index;
  final bool busy;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback? onMoveUp;
  final VoidCallback? onMoveDown;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 20,
          child: Column(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: index == 0 ? AppColors.secondary : AppColors.primary,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.surface, width: 3),
                  boxShadow: const [
                    BoxShadow(color: Color(0x33006A6A), blurRadius: 3),
                  ],
                ),
              ),
              Container(width: 2, height: 104, color: AppColors.sand),
            ],
          ),
        ),
        const SizedBox(width: 4),
        Expanded(
          child: SurfaceCard(
            padding: const EdgeInsets.all(10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 72,
                  height: 82,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: index.isEven
                          ? const [Color(0xFFB9E5E4), Color(0xFF5AAEAA)]
                          : const [Color(0xFFFFD9B0), Color(0xFFD97706)],
                    ),
                  ),
                  child: Stack(
                    children: [
                      Center(
                        child: Icon(
                          _activityIcon(activity.category),
                          color: Colors.white,
                          size: 30,
                        ),
                      ),
                      Positioned(
                        top: 7,
                        left: 7,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 7,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.primary,
                            borderRadius: BorderRadius.circular(99),
                          ),
                          child: Text(
                            '${index + 1}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${_clock(activity.startAt)} · ${activity.category.toUpperCase()}',
                        style: const TextStyle(
                          color: AppColors.secondary,
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        activity.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.ink,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        activity.notes.isEmpty
                            ? '${_clock(activity.startAt)}–${_clock(activity.endAt)}'
                            : activity.notes,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 10),
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              moneyVnd(activity.estimatedCostVnd),
                              style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          _MiniIcon(
                            icon: Icons.arrow_upward_rounded,
                            tooltip: 'Đưa lên',
                            onPressed: busy ? null : onMoveUp,
                          ),
                          _MiniIcon(
                            icon: Icons.arrow_downward_rounded,
                            tooltip: 'Đưa xuống',
                            onPressed: busy ? null : onMoveDown,
                          ),
                          _MiniIcon(
                            icon: Icons.edit_outlined,
                            tooltip: 'Sửa',
                            onPressed: busy ? null : onEdit,
                          ),
                          _MiniIcon(
                            icon: Icons.delete_outline,
                            tooltip: 'Xóa',
                            onPressed: busy ? null : onDelete,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class _MiniIcon extends StatelessWidget {
  const _MiniIcon({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });
  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => IconButton(
    constraints: const BoxConstraints.tightFor(width: 27, height: 30),
    padding: EdgeInsets.zero,
    visualDensity: VisualDensity.compact,
    tooltip: tooltip,
    onPressed: onPressed,
    icon: Icon(icon, size: 18),
  );
}

IconData _activityIcon(String category) => switch (category) {
  'food' => Icons.restaurant_rounded,
  'transport' => Icons.directions_bike_rounded,
  'ticket' => Icons.local_activity_rounded,
  _ => Icons.place_rounded,
};

class TripEditor extends StatefulWidget {
  const TripEditor({super.key, this.trip});
  final Trip? trip;

  @override
  State<TripEditor> createState() => _TripEditorState();
}

class _TripEditorState extends State<TripEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _budget;
  late final TextEditingController _travelers;
  late DateTime _start;
  late int _days;
  late String _transport;

  @override
  void initState() {
    super.initState();
    final trip = widget.trip;
    _title = TextEditingController(text: trip?.title ?? 'Cuối tuần ở Đà Nẵng');
    _budget = TextEditingController(text: '${trip?.budgetVnd ?? 3000000}');
    _travelers = TextEditingController(text: '${trip?.travelers ?? 2}');
    final now = DateTime.now();
    _start =
        trip?.startDate ??
        DateTime(now.year, now.month, now.day).add(const Duration(days: 1));
    _days = trip == null
        ? 2
        : trip.endDate.difference(trip.startDate).inDays + 1;
    _transport = trip?.transport ?? 'motorbike';
  }

  @override
  void dispose() {
    _title.dispose();
    _budget.dispose();
    _travelers.dispose();
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.pop(context, {
      'title': _title.text.trim(),
      'start_date': isoDate(_start),
      'end_date': isoDate(_start.add(Duration(days: _days - 1))),
      'day_start': '07:00:00',
      'day_end': '21:00:00',
      'travelers': int.parse(_travelers.text),
      'budget_vnd': int.parse(_budget.text),
      'transport': _transport,
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      18,
      4,
      18,
      MediaQuery.viewInsetsOf(context).bottom + 18,
    ),
    child: SingleChildScrollView(
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.trip == null ? 'Tạo chuyến Đà Nẵng' : 'Sửa chuyến đi',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
            TextFormField(
              key: const Key('trip-title-field'),
              controller: _title,
              decoration: const InputDecoration(labelText: 'Tên chuyến đi'),
              validator: _required,
            ),
            const SizedBox(height: 10),
            InkWell(
              onTap: () async {
                final picked = await showDatePicker(
                  context: context,
                  initialDate: _start,
                  firstDate: DateTime(2024),
                  lastDate: DateTime(2035),
                );
                if (picked != null) setState(() => _start = picked);
              },
              child: InputDecorator(
                decoration: const InputDecoration(labelText: 'Ngày bắt đầu'),
                child: Text(_shortDate(_start)),
              ),
            ),
            const SizedBox(height: 10),
            SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 1, label: Text('1 ngày')),
                ButtonSegment(value: 2, label: Text('2 ngày')),
              ],
              selected: {_days},
              onSelectionChanged: (value) =>
                  setState(() => _days = value.first),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _travelers,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Số người'),
                    validator: _positive,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    controller: _budget,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Ngân sách (VND)',
                    ),
                    validator: _nonNegative,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _transport,
              decoration: const InputDecoration(labelText: 'Di chuyển'),
              items: const [
                DropdownMenuItem(value: 'motorbike', child: Text('Xe máy')),
                DropdownMenuItem(value: 'car', child: Text('Ô tô')),
                DropdownMenuItem(value: 'walking', child: Text('Đi bộ')),
              ],
              onChanged: (value) => setState(() => _transport = value!),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                key: const Key('save-trip-button'),
                onPressed: _save,
                child: const Text('Lưu chuyến đi'),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class ActivityEditor extends StatefulWidget {
  const ActivityEditor({super.key, required this.state, this.activity});
  final AppState state;
  final ActivityItem? activity;

  @override
  State<ActivityEditor> createState() => _ActivityEditorState();
}

class _ActivityEditorState extends State<ActivityEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _notes;
  late final TextEditingController _lat;
  late final TextEditingController _lon;
  late final TextEditingController _time;
  late final TextEditingController _duration;
  late final TextEditingController _cost;
  final _search = TextEditingController();
  String? _poiId;
  String _category = 'visit';
  List<PoiItem> _results = [];
  bool _searching = false;

  @override
  void initState() {
    super.initState();
    final item = widget.activity;
    _title = TextEditingController(text: item?.title ?? '');
    _notes = TextEditingController(text: item?.notes ?? '');
    _lat = TextEditingController(text: '${item?.latitude ?? 16.0544}');
    _lon = TextEditingController(text: '${item?.longitude ?? 108.2022}');
    _time = TextEditingController(
      text: item == null ? '09:00' : _clock(item.startAt),
    );
    _duration = TextEditingController(
      text:
          '${item == null ? 60 : item.endAt.difference(item.startAt).inMinutes}',
    );
    _cost = TextEditingController(text: '${item?.estimatedCostVnd ?? 0}');
    _poiId = item?.poiId;
    _category = item?.category ?? 'visit';
  }

  @override
  void dispose() {
    for (final controller in [
      _title,
      _notes,
      _lat,
      _lon,
      _time,
      _duration,
      _cost,
      _search,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _findPoi() async {
    setState(() => _searching = true);
    try {
      _results = await widget.state.searchPois(_search.text.trim());
    } catch (_) {
      _results = [];
    }
    if (mounted) setState(() => _searching = false);
  }

  void _selectPoi(PoiItem poi) {
    setState(() {
      _poiId = poi.id;
      _title.text = poi.name;
      _lat.text = '${poi.latitude}';
      _lon.text = '${poi.longitude}';
      _results = [];
    });
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    final parts = _time.text.split(':');
    final tripDate = widget.state.activeTrip!.startDate;
    final start = DateTime(
      tripDate.year,
      tripDate.month,
      tripDate.day,
      int.parse(parts[0]),
      int.parse(parts[1]),
    );
    final end = start.add(Duration(minutes: int.parse(_duration.text)));
    Navigator.pop(context, {
      'poi_id': _poiId,
      'title': _title.text.trim(),
      'notes': _notes.text.trim(),
      'latitude': double.parse(_lat.text),
      'longitude': double.parse(_lon.text),
      'start_at': start.toIso8601String(),
      'end_at': end.toIso8601String(),
      'category': _category,
      'estimated_cost_vnd': int.parse(_cost.text),
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      18,
      4,
      18,
      MediaQuery.viewInsetsOf(context).bottom + 18,
    ),
    child: SingleChildScrollView(
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.activity == null ? 'Thêm hoạt động' : 'Sửa hoạt động',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            const Text(
              'Tìm POI có sẵn hoặc nhập địa điểm riêng.',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('poi-search-field'),
                    controller: _search,
                    decoration: const InputDecoration(
                      labelText: 'Tìm POI',
                      hintText: 'Cầu Rồng, biển, cà phê…',
                    ),
                    onSubmitted: (_) => _findPoi(),
                  ),
                ),
                const SizedBox(width: 7),
                IconButton.filledTonal(
                  key: const Key('search-poi-button'),
                  onPressed: _searching ? null : _findPoi,
                  icon: _searching
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.search_rounded),
                ),
              ],
            ),
            if (_results.isNotEmpty)
              Container(
                constraints: const BoxConstraints(maxHeight: 180),
                margin: const EdgeInsets.only(top: 6),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  border: Border.all(color: AppColors.outline),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _results.length,
                  itemBuilder: (_, index) {
                    final poi = _results[index];
                    return ListTile(
                      dense: true,
                      title: Text(poi.name),
                      subtitle: Text(poi.type),
                      trailing: poi.verified
                          ? const Icon(Icons.verified, size: 16)
                          : null,
                      onTap: () => _selectPoi(poi),
                    );
                  },
                ),
              ),
            const SizedBox(height: 10),
            TextFormField(
              key: const Key('activity-title-field'),
              controller: _title,
              decoration: const InputDecoration(labelText: 'Tên địa điểm'),
              validator: _required,
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _lat,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    decoration: const InputDecoration(labelText: 'Vĩ độ'),
                    validator: _coordinate,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    controller: _lon,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    decoration: const InputDecoration(labelText: 'Kinh độ'),
                    validator: _coordinate,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _time,
                    decoration: const InputDecoration(
                      labelText: 'Bắt đầu',
                      hintText: '09:00',
                    ),
                    validator: _timeValidator,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    controller: _duration,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Số phút'),
                    validator: _positive,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _category,
                    decoration: const InputDecoration(labelText: 'Loại'),
                    items: const [
                      DropdownMenuItem(
                        value: 'visit',
                        child: Text('Tham quan'),
                      ),
                      DropdownMenuItem(value: 'food', child: Text('Ăn uống')),
                      DropdownMenuItem(
                        value: 'transport',
                        child: Text('Di chuyển'),
                      ),
                      DropdownMenuItem(value: 'ticket', child: Text('Vé')),
                    ],
                    onChanged: (value) => setState(() => _category = value!),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextFormField(
                    controller: _cost,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Dự chi (VND)',
                    ),
                    validator: _nonNegative,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _notes,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Ghi chú'),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                key: const Key('save-activity-button'),
                onPressed: _save,
                child: const Text('Lưu hoạt động'),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

String? _required(String? value) =>
    value == null || value.trim().isEmpty ? 'Không được để trống' : null;
String? _positive(String? value) {
  final number = int.tryParse(value ?? '');
  return number == null || number < 1 ? 'Nhập số lớn hơn 0' : null;
}

String? _nonNegative(String? value) {
  final number = int.tryParse(value ?? '');
  return number == null || number < 0 ? 'Nhập số từ 0' : null;
}

String? _coordinate(String? value) =>
    double.tryParse(value ?? '') == null ? 'Tọa độ không hợp lệ' : null;
String? _timeValidator(String? value) {
  final match = RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(value ?? '');
  return match ? null : 'Dùng HH:mm';
}

String _shortDate(DateTime value) =>
    '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';
String _clock(DateTime value) =>
    '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';

Future<bool> _confirm(
  BuildContext context,
  String title,
  String message,
) async =>
    await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xác nhận'),
          ),
        ],
      ),
    ) ??
    false;

void _error(BuildContext context, String? message) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message ?? 'Không thể hoàn tất thao tác.')),
  );
}
