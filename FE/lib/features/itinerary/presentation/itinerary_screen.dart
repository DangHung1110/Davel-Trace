import 'package:flutter/material.dart';

import '../../../shared/widgets/surface_card.dart';
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
  int _dayCount = 1;
  TripStop _origin = DemoTripData.defaultOrigin;
  List<TripStop> _activities = DemoTripData.activities;

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
        .where((activity) => _interests.contains(activity.interest))
        .toList();

    if (selectedActivities.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Hãy chọn ít nhất một sở thích.')),
      );
      return;
    }

    setState(() => _activities = selectedActivities);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Đã tạo lịch trình mock ${selectedActivities.length} địa điểm.',
        ),
      ),
    );
    widget.onPlanGenerated([_origin, ...selectedActivities]);
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(context),
          const SizedBox(height: 24),
          SurfaceCard(child: _buildPlannerForm(context)),
          const SizedBox(height: 26),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Lịch trình gợi ý',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text('${_activities.length} địa điểm'),
            ],
          ),
          const SizedBox(height: 8),
          ..._activities.indexed.map(
            (entry) => _TimelineTile(
              activity: entry.$2,
              isLast: entry.$1 == _activities.length - 1,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF246BFD), Color(0xFF6B8CFF)],
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: const Icon(Icons.route, color: Colors.white),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Davel Trace',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const Text('Khám phá Đà Nẵng theo cách của bạn'),
            ],
          ),
        ),
        IconButton.filledTonal(
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Bạn chưa có thông báo mới.')),
            );
          },
          icon: const Icon(Icons.notifications_none_rounded),
        ),
      ],
    );
  }

  Widget _buildPlannerForm(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Tạo chuyến đi mới',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 6),
        const Text('Chọn thông tin để thử tạo lịch trình bằng dữ liệu mock.'),
        const SizedBox(height: 18),
        Row(
          children: [
            Expanded(
              child: InkWell(
                key: const Key('start-date-field'),
                onTap: _pickDate,
                borderRadius: BorderRadius.circular(14),
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Ngày bắt đầu',
                    prefixIcon: Icon(Icons.calendar_today_outlined),
                  ),
                  child: Text(_formattedDate),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DropdownButtonFormField<int>(
                initialValue: _dayCount,
                decoration: const InputDecoration(
                  labelText: 'Số ngày',
                  prefixIcon: Icon(Icons.schedule_outlined),
                ),
                items: [1, 2, 3]
                    .map(
                      (days) => DropdownMenuItem(
                        value: days,
                        child: Text('$days ngày'),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _dayCount = value ?? 1),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<TripStop>(
          initialValue: _origin,
          decoration: const InputDecoration(
            labelText: 'Điểm xuất phát',
            prefixIcon: Icon(Icons.location_on_outlined),
          ),
          items: DemoTripData.origins
              .map(
                (origin) =>
                    DropdownMenuItem(value: origin, child: Text(origin.title)),
              )
              .toList(),
          onChanged: (value) {
            if (value != null) setState(() => _origin = value);
          },
        ),
        const SizedBox(height: 18),
        const Text(
          'Bạn quan tâm điều gì?',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: ['Ẩm thực', 'Biển', 'Thiên nhiên', 'Văn hóa'].map((
            interest,
          ) {
            final selected = _interests.contains(interest);
            return FilterChip(
              selected: selected,
              label: Text(interest),
              onSelected: (value) => setState(() {
                value ? _interests.add(interest) : _interests.remove(interest);
              }),
            );
          }).toList(),
        ),
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            key: const Key('generate-plan-button'),
            onPressed: _generatePlan,
            icon: const Icon(Icons.auto_awesome),
            label: const Padding(
              padding: EdgeInsets.symmetric(vertical: 14),
              child: Text('Tạo lịch trình & xem bản đồ'),
            ),
          ),
        ),
      ],
    );
  }
}

class _TimelineTile extends StatelessWidget {
  const _TimelineTile({required this.activity, required this.isLast});

  final TripStop activity;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 54,
            child: Column(
              children: [
                Text(
                  activity.time,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: activity.color,
                    shape: BoxShape.circle,
                  ),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(width: 2, color: const Color(0xFFDDE3ED)),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: SurfaceCard(
                padding: const EdgeInsets.all(15),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: activity.color.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: Icon(activity.icon, color: activity.color),
                    ),
                    const SizedBox(width: 13),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            activity.title,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 4),
                          Text(activity.subtitle),
                        ],
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        const Icon(
                          Icons.check_circle,
                          color: AppColors.success,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          activity.durationLabel,
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
