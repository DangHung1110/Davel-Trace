import 'package:flutter/material.dart';

import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../domain/demo_trip.dart';

enum PlannerView {
  onboarding,
  planner,
  clarification,
  feasibility,
  comparison,
  itinerary,
  poi,
  replan,
}

class ItineraryScreen extends StatelessWidget {
  const ItineraryScreen({
    super.key,
    required this.view,
    required this.onViewChanged,
    required this.onPlanGenerated,
    required this.onStartTrip,
  });

  final PlannerView view;
  final ValueChanged<PlannerView> onViewChanged;
  final ValueChanged<List<TripStop>> onPlanGenerated;
  final VoidCallback onStartTrip;

  @override
  Widget build(BuildContext context) => switch (view) {
    PlannerView.onboarding => _Onboarding(
      onContinue: () => onViewChanged(PlannerView.planner),
    ),
    PlannerView.planner => _Planner(
      onCreate: () => onViewChanged(PlannerView.clarification),
      onOpenCached: () => onPlanGenerated(DemoTripData.defaultRoute),
    ),
    PlannerView.clarification => _Clarification(
      onBack: () => onViewChanged(PlannerView.planner),
      onContinue: () => onViewChanged(PlannerView.feasibility),
    ),
    PlannerView.feasibility => _Feasibility(
      onContinue: () => onViewChanged(PlannerView.comparison),
    ),
    PlannerView.comparison => _PlanComparison(
      onSelect: () => onPlanGenerated(DemoTripData.defaultRoute),
    ),
    PlannerView.itinerary => _ItineraryDetail(
      onOpenPoi: () => onViewChanged(PlannerView.poi),
      onOpenReplan: () => onViewChanged(PlannerView.replan),
      onStartTrip: onStartTrip,
    ),
    PlannerView.poi => _PoiDetail(
      onBack: () => onViewChanged(PlannerView.itinerary),
      onDirections: onStartTrip,
    ),
    PlannerView.replan => _Replan(
      onBack: () => onViewChanged(PlannerView.itinerary),
      onApply: () => onPlanGenerated(DemoTripData.defaultRoute),
    ),
  };
}

class _Onboarding extends StatefulWidget {
  const _Onboarding({required this.onContinue});
  final VoidCallback onContinue;

  @override
  State<_Onboarding> createState() => _OnboardingState();
}

class _OnboardingState extends State<_Onboarding> {
  String _pace = 'Cân bằng';
  final _needs = <String>{'Đi bộ vừa phải'};

  @override
  Widget build(BuildContext context) => _Page(
    showHeader: false,
    children: [
      const SizedBox(height: 18),
      const _BrandMark(),
      const SizedBox(height: 30),
      const _Eyebrow('HỒ SƠ DU LỊCH · 2/5'),
      const SizedBox(height: 8),
      Text('Hiểu gu du hành', style: Theme.of(context).textTheme.displaySmall),
      const SizedBox(height: 8),
      const Text(
        'Một vài lựa chọn ngắn giúp lịch trình vừa sức và đúng nhịp của bạn.',
        style: TextStyle(color: AppColors.muted, height: 1.5),
      ),
      const SizedBox(height: 22),
      const _SectionTitle('Bạn thích nhịp đi như thế nào?'),
      const SizedBox(height: 10),
      ...['Thong thả', 'Cân bằng', 'Khám phá nhiều'].map(
        (value) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: _SelectionTile(
            title: value,
            subtitle: switch (value) {
              'Thong thả' => 'Ít điểm, nhiều thời gian nghỉ',
              'Cân bằng' => 'Đủ trải nghiệm, vẫn có khoảng thở',
              _ => 'Tối ưu số điểm trong một ngày',
            },
            selected: _pace == value,
            onTap: () => setState(() => _pace = value),
          ),
        ),
      ),
      const SizedBox(height: 12),
      const _SectionTitle('Điều gì cần được ưu tiên?'),
      const SizedBox(height: 10),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: ['Đi bộ vừa phải', 'Có thời gian nghỉ', 'Không dậy quá sớm']
            .map(
              (value) => FilterChip(
                selected: _needs.contains(value),
                label: Text(value),
                onSelected: (selected) => setState(() {
                  selected ? _needs.add(value) : _needs.remove(value);
                }),
              ),
            )
            .toList(),
      ),
      const SizedBox(height: 20),
      const SurfaceCard(
        color: AppColors.softSurface,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.auto_awesome_rounded, color: AppColors.accent),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'Davel sẽ ghi nhớ hồ sơ này và giải thích vì sao từng gợi ý phù hợp.',
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 22),
      FilledButton(
        key: const Key('onboarding-continue-button'),
        onPressed: widget.onContinue,
        child: const Text('Lưu hồ sơ & tiếp tục'),
      ),
    ],
  );
}

class _Planner extends StatefulWidget {
  const _Planner({required this.onCreate, required this.onOpenCached});
  final VoidCallback onCreate;
  final VoidCallback onOpenCached;

  @override
  State<_Planner> createState() => _PlannerState();
}

class _PlannerState extends State<_Planner> {
  final _promptController = TextEditingController(
    text: 'Một ngày Đà Nẵng có biển, đồ ăn ngon và ngắm cảnh.',
  );
  final _interests = <String>{'Biển', 'Ẩm thực'};

  @override
  void dispose() {
    _promptController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Lập kế hoạch',
    children: [
      Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _Eyebrow('TRỢ LÝ DU LỊCH AI'),
                const SizedBox(height: 5),
                Text(
                  'Đi đâu hôm nay?',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
              ],
            ),
          ),
          const _WeatherBadge(),
        ],
      ),
      const SizedBox(height: 8),
      const Text(
        'Kể bằng cách tự nhiên, Davel sẽ hỏi lại khi còn thiếu dữ kiện.',
      ),
      const SizedBox(height: 18),
      TextField(
        controller: _promptController,
        minLines: 3,
        maxLines: 5,
        decoration: const InputDecoration(
          labelText: 'Bạn muốn chuyến đi như thế nào?',
          alignLabelWithHint: true,
        ),
      ),
      const SizedBox(height: 12),
      const Row(
        children: [
          Expanded(
            child: _InfoField(
              icon: Icons.schedule_rounded,
              label: '09:00 · 1 ngày',
            ),
          ),
          SizedBox(width: 8),
          Expanded(
            child: _InfoField(icon: Icons.people_outline, label: '2 người'),
          ),
        ],
      ),
      const SizedBox(height: 8),
      const Row(
        children: [
          Expanded(
            child: _InfoField(icon: Icons.near_me_outlined, label: 'Cầu Rồng'),
          ),
          SizedBox(width: 8),
          Expanded(
            child: _InfoField(
              icon: Icons.wallet_outlined,
              label: '4.000.000 ₫',
            ),
          ),
        ],
      ),
      const SizedBox(height: 18),
      const _SectionTitle('Ưu tiên trải nghiệm'),
      const SizedBox(height: 8),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: ['Biển', 'Ẩm thực', 'Thiên nhiên', 'Văn hóa'].map((value) {
          final selected = _interests.contains(value);
          return FilterChip(
            selected: selected,
            label: Text(value),
            onSelected: (checked) => setState(() {
              checked ? _interests.add(value) : _interests.remove(value);
            }),
          );
        }).toList(),
      ),
      const SizedBox(height: 20),
      FilledButton.icon(
        key: const Key('generate-plan-button'),
        onPressed: widget.onCreate,
        icon: const Icon(Icons.auto_awesome_rounded, size: 18),
        label: const Text('Tạo lịch trình khả thi'),
      ),
      const SizedBox(height: 24),
      Row(
        children: [
          const Expanded(child: _SectionTitle('Lịch trình gần đây')),
          TextButton(
            onPressed: widget.onOpenCached,
            child: const Text('Mở lại'),
          ),
        ],
      ),
      SurfaceCard(
        child: InkWell(
          onTap: widget.onOpenCached,
          child: const Row(
            children: [
              _DateTile(),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Đà Nẵng chậm mà chất',
                      style: TextStyle(fontWeight: FontWeight.w800),
                    ),
                    SizedBox(height: 4),
                    Text(
                      '4 điểm · Đã lưu lúc 08:30',
                      style: TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    ],
  );
}

class _Clarification extends StatefulWidget {
  const _Clarification({required this.onBack, required this.onContinue});
  final VoidCallback onBack;
  final VoidCallback onContinue;

  @override
  State<_Clarification> createState() => _ClarificationState();
}

class _ClarificationState extends State<_Clarification> {
  String _time = '09:00';

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Làm rõ yêu cầu',
    leadingBack: widget.onBack,
    children: [
      const _Eyebrow('CÒN 1 CÂU HỎI'),
      const SizedBox(height: 7),
      Text(
        'Bạn muốn bắt đầu lúc nào?',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      const Text(
        'Giờ khởi hành ảnh hưởng trực tiếp tới giờ mở cửa, thời tiết và quãng đường.',
      ),
      const SizedBox(height: 20),
      ...['07:30', '09:00', '14:00'].map(
        (value) => Padding(
          padding: const EdgeInsets.only(bottom: 9),
          child: _SelectionTile(
            title: value,
            subtitle: switch (value) {
              '07:30' => 'Mát hơn, có thể ghé Sơn Trà sớm',
              '09:00' => 'Cân bằng và phù hợp hồ sơ của bạn',
              _ => 'Rút gọn lịch trình, ưu tiên biển và ẩm thực',
            },
            selected: _time == value,
            onTap: () => setState(() => _time = value),
          ),
        ),
      ),
      const SizedBox(height: 12),
      const SurfaceCard(
        color: AppColors.softSurface,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Eyebrow('GIẢ ĐỊNH HỆ THỐNG'),
            SizedBox(height: 8),
            Text('• Di chuyển bằng xe máy hoặc taxi'),
            Text('• Không có yêu cầu hỗ trợ tiếp cận đặc biệt'),
            Text('• Chi phí chưa gồm khách sạn'),
          ],
        ),
      ),
      const SizedBox(height: 22),
      FilledButton(
        key: const Key('clarification-confirm-button'),
        onPressed: widget.onContinue,
        child: const Text('Xác nhận & kiểm tra khả thi'),
      ),
    ],
  );
}

class _Feasibility extends StatelessWidget {
  const _Feasibility({required this.onContinue});
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Kiểm tra khả thi',
    children: [
      const _Eyebrow('FEASIBILITY GATE'),
      const SizedBox(height: 7),
      Text(
        'Lịch trình đã vượt qua kiểm tra',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      const Text(
        'Davel chỉ so sánh các phương án sau khi những ràng buộc chính đã hợp lệ.',
      ),
      const SizedBox(height: 20),
      const SurfaceCard(
        child: Column(
          children: [
            _CheckRow(
              'Hiểu đúng yêu cầu',
              'Đủ thời gian, ngân sách và sở thích',
            ),
            _CheckRow(
              'Lọc địa điểm phù hợp',
              '8 ứng viên → 5 địa điểm đạt yêu cầu',
            ),
            _CheckRow(
              'Kiểm tra giờ mở cửa',
              '4 đã xác minh · 1 cần kiểm tra lại',
            ),
            _CheckRow(
              'Ước lượng đường đi & chi phí',
              'OSRM · 28 km · trong ngân sách',
            ),
            _CheckRow(
              'Tạo 3 hồ sơ kế hoạch',
              'Tiết kiệm · Cân bằng · Trải nghiệm',
              last: true,
            ),
          ],
        ),
      ),
      const SizedBox(height: 14),
      const _Notice(
        icon: Icons.info_outline_rounded,
        text: 'Giờ đông khách của Bé Mặn là suy luận từ dữ liệu tham khảo, chưa phải dữ kiện xác minh.',
      ),
      const SizedBox(height: 22),
      FilledButton(
        key: const Key('feasibility-continue-button'),
        onPressed: onContinue,
        child: const Text('Xem 3 phương án'),
      ),
    ],
  );
}

class _PlanComparison extends StatelessWidget {
  const _PlanComparison({required this.onSelect});
  final VoidCallback onSelect;

  @override
  Widget build(BuildContext context) => _Page(
    section: 'So sánh kế hoạch',
    children: [
      const _Eyebrow('3 PHƯƠNG ÁN KHẢ THI'),
      const SizedBox(height: 7),
      Text(
        'Chọn nhịp đi hợp gu',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      const Text(
        'Mọi phương án đều đáp ứng thời gian, ngân sách và giới hạn di chuyển.',
      ),
      const SizedBox(height: 18),
      const _PlanCard(
        title: 'Tiết kiệm',
        description: 'Gọn đường, ưu tiên điểm miễn phí',
        cost: '2,1 triệu',
        travel: '19 km',
        stops: '4 điểm',
        match: '84%',
      ),
      const SizedBox(height: 10),
      _PlanCard(
        title: 'Cân bằng',
        description: 'Đủ biển, ẩm thực và khoảng nghỉ',
        cost: '3,25 triệu',
        travel: '24 km',
        stops: '4 điểm',
        match: '96%',
        recommended: true,
        action: FilledButton(
          key: const Key('select-balanced-plan-button'),
          onPressed: onSelect,
          child: const Text('Chọn phương án này'),
        ),
      ),
      const SizedBox(height: 10),
      const _PlanCard(
        title: 'Trải nghiệm',
        description: 'Thêm điểm check-in và bữa tối nổi bật',
        cost: '3,85 triệu',
        travel: '31 km',
        stops: '5 điểm',
        match: '90%',
      ),
    ],
  );
}

class _ItineraryDetail extends StatelessWidget {
  const _ItineraryDetail({
    required this.onOpenPoi,
    required this.onOpenReplan,
    required this.onStartTrip,
  });
  final VoidCallback onOpenPoi;
  final VoidCallback onOpenReplan;
  final VoidCallback onStartTrip;

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Lịch trình ngày 1',
    children: [
      Row(
        children: [
          Expanded(
            child: Text(
              'Đà Nẵng chậm mà chất',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ),
          IconButton.filledTonal(
            key: const Key('open-replan-button'),
            tooltip: 'Lập lại kế hoạch',
            onPressed: onOpenReplan,
            icon: const Icon(Icons.tune_rounded),
          ),
        ],
      ),
      const SizedBox(height: 6),
      const Text('Chủ nhật, 20/09 · Lưu ngoại tuyến lúc 08:30'),
      const SizedBox(height: 14),
      const Row(
        children: [
          Expanded(child: _SummaryMetric('3,25tr', 'dự kiến')),
          SizedBox(width: 8),
          Expanded(child: _SummaryMetric('24 km', 'di chuyển')),
          SizedBox(width: 8),
          Expanded(child: _SummaryMetric('4', 'điểm dừng')),
        ],
      ),
      const SizedBox(height: 12),
      const _Notice(
        icon: Icons.wb_sunny_outlined,
        text: 'Trời nắng 28°C. Sơn Trà phù hợp trước 11:00.',
      ),
      const SizedBox(height: 18),
      ...DemoTripData.activities.indexed.map(
        (entry) => _TimelineStop(
          stop: entry.$2,
          index: entry.$1,
          isLast: entry.$1 == DemoTripData.activities.length - 1,
          onTap: entry.$2.id == 'be-man' ? onOpenPoi : null,
        ),
      ),
      const SizedBox(height: 12),
      FilledButton.icon(
        key: const Key('start-trip-button'),
        onPressed: onStartTrip,
        icon: const Icon(Icons.navigation_rounded),
        label: const Text('Bắt đầu chuyến đi'),
      ),
    ],
  );
}

class _PoiDetail extends StatelessWidget {
  const _PoiDetail({required this.onBack, required this.onDirections});
  final VoidCallback onBack;
  final VoidCallback onDirections;

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Chi tiết địa điểm',
    leadingBack: onBack,
    children: [
      ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: AspectRatio(
          aspectRatio: 16 / 9,
          child: Image.network(
            DemoTripData.beManImage,
            fit: BoxFit.cover,
            errorBuilder: (_, error, stack) => const ColoredBox(
              color: AppColors.sand,
              child: Icon(
                Icons.restaurant_rounded,
                size: 48,
                color: AppColors.primary,
              ),
            ),
          ),
        ),
      ),
      const SizedBox(height: 16),
      const Row(
        children: [
          Expanded(
            child: Text(
              'Hải sản Bé Mặn',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
            ),
          ),
          _StatusPill('Tin cậy 92%', AppColors.success),
        ],
      ),
      const SizedBox(height: 6),
      const Text('Lô 14 Hoàng Sa · Hải sản địa phương · 4,5 ★'),
      const SizedBox(height: 18),
      const SurfaceCard(
        color: AppColors.softSurface,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Eyebrow('VÌ SAO PHÙ HỢP'),
            SizedBox(height: 7),
            Text(
              'Đúng ưu tiên ẩm thực địa phương, gần tuyến ven biển và nằm trong ngân sách.',
            ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      const _FactCard(
        label: 'ĐÃ XÁC MINH',
        color: AppColors.success,
        items: [
          'Địa chỉ và vị trí bản đồ',
          'Khoảng giá 250k–450k/người',
          'Có bãi đỗ xe máy',
        ],
      ),
      const SizedBox(height: 10),
      const _FactCard(
        label: 'SUY LUẬN',
        color: AppColors.warning,
        items: ['Có thể đông sau 19:00', 'Bàn ngoài trời phụ thuộc thời tiết'],
      ),
      const SizedBox(height: 10),
      const _Notice(
        icon: Icons.warning_amber_rounded,
        text: 'Giờ mở cửa có thể thay đổi. Nên gọi trước khi đến.',
      ),
      const SizedBox(height: 20),
      Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.bookmark_border_rounded),
              label: const Text('Lưu'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: FilledButton.icon(
              key: const Key('poi-directions-button'),
              onPressed: onDirections,
              icon: const Icon(Icons.directions_rounded),
              label: const Text('Chỉ đường'),
            ),
          ),
        ],
      ),
    ],
  );
}

class _Replan extends StatefulWidget {
  const _Replan({required this.onBack, required this.onApply});
  final VoidCallback onBack;
  final VoidCallback onApply;

  @override
  State<_Replan> createState() => _ReplanState();
}

class _ReplanState extends State<_Replan> {
  String _reason = 'Mưa bất chợt';

  @override
  Widget build(BuildContext context) => _Page(
    section: 'Điều chỉnh chuyến đi',
    leadingBack: widget.onBack,
    children: [
      const _Eyebrow('REPLAN'),
      const SizedBox(height: 7),
      Text(
        'Kế hoạch thay đổi?',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      const Text('Chọn tình huống. Davel giữ tối đa những gì vẫn còn hợp lý.'),
      const SizedBox(height: 16),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: ['Mưa bất chợt', 'Muốn nghỉ', 'Trễ giờ', 'Thêm địa điểm']
            .map(
              (value) => ChoiceChip(
                selected: _reason == value,
                label: Text(value),
                onSelected: (_) => setState(() => _reason = value),
              ),
            )
            .toList(),
      ),
      const SizedBox(height: 18),
      const _ChangeCard(
        icon: Icons.lock_outline_rounded,
        title: 'Giữ lại',
        text: 'Bữa trưa địa phương · Ngân sách 4 triệu',
        color: AppColors.success,
      ),
      const SizedBox(height: 9),
      const _ChangeCard(
        icon: Icons.remove_circle_outline,
        title: 'Bỏ',
        text: 'Xưởng sách ngoài trời lúc 16:00',
        color: AppColors.error,
      ),
      const SizedBox(height: 9),
      const _ChangeCard(
        icon: Icons.swap_horiz_rounded,
        title: 'Thay thế',
        text: 'Bảo tàng Chăm · hoạt động trong nhà',
        color: AppColors.accent,
      ),
      const SizedBox(height: 9),
      const _ChangeCard(
        icon: Icons.schedule_rounded,
        title: 'Dời giờ',
        text: 'Hải sản Bé Mặn → 18:15',
        color: AppColors.warning,
      ),
      const SizedBox(height: 20),
      FilledButton(
        key: const Key('apply-replan-button'),
        onPressed: widget.onApply,
        child: const Text('Áp dụng kế hoạch mới'),
      ),
    ],
  );
}

class _Page extends StatelessWidget {
  const _Page({
    required this.children,
    this.section = 'Lịch trình',
    this.showHeader = true,
    this.leadingBack,
  });
  final List<Widget> children;
  final String section;
  final bool showHeader;
  final VoidCallback? leadingBack;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: AppColors.canvas,
    child: Column(
      children: [
        if (showHeader)
          AppHeader(
            compact: true,
            section: section,
            trailing: leadingBack == null
                ? null
                : IconButton(
                    onPressed: leadingBack,
                    icon: const Icon(Icons.arrow_back_rounded),
                  ),
          ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: children,
            ),
          ),
        ),
      ],
    ),
  );
}

class _BrandMark extends StatelessWidget {
  const _BrandMark();
  @override
  Widget build(BuildContext context) => const Row(
    children: [
      CircleAvatar(
        backgroundColor: AppColors.primary,
        child: Icon(Icons.route_rounded, color: Colors.white),
      ),
      SizedBox(width: 10),
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Davel Trace',
            style: TextStyle(
              color: AppColors.primary,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            'Da Nang Planner',
            style: TextStyle(color: AppColors.muted, fontSize: 11),
          ),
        ],
      ),
    ],
  );
}

class _Eyebrow extends StatelessWidget {
  const _Eyebrow(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(
      color: AppColors.accent,
      fontSize: 10,
      fontWeight: FontWeight.w800,
      letterSpacing: 1.1,
    ),
  );
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(
      color: AppColors.ink,
      fontSize: 14,
      fontWeight: FontWeight.w800,
    ),
  );
}

class _SelectionTile extends StatelessWidget {
  const _SelectionTile({
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });
  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Material(
    color: selected ? AppColors.softSurface : AppColors.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: BorderSide(
        color: selected ? AppColors.primary : AppColors.outline,
        width: selected ? 1.5 : 1,
      ),
    ),
    child: ListTile(
      onTap: onTap,
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(subtitle),
      trailing: Icon(
        selected ? Icons.check_circle_rounded : Icons.circle_outlined,
        color: selected ? AppColors.primary : AppColors.outline,
      ),
    ),
  );
}

class _WeatherBadge extends StatelessWidget {
  const _WeatherBadge();
  @override
  Widget build(BuildContext context) => const _StatusPill(
    '28°C · Nắng',
    AppColors.warning,
    icon: Icons.wb_sunny_outlined,
  );
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(this.text, this.color, {this.icon});
  final String text;
  final Color color;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .12),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 4),
        ],
        Text(
          text,
          style: TextStyle(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    ),
  );
}

class _InfoField extends StatelessWidget {
  const _InfoField({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: AppColors.outline),
    ),
    child: Row(
      children: [
        Icon(icon, size: 17, color: AppColors.primary),
        const SizedBox(width: 7),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: AppColors.ink,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    ),
  );
}

class _DateTile extends StatelessWidget {
  const _DateTile();
  @override
  Widget build(BuildContext context) => Container(
    width: 46,
    padding: const EdgeInsets.symmetric(vertical: 7),
    decoration: BoxDecoration(
      color: AppColors.primary,
      borderRadius: BorderRadius.circular(12),
    ),
    child: const Column(
      children: [
        Text(
          '20',
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        Text('TH09', style: TextStyle(color: Colors.white70, fontSize: 9)),
      ],
    ),
  );
}

class _CheckRow extends StatelessWidget {
  const _CheckRow(this.title, this.subtitle, {this.last = false});
  final String title;
  final String subtitle;
  final bool last;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(vertical: 12),
    decoration: BoxDecoration(
      border: last
          ? null
          : const Border(bottom: BorderSide(color: AppColors.outline)),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(
          Icons.check_circle_rounded,
          color: AppColors.success,
          size: 20,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 3),
              Text(subtitle, style: const TextStyle(fontSize: 12)),
            ],
          ),
        ),
      ],
    ),
  );
}

class _Notice extends StatelessWidget {
  const _Notice({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: AppColors.softSurface,
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.accent, size: 19),
        const SizedBox(width: 9),
        Expanded(child: Text(text, style: const TextStyle(fontSize: 12))),
      ],
    ),
  );
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.title,
    required this.description,
    required this.cost,
    required this.travel,
    required this.stops,
    required this.match,
    this.recommended = false,
    this.action,
  });
  final String title;
  final String description;
  final String cost;
  final String travel;
  final String stops;
  final String match;
  final bool recommended;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(
        color: recommended ? AppColors.primary : AppColors.outline,
        width: recommended ? 1.8 : 1,
      ),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            if (recommended) const _StatusPill('Đề xuất', AppColors.primary),
          ],
        ),
        const SizedBox(height: 4),
        Text(description),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(child: _MetricText(cost, 'chi phí')),
            Expanded(child: _MetricText(travel, 'di chuyển')),
            Expanded(child: _MetricText(stops, 'dừng')),
            Expanded(child: _MetricText(match, 'hợp gu')),
          ],
        ),
        if (action != null) ...[
          const SizedBox(height: 14),
          SizedBox(width: double.infinity, child: action!),
        ],
      ],
    ),
  );
}

class _MetricText extends StatelessWidget {
  const _MetricText(this.value, this.label);
  final String value;
  final String label;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        value,
        style: const TextStyle(
          color: AppColors.ink,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
      Text(label, style: const TextStyle(fontSize: 9)),
    ],
  );
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric(this.value, this.label);
  final String value;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(11),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: AppColors.outline),
    ),
    child: Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            color: AppColors.primary,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(fontSize: 10)),
      ],
    ),
  );
}

class _TimelineStop extends StatelessWidget {
  const _TimelineStop({
    required this.stop,
    required this.index,
    required this.isLast,
    this.onTap,
  });
  final TripStop stop;
  final int index;
  final bool isLast;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => IntrinsicHeight(
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          width: 30,
          child: Column(
            children: [
              CircleAvatar(
                radius: 12,
                backgroundColor: AppColors.primary,
                child: Text(
                  '${index + 1}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (!isLast)
                Expanded(child: Container(width: 2, color: AppColors.outline)),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: SurfaceCard(
              padding: const EdgeInsets.all(12),
              child: InkWell(
                key: stop.id == 'be-man' ? const Key('open-poi-button') : null,
                onTap: onTap,
                child: Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: stop.color.withValues(alpha: .12),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(stop.icon, color: stop.color),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${stop.time} · ${stop.durationLabel}',
                            style: const TextStyle(
                              color: AppColors.accent,
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            stop.title,
                            style: const TextStyle(
                              color: AppColors.ink,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          Text(
                            stop.subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                    if (onTap != null) const Icon(Icons.chevron_right_rounded),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );
}

class _FactCard extends StatelessWidget {
  const _FactCard({
    required this.label,
    required this.color,
    required this.items,
  });
  final String label;
  final Color color;
  final List<String> items;
  @override
  Widget build(BuildContext context) => SurfaceCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StatusPill(label, color),
        const SizedBox(height: 9),
        ...items.map(
          (item) => Padding(
            padding: const EdgeInsets.only(bottom: 5),
            child: Row(
              children: [
                Icon(Icons.check_rounded, color: color, size: 16),
                const SizedBox(width: 7),
                Expanded(child: Text(item)),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class _ChangeCard extends StatelessWidget {
  const _ChangeCard({
    required this.icon,
    required this.title,
    required this.text,
    required this.color,
  });
  final IconData icon;
  final String title;
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => SurfaceCard(
    padding: const EdgeInsets.all(13),
    child: Row(
      children: [
        CircleAvatar(
          backgroundColor: color.withValues(alpha: .12),
          child: Icon(icon, color: color, size: 19),
        ),
        const SizedBox(width: 11),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  color: color,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                text,
                style: const TextStyle(
                  color: AppColors.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}
