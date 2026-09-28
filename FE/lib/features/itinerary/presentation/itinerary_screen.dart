import 'package:flutter/material.dart';

import '../../../shared/widgets/app_header.dart';
import '../../../theme/app_theme.dart';
import '../domain/demo_trip.dart';

class ItineraryScreen extends StatefulWidget {
  const ItineraryScreen({super.key, required this.onPlanGenerated});

  final ValueChanged<List<TripStop>> onPlanGenerated;

  @override
  State<ItineraryScreen> createState() => _ItineraryScreenState();
}

class _ItineraryScreenState extends State<ItineraryScreen> {
  final _interests = <String>{'Ẩm thực', 'Biển'};
  DateTime _startDate = DateTime(2026, 9, 20);
  int _dayCount = 3;
  TripStop _origin = DemoTripData.defaultOrigin;
  List<TripStop> _activities = List.of(DemoTripData.activities);
  final Set<String> _selectedIds = DemoTripData.activities
      .map((e) => e.id)
      .toSet();

  String get _formattedDate =>
      '${_startDate.day.toString().padLeft(2, '0')}/'
      '${_startDate.month.toString().padLeft(2, '0')}/${_startDate.year}';

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime(2026),
      lastDate: DateTime(2028),
    );
    if (selected != null) setState(() => _startDate = selected);
  }

  void _generatePlan() {
    final selectedActivities = DemoTripData.activities
        .where(
          (activity) =>
              _interests.contains(activity.interest) &&
              _selectedIds.contains(activity.id),
        )
        .toList();
    if (selectedActivities.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Hãy chọn ít nhất một sở thích và địa điểm.'),
        ),
      );
      return;
    }
    setState(() => _activities = selectedActivities);
    widget.onPlanGenerated([_origin, ...selectedActivities]);
  }

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          const AppHeader(compact: true),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _PlannerCard(
                    formattedDate: _formattedDate,
                    dayCount: _dayCount,
                    origin: _origin,
                    interests: _interests,
                    onPickDate: _pickDate,
                    onDayChanged: (value) => setState(() => _dayCount = value),
                    onOriginChanged: (value) => setState(() => _origin = value),
                    onInterestChanged: (interest, selected) => setState(() {
                      selected
                          ? _interests.add(interest)
                          : _interests.remove(interest);
                    }),
                    onGenerate: _generatePlan,
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Lịch trình gợi ý',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const _TinyPill(label: 'Ngày 1', color: AppColors.sky),
                      TextButton.icon(
                        onPressed: () => setState(
                          () => _activities = _activities.reversed.toList(),
                        ),
                        icon: const Icon(Icons.swap_vert_rounded, size: 15),
                        label: const Text('Sắp xếp'),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.blue,
                          minimumSize: Size.zero,
                          padding: const EdgeInsets.symmetric(horizontal: 6),
                          textStyle: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  ..._activities.indexed.map(
                    (entry) => _TimelineTile(
                      activity: entry.$2,
                      selected: _selectedIds.contains(entry.$2.id),
                      isLast: entry.$1 == _activities.length - 1,
                      onTap: () => setState(() {
                        final id = entry.$2.id;
                        _selectedIds.contains(id)
                            ? _selectedIds.remove(id)
                            : _selectedIds.add(id);
                      }),
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
}

class _PlannerCard extends StatelessWidget {
  const _PlannerCard({
    required this.formattedDate,
    required this.dayCount,
    required this.origin,
    required this.interests,
    required this.onPickDate,
    required this.onDayChanged,
    required this.onOriginChanged,
    required this.onInterestChanged,
    required this.onGenerate,
  });

  final String formattedDate;
  final int dayCount;
  final TripStop origin;
  final Set<String> interests;
  final VoidCallback onPickDate;
  final ValueChanged<int> onDayChanged;
  final ValueChanged<TripStop> onOriginChanged;
  final void Function(String, bool) onInterestChanged;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.softSurface,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.auto_awesome,
                  color: AppColors.blue,
                  size: 14,
                ),
              ),
              const SizedBox(width: 8),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'Davel Trace',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        SizedBox(width: 5),
                        _TinyPill(label: 'Đề xuất', color: Color(0xFFDDE7FF)),
                      ],
                    ),
                    Text(
                      'Khám phá Đà Nẵng theo cách của bạn',
                      style: TextStyle(fontSize: 8, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
              IconButton.filled(
                onPressed: () {},
                style: IconButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: AppColors.blue,
                ),
                icon: const Icon(Icons.notifications_none_rounded, size: 17),
              ),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            'TRỢ LÝ LẬP TRÌNH AI',
            style: TextStyle(
              fontSize: 8,
              color: AppColors.blue,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            'Tạo chuyến đi mới',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const Text(
            'Chọn thông tin để tạo lịch trình phù hợp.',
            style: TextStyle(fontSize: 9),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: InkWell(
                  key: const Key('start-date-field'),
                  onTap: onPickDate,
                  borderRadius: BorderRadius.circular(12),
                  child: InputDecorator(
                    decoration: const InputDecoration(
                      labelText: 'Khởi hành',
                      prefixIcon: Icon(Icons.calendar_today_outlined, size: 16),
                    ),
                    child: Text(
                      formattedDate,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Thời gian',
                    prefixIcon: Icon(Icons.schedule_outlined, size: 16),
                  ),
                  child: Text(
                    '$dayCount ngày ${dayCount > 1 ? dayCount - 1 : 0} đêm',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            'Số ngày trải nghiệm',
            style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          Row(
            children: [1, 2, 3, 4].map((day) {
              final selected = dayCount == day;
              return Expanded(
                child: Padding(
                  padding: EdgeInsets.only(right: day == 4 ? 0 : 6),
                  child: ChoiceChip(
                    selected: selected,
                    showCheckmark: false,
                    label: SizedBox(
                      width: double.infinity,
                      child: Text(
                        day == 4 ? '4+\nngày' : '$day\nngày',
                        textAlign: TextAlign.center,
                      ),
                    ),
                    onSelected: (_) => onDayChanged(day),
                    selectedColor: AppColors.blue,
                    backgroundColor: Colors.white,
                    labelStyle: TextStyle(
                      color: selected ? Colors.white : AppColors.navy,
                      fontSize: 9,
                      height: 1.1,
                    ),
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<TripStop>(
            initialValue: origin,
            isDense: true,
            decoration: const InputDecoration(
              labelText: 'Điểm xuất phát',
              prefixIcon: Icon(Icons.location_on_outlined, size: 17),
            ),
            items: DemoTripData.origins
                .map(
                  (item) => DropdownMenuItem(
                    value: item,
                    child: Text(
                      item.title,
                      style: const TextStyle(fontSize: 11),
                    ),
                  ),
                )
                .toList(),
            onChanged: (value) {
              if (value != null) onOriginChanged(value);
            },
          ),
          const SizedBox(height: 10),
          const Text(
            'Sở thích trải nghiệm (chọn nhiều)',
            style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children:
                const {
                  'Ẩm thực': Icons.restaurant_outlined,
                  'Biển': Icons.beach_access_outlined,
                  'Thiên nhiên': Icons.landscape_outlined,
                  'Văn hóa': Icons.museum_outlined,
                }.entries.map((entry) {
                  final selected = interests.contains(entry.key);
                  return FilterChip(
                    selected: selected,
                    label: Text(entry.key),
                    avatar: Icon(
                      entry.value,
                      size: 13,
                      color: selected ? Colors.white : AppColors.blue,
                    ),
                    onSelected: (value) => onInterestChanged(entry.key, value),
                    selectedColor: AppColors.blue,
                    backgroundColor: Colors.white,
                    labelStyle: TextStyle(
                      color: selected ? Colors.white : AppColors.navy,
                    ),
                    visualDensity: VisualDensity.compact,
                  );
                }).toList(),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              key: const Key('generate-plan-button'),
              onPressed: onGenerate,
              icon: const Icon(Icons.auto_awesome, size: 15),
              label: const Padding(
                padding: EdgeInsets.symmetric(vertical: 11),
                child: Text('Tạo lịch trình & xem bản đồ'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineTile extends StatelessWidget {
  const _TimelineTile({
    required this.activity,
    required this.selected,
    required this.isLast,
    required this.onTap,
  });

  final TripStop activity;
  final bool selected;
  final bool isLast;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 26,
            child: Column(
              children: [
                GestureDetector(
                  onTap: onTap,
                  child: Container(
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      color: selected ? AppColors.success : AppColors.outline,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      selected ? Icons.check : Icons.add,
                      color: Colors.white,
                      size: 13,
                    ),
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(width: 2, color: const Color(0xFFD5D9E4)),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(15),
                border: Border.all(color: AppColors.outline),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _TinyPill(label: activity.time, color: AppColors.sky),
                      const SizedBox(width: 5),
                      const Icon(
                        Icons.schedule,
                        size: 10,
                        color: AppColors.muted,
                      ),
                      const SizedBox(width: 2),
                      Text(
                        activity.durationLabel,
                        style: const TextStyle(fontSize: 8),
                      ),
                      const Spacer(),
                      const Icon(
                        Icons.star_rounded,
                        size: 13,
                        color: AppColors.amber,
                      ),
                      Text(
                        '${activity.rating ?? 4.5}',
                        style: const TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(width: 3),
                      const Icon(
                        Icons.more_vert_rounded,
                        size: 16,
                        color: AppColors.muted,
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: SizedBox(
                          width: 62,
                          height: 58,
                          child: Image.network(
                            activity.imageUrl,
                            fit: BoxFit.cover,
                            errorBuilder: (_, error, stackTrace) => ColoredBox(
                              color: activity.color.withValues(alpha: .14),
                              child: Icon(activity.icon, color: activity.color),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              activity.title,
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              activity.subtitle,
                              style: const TextStyle(fontSize: 8),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 5),
                            Wrap(
                              spacing: 4,
                              runSpacing: 3,
                              children: [
                                ...activity.tags.map(
                                  (tag) => _TinyPill(
                                    label: tag,
                                    color: AppColors.softSurface,
                                  ),
                                ),
                                if (activity.priceLabel case final price?)
                                  _TinyPill(
                                    label: price,
                                    color: const Color(0xFFFFF1D8),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
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

class _TinyPill extends StatelessWidget {
  const _TinyPill({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700),
      ),
    );
  }
}
