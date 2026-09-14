import 'package:flutter/material.dart';

import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';

class ItineraryScreen extends StatefulWidget {
  const ItineraryScreen({super.key});

  @override
  State<ItineraryScreen> createState() => _ItineraryScreenState();
}

class _ItineraryScreenState extends State<ItineraryScreen> {
  final _interests = <String>{'Ẩm thực', 'Biển'};

  static const _activities = [
    _Activity(
      time: '07:30',
      duration: '3 giờ',
      title: 'Bán đảo Sơn Trà',
      subtitle: 'Leo núi nhẹ · Ngắm cảnh',
      icon: Icons.landscape_outlined,
      color: AppColors.success,
    ),
    _Activity(
      time: '11:30',
      duration: '1 giờ',
      title: 'Mì Quảng Bà Mua',
      subtitle: 'Ăn trưa · 4.5 ★',
      icon: Icons.restaurant_outlined,
      color: AppColors.amber,
    ),
    _Activity(
      time: '15:30',
      duration: '2 giờ 30',
      title: 'Bãi biển Mỹ Khê',
      subtitle: 'Tắm biển · Ngắm hoàng hôn',
      icon: Icons.beach_access_outlined,
      color: AppColors.blue,
    ),
  ];

  void _generatePlan() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Đã tạo lịch trình mẫu cho một ngày ở Đà Nẵng.'),
      ),
    );
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
              TextButton(onPressed: () {}, child: const Text('Chỉnh sửa')),
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
          onPressed: () {},
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
        const Text('Cho chúng tôi biết thời gian và điều bạn yêu thích.'),
        const SizedBox(height: 18),
        const Row(
          children: [
            Expanded(
              child: TextField(
                readOnly: true,
                decoration: InputDecoration(
                  labelText: 'Ngày bắt đầu',
                  hintText: '20/09/2026',
                  prefixIcon: Icon(Icons.calendar_today_outlined),
                ),
              ),
            ),
            SizedBox(width: 12),
            Expanded(
              child: TextField(
                readOnly: true,
                decoration: InputDecoration(
                  labelText: 'Số ngày',
                  hintText: '1 ngày',
                  prefixIcon: Icon(Icons.schedule_outlined),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        const TextField(
          decoration: InputDecoration(
            labelText: 'Điểm xuất phát',
            hintText: 'Khách sạn hoặc vị trí của bạn',
            prefixIcon: Icon(Icons.location_on_outlined),
          ),
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
              child: Text('Tạo lịch trình'),
            ),
          ),
        ),
      ],
    );
  }
}

class _TimelineTile extends StatelessWidget {
  const _TimelineTile({required this.activity, required this.isLast});

  final _Activity activity;
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
                        const Icon(Icons.more_horiz, color: AppColors.muted),
                        const SizedBox(height: 8),
                        Text(
                          activity.duration,
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

class _Activity {
  const _Activity({
    required this.time,
    required this.duration,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
  });

  final String time;
  final String duration;
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
}
