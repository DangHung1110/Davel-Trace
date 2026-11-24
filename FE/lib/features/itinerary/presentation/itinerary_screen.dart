import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../core/errors/api_exception.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../../planning/domain/models.dart';
import '../../profile/presentation/profile_screen.dart';
import 'planning_request_review.dart';

class ItineraryScreen extends StatelessWidget {
  const ItineraryScreen({
    super.key,
    required this.state,
    required this.onOpenMap,
    this.onBack,
  });

  final AppState state;
  final VoidCallback? onBack;

  Future<void> openTripEditor(BuildContext context) => _tripEditor(context);

  Future<void> _runAction(
    BuildContext context,
    Future<void> Function() action,
  ) async {
    try {
      await action();
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  static Future<void> _reviewProposal(
    BuildContext context,
    AppState state,
  ) async {
    final proposal = state.aiProposal;
    if (proposal == null) return;
    final corrections = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => PlanningRequestReview(
          values: proposal.confirmedOverrides,
          repository: state.repository,
          placeResolutions: proposal.placeResolutions,
        ),
      ),
    );
    if (corrections != null && context.mounted) {
      await state.confirmAiProposalAndPlan(corrections: corrections);
    }
  }

  final VoidCallback onOpenMap;

  Future<void> _tripEditor(BuildContext context, {Trip? trip}) async {
    final data = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => TripEditor(trip: trip)),
    );
    if (data == null || !context.mounted) return;
    try {
      if (trip == null) {
        await state.createTrip(data);
      } else {
        await state.updateActiveTrip(data);
      }
    } on ApiException catch (error) {
      if (trip != null &&
          error.code == 'DATE_REDUCTION_CONFIRMATION_REQUIRED' &&
          context.mounted &&
          await _confirm(
            context,
            'Xóa các ngày bị rút ngắn?',
            'Các hoạt động trong những ngày bị loại khỏi chuyến đi sẽ bị xóa.',
          )) {
        await state.updateActiveTrip(data, confirmRemovedDays: true);
        return;
      }
      if (context.mounted) _error(context, state.errorMessage);
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
      'Chuyến đi sẽ vào thùng rác và có thể khôi phục trong 30 ngày.',
    )) {
      return;
    }
    try {
      await state.deleteActiveTrip();
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  Future<void> _archiveTrip(BuildContext context) async {
    if (!await _confirm(
      context,
      'Lưu trữ chuyến đi?',
      'Dữ liệu ngày và hoạt động vẫn được giữ nguyên.',
    )) {
      return;
    }
    try {
      await state.archiveActiveTrip();
    } catch (_) {
      if (context.mounted) _error(context, state.errorMessage);
    }
  }

  @override
  Widget build(BuildContext context) {
    final trip = state.activeTrip;
    final itinerary = state.itinerary;
    final dayActivities = state.activitiesForSelectedDay;
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          AppHeader(
            compact: true,
            section: 'Lịch trình',
            trailing: onBack == null
                ? null
                : TextButton.icon(
                    key: const Key('back-to-trips'),
                    onPressed: onBack,
                    icon: const Icon(Icons.arrow_back, size: 18),
                    label: const Text('Chuyến đi'),
                  ),
          ),
          Expanded(
            child: trip == null
                ? _NoTrip(state: state, onCreate: () => _tripEditor(context))
                : RefreshIndicator(
                    onRefresh: state.refresh,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
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
                              enabled: !state.isMutating && !state.isPlanning,
                              tooltip: 'Tùy chọn chuyến đi',
                              onSelected: (value) {
                                if (value == 'edit') {
                                  _tripEditor(context, trip: trip);
                                }
                                if (value == 'delete') {
                                  _deleteTrip(context);
                                }
                                if (value == 'archive') {
                                  _archiveTrip(context);
                                }
                                if (value == 'clear') {
                                  _runAction(context, state.clearActiveTrip);
                                }
                              },
                              itemBuilder: (_) => const [
                                PopupMenuItem(
                                  value: 'edit',
                                  child: Text('Sửa chuyến đi'),
                                ),
                                PopupMenuItem(
                                  value: 'clear',
                                  child: Text('Bỏ chọn chuyến đang dùng'),
                                ),
                                PopupMenuItem(
                                  value: 'archive',
                                  child: Text('Lưu trữ chuyến đi'),
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
                        SurfaceCard(
                          color: AppColors.sand,
                          child: Row(
                            children: [
                              const Icon(
                                Icons.calendar_month_outlined,
                                color: AppColors.primary,
                              ),
                              const SizedBox(width: 11),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${_shortDate(trip.startDate)} đến ${_shortDate(trip.endDate)}',
                                      style: const TextStyle(
                                        color: AppColors.ink,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                    Text(
                                      '${trip.dayStart.substring(0, 5)}–${trip.dayEnd.substring(0, 5)} · ${trip.travelers} người · ${moneyVnd(trip.budgetVnd)}',
                                      style: const TextStyle(
                                        color: AppColors.muted,
                                        fontSize: 12,
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
                                  color: AppColors.primary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          key: const Key('open-planning-button'),
                          onPressed: state.isMutating
                              ? null
                              : () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) =>
                                        PlanningScreen(state: state),
                                  ),
                                ),
                          icon: const Icon(Icons.auto_awesome_outlined),
                          label: const Text('Lập lịch cho chuyến đi'),
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
                        if (state.tripDates.length > 1) ...[
                          _DaySelector(state: state),
                          const SizedBox(height: 14),
                        ],
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                'Lịch trình trong ngày',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                            ),
                            Text(
                              'Bản ${itinerary?.version ?? 1}',
                              style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 9),
                        if (itinerary == null || dayActivities.isEmpty)
                          const _EmptyActivities()
                        else
                          ...dayActivities.indexed.map(
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
                              onStatus: (status) => _runAction(
                                context,
                                () => state.setActivityStatus(entry.$2, status),
                              ),
                              onMoveUp: entry.$1 == 0
                                  ? null
                                  : () => _runAction(
                                      context,
                                      () => state.moveActivity(
                                        entry.$1,
                                        entry.$1 - 1,
                                      ),
                                    ),
                              onMoveDown: entry.$1 == dayActivities.length - 1
                                  ? null
                                  : () => _runAction(
                                      context,
                                      () => state.moveActivity(
                                        entry.$1,
                                        entry.$1 + 1,
                                      ),
                                    ),
                            ),
                          ),
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
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

class PlanningScreen extends StatelessWidget {
  const PlanningScreen({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Lập lịch chuyến đi')),
    body: AnimatedBuilder(
      animation: state,
      builder: (context, _) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            state.activeTrip?.title ?? 'Chuyến đi',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 8),
          const Text(
            'Tạo phương án, xem các điểm dừng rồi chọn lịch phù hợp. Lịch hiện tại chỉ thay đổi khi bạn xác nhận chọn.',
          ),
          const SizedBox(height: 16),
          TextButton.icon(
            key: const Key('planning-preferences-button'),
            onPressed: state.isPlanning
                ? null
                : () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => Scaffold(
                        appBar: AppBar(title: const Text('Sở thích du lịch')),
                        body: AnimatedBuilder(
                          animation: state,
                          builder: (_, _) =>
                              ProfileScreen(state: state, showHeader: false),
                        ),
                      ),
                    ),
                  ),
            icon: const Icon(Icons.tune),
            label: const Text('Sở thích du lịch'),
          ),
          const SizedBox(height: 16),
          _PlanningPanel(state: state),
        ],
      ),
    ),
  );
}

class _PlanningPanel extends StatefulWidget {
  const _PlanningPanel({required this.state});
  final AppState state;

  @override
  State<_PlanningPanel> createState() => _PlanningPanelState();
}

class _PlanningPanelState extends State<_PlanningPanel> {
  AppState get state => widget.state;
  final _placeNames = <String, Future<PoiItem?>>{};

  Future<PoiItem?> _resolvePlace(String id) =>
      _placeNames.putIfAbsent(id, () async {
        try {
          return await state.repository.getPoiDetails(id);
        } catch (_) {
          return null;
        }
      });

  Future<void> _interpret(BuildContext context) async {
    final controller = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Diễn giải mong muốn với AI'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Nội dung sẽ được gửi tới nhà cung cấp AI bên ngoài. Không nhập mật khẩu, token hoặc thông tin riêng tư không cần thiết.',
                style: TextStyle(fontSize: 12, color: AppColors.muted),
              ),
              const SizedBox(height: 10),
              TextField(
                key: const Key('planning-ai-prompt'),
                controller: controller,
                minLines: 3,
                maxLines: 6,
                maxLength: 4000,
                decoration: const InputDecoration(
                  labelText: 'Ví dụ: Đi 2 người, 3 triệu, phải ghé Cầu Rồng…',
                  alignLabelWithHint: true,
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Dùng form thường'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Diễn giải'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (text != null && text.length >= 3) {
      await state.interpretPlanningRequest(text);
    }
  }

  Future<void> _showHistory(BuildContext context) async {
    await state.loadItineraryHistory();
    if (!context.mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) => FractionallySizedBox(
        heightFactor: 0.72,
        child: ListView(
          key: const Key('itinerary-version-history'),
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
          children: [
            Text(
              'Lịch sử phiên bản',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            if (state.itineraryVersions.isEmpty)
              const Text('Chưa có phiên bản đã chốt.'),
            ...state.itineraryVersions.map(
              (version) => Card(
                child: ListTile(
                  title: Text('Phiên bản ${version.ordinal}'),
                  subtitle: Text(
                    '${version.reason} · ${version.dataVersion}'
                    '${version.parentId == null ? '' : ' · có phiên bản cha'}',
                  ),
                  trailing: version.active
                      ? const Chip(label: Text('Đang dùng'))
                      : TextButton(
                          onPressed: state.isPlanning
                              ? null
                              : () async {
                                  await state.activateItineraryVersion(version);
                                  if (sheetContext.mounted) {
                                    Navigator.pop(sheetContext);
                                  }
                                },
                          child: const Text('Kích hoạt'),
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

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
        ? 'Phương án từ hệ thống'
        : stale
        ? 'Dữ liệu gần nhất · mất kết nối'
        : state.isDemoManagement
        ? 'Phương án mẫu để tham khảo'
        : 'Chưa có phương án cho chuyến này';
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
                live
                    ? Icons.cloud_done_outlined
                    : stale
                    ? Icons.cloud_off_outlined
                    : state.isDemoManagement
                    ? Icons.science_outlined
                    : Icons.alt_route_outlined,
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
                      live
                          ? 'Chọn một phương án để lưu vào lịch trình.'
                          : stale
                          ? 'Không tải được phương án mới. Bạn đang xem dữ liệu gần nhất.'
                          : state.isDemoManagement
                          ? 'Các phương án mẫu chưa được lưu vào chuyến đi.'
                          : 'Tạo phương án để bắt đầu, sau đó xem và chọn lịch phù hợp.',
                      style: const TextStyle(fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 9),
        if (state.errorMessage != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: SurfaceCard(
              color: const Color(0xFFFBEEEE),
              padding: const EdgeInsets.all(12),
              child: Text(
                state.errorMessage!,
                key: const Key('planning-action-error'),
                style: const TextStyle(color: AppColors.error, fontSize: 13),
              ),
            ),
          ),
        FilledButton.icon(
          key: const Key('request-plan-button'),
          onPressed:
              state.isPlanning || state.isInterpreting || state.isDemoManagement
              ? null
              : state.requestPlan,
          icon: Icon(
            state.isPlanning ? Icons.hourglass_top : Icons.alt_route_rounded,
          ),
          label: Text(
            state.isPlanning
                ? 'Đang lập phương án…'
                : state.isDemoManagement
                ? 'Đăng nhập để lập lịch'
                : 'Tạo phương án lịch trình',
          ),
        ),
        const SizedBox(height: 12),
        TextButton.icon(
          key: const Key('request-ai-interpretation'),
          onPressed:
              state.isInterpreting || state.isPlanning || state.isDemoManagement
              ? null
              : () => _interpret(context),
          icon: Icon(
            state.isInterpreting ? Icons.hourglass_top : Icons.auto_awesome,
          ),
          label: Text(
            state.isInterpreting
                ? 'AI đang diễn giải…'
                : 'Nhập mong muốn bằng lời với AI',
          ),
        ),
        if (state.aiMessage != null) ...[
          const SizedBox(height: 6),
          Text(
            state.aiMessage!,
            key: const Key('planning-ai-message'),
            style: const TextStyle(fontSize: 11, color: AppColors.muted),
          ),
        ],
        if (state.aiProposal case final proposal?) ...[
          const SizedBox(height: 8),
          SurfaceCard(
            key: const Key('planning-ai-proposal'),
            color: const Color(0xFFF2F5F4),
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Yêu cầu đã được diễn giải',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 5),
                const Text(
                  'Kiểm tra ngân sách, thời gian và địa điểm trước khi dùng để lập lịch.',
                ),
                if (proposal.assumptions.isNotEmpty)
                  Text('Giả định: ${proposal.assumptions.join('; ')}'),
                if (proposal.unresolved.isNotEmpty)
                  Text(
                    'Chưa xác minh (không dùng): ${proposal.unresolved.join('; ')}',
                    style: const TextStyle(color: AppColors.warning),
                  ),
                if (proposal.placeResolutions.isNotEmpty)
                  Text(
                    '${proposal.placeResolutions.length} tên địa điểm cần bạn chọn hoặc bỏ trong bước kiểm tra.',
                  ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    TextButton(
                      onPressed: state.skipAiProposal,
                      child: const Text('Bỏ qua AI'),
                    ),
                    FilledButton(
                      key: const Key('confirm-ai-proposal'),
                      onPressed: () =>
                          ItineraryScreen._reviewProposal(context, state),
                      child: const Text('Xác nhận và lập lịch'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 9),
        const SizedBox(height: 10),
        if (state.acceptance != null) ...[
          FilledButton.tonalIcon(
            key: const Key('view-accepted-itinerary'),
            onPressed: () => Navigator.of(context).pop(),
            icon: const Icon(Icons.check_circle_outline),
            label: const Text('Đã lưu · Xem lịch trình'),
          ),
          const SizedBox(height: 12),
        ],
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
              busy: state.isPlanning || state.isDemoManagement || stale,
              previewOnly: state.isDemoManagement,
              resolvePlace: _resolvePlace,
              onSelect: () => state.acceptAlternative(plan),
            ),
          ),
        ),
        if (state.activeAlternative != null) ...[
          TextButton.icon(
            key: const Key('explain-active-plan'),
            onPressed: state.isExplaining
                ? null
                : () => state.explainPlan(state.activeAlternative!),
            icon: const Icon(Icons.info_outline),
            label: Text(
              state.isExplaining
                  ? 'Đang giải thích…'
                  : 'Vì sao gợi ý lịch này? (có dùng AI bên ngoài)',
            ),
          ),
          if (state.planExplanation case final explanation?)
            SurfaceCard(
              key: const Key('plan-explanation'),
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    explanation.source == 'ai_grounded'
                        ? 'Giải thích AI có dẫn chứng'
                        : 'Giải thích từ dữ liệu lịch trình',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  Text(explanation.summary),
                  ...explanation.reasons.map(
                    (reason) => Text('• ${reason['text'] ?? ''}'),
                  ),
                ],
              ),
            ),
        ],
        if (state.itineraryVersions.isNotEmpty ||
            (live && state.acceptance != null)) ...[
          const SizedBox(height: 2),
          ExpansionTile(
            key: const Key('planning-more-options'),
            tilePadding: EdgeInsets.zero,
            title: const Text('Lịch sử & điều chỉnh'),
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    key: const Key('open-version-history'),
                    onPressed: state.isPlanning
                        ? null
                        : () => _showHistory(context),
                    icon: const Icon(Icons.history_rounded),
                    label: const Text('Lịch sử'),
                  ),
                  FilledButton.tonalIcon(
                    key: const Key('request-replan-button'),
                    onPressed:
                        state.isPlanning ||
                            !state.itineraryVersions.any((item) => item.active)
                        ? null
                        : state.requestReplan,
                    icon: const Icon(Icons.refresh_rounded),
                    label: const Text('Lập lại phần còn lại'),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
        ],
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
    required this.resolvePlace,
    this.previewOnly = false,
  });

  final PlanAlternative plan;
  final bool selected;
  final bool accepted;
  final bool isLive;
  final bool busy;
  final VoidCallback onSelect;
  final Future<PoiItem?> Function(String) resolvePlace;
  final bool previewOnly;

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
        for (final activity in plan.activities)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: FutureBuilder<PoiItem?>(
              future: activity['name'] != null || activity['title'] != null
                  ? null
                  : resolvePlace(activity['poi_id']?.toString() ?? ''),
              builder: (_, snapshot) => Text(
                '${activity['start'] ?? activity['start_time'] ?? ''}  ${activity['name'] ?? activity['title'] ?? snapshot.data?.name ?? (snapshot.connectionState == ConnectionState.waiting ? 'Đang tải địa điểm…' : 'Chưa tải được tên địa điểm')}',
              ),
            ),
          ),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            key: Key('accept-plan-${plan.id}'),
            onPressed: busy || accepted || !plan.gatePassed ? null : onSelect,
            child: Text(
              previewOnly
                  ? 'Đăng nhập để lưu lịch'
                  : accepted
                  ? 'Đã lưu lựa chọn'
                  : selected && !isLive
                  ? 'Đã chọn cục bộ'
                  : !isLive
                  ? 'Kết nối lại để lưu lịch'
                  : 'Dùng lịch trình này',
            ),
          ),
        ),
      ],
    ),
  );
}

class _NoTrip extends StatelessWidget {
  const _NoTrip({required this.state, required this.onCreate});
  final AppState state;
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
          Text(
            state.trips.isEmpty
                ? 'Tạo chuyến Đà Nẵng, sau đó tự thêm hoạt động theo từng ngày.'
                : 'Chọn một chuyến có sẵn để tiếp tục quản lý.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            key: const Key('empty-create-trip-button'),
            onPressed: onCreate,
            icon: const Icon(Icons.add_rounded),
            label: Text(
              state.trips.isEmpty ? 'Tạo chuyến đầu tiên' : 'Tạo chuyến mới',
            ),
          ),
          if (state.trips.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...state.trips.map(
              (trip) => ListTile(
                title: Text(trip.title),
                subtitle: Text(
                  '${_shortDate(trip.startDate)} → ${_shortDate(trip.endDate)}',
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => state.selectTrip(trip),
              ),
            ),
          ],
          if (state.archivedTrips.isNotEmpty ||
              state.deletedTrips.isNotEmpty) ...[
            const SizedBox(height: 8),
            TripArchiveButton(state: state),
          ],
        ],
      ),
    ),
  );
}

class TripArchiveButton extends StatelessWidget {
  const TripArchiveButton({super.key, required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    icon: const Icon(Icons.inventory_2_outlined),
    label: Text(
      'Đã lưu trữ / đã xóa (${state.archivedTrips.length + state.deletedTrips.length})',
    ),
    onPressed: () => showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            Text(
              'Khôi phục chuyến đi',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            for (final trip in [...state.archivedTrips, ...state.deletedTrips])
              ListTile(
                title: Text(trip.title),
                subtitle: Text(
                  state.deletedTrips.any((item) => item.id == trip.id)
                      ? 'Trong thùng rác'
                      : 'Đã lưu trữ',
                ),
                trailing: TextButton(
                  onPressed: state.isMutating
                      ? null
                      : () async {
                          try {
                            await state.restoreTrip(trip);
                            if (sheetContext.mounted) {
                              Navigator.pop(sheetContext);
                            }
                          } catch (_) {
                            if (sheetContext.mounted) {
                              _error(sheetContext, state.errorMessage);
                            }
                          }
                        },
                  child: const Text('Khôi phục'),
                ),
              ),
          ],
        ),
      ),
    ),
  );
}

class _DaySelector extends StatelessWidget {
  const _DaySelector({required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: MediaQuery.textScalerOf(context).scale(12) + 32,
    child: ListView.separated(
      scrollDirection: Axis.horizontal,
      itemCount: state.tripDates.length,
      separatorBuilder: (_, _) => const SizedBox(width: 8),
      itemBuilder: (_, index) {
        final date = state.tripDates[index];
        final selected =
            state.selectedTripDate != null &&
            DateUtils.isSameDay(state.selectedTripDate, date);
        return ChoiceChip(
          selected: selected,
          label: Text('Ngày ${index + 1} · ${_shortDate(date)}'),
          onSelected: (_) => state.selectTripDate(date),
        );
      },
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
            'Chưa có hoạt động trong ngày này. Thêm địa điểm hoặc lập lịch để bắt đầu.',
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
    required this.onStatus,
  });

  final ActivityItem activity;
  final int index;
  final bool busy;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback? onMoveUp;
  final VoidCallback? onMoveDown;
  final ValueChanged<String> onStatus;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(_activityIcon(activity.category), color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${_clock(activity.startAt)} – ${_clock(activity.endAt)}',
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      activity.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ],
                ),
              ),
              PopupMenuButton<String>(
                tooltip: 'Tùy chọn hoạt động',
                enabled: !busy,
                onSelected: (action) {
                  switch (action) {
                    case 'edit':
                      onEdit();
                    case 'delete':
                      onDelete();
                    case 'up':
                      onMoveUp?.call();
                    case 'down':
                      onMoveDown?.call();
                  }
                },
                itemBuilder: (_) => [
                  const PopupMenuItem(
                    value: 'edit',
                    child: Text('Sửa hoạt động'),
                  ),
                  PopupMenuItem(
                    value: 'up',
                    enabled: onMoveUp != null,
                    child: const Text('Đưa lên'),
                  ),
                  PopupMenuItem(
                    value: 'down',
                    enabled: onMoveDown != null,
                    child: const Text('Đưa xuống'),
                  ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: Text('Xóa hoạt động'),
                  ),
                ],
              ),
            ],
          ),
          if (activity.notes.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(activity.notes),
          ],
          const SizedBox(height: 12),
          Text(
            'Chi phí dự kiến: ${moneyVnd(activity.estimatedCostVnd)}',
            style: const TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 4),
          PopupMenuButton<String>(
            tooltip: 'Đổi trạng thái',
            enabled: !busy,
            initialValue: activity.progressState,
            onSelected: onStatus,
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'planned', child: Text('Đã lên kế hoạch')),
              PopupMenuItem(value: 'completed', child: Text('Đã hoàn thành')),
              PopupMenuItem(value: 'skipped', child: Text('Đã bỏ qua')),
            ],
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    activity.progressState == 'completed'
                        ? Icons.check_circle_outline
                        : activity.progressState == 'skipped'
                        ? Icons.cancel_outlined
                        : Icons.schedule,
                    size: 18,
                    color: AppColors.primary,
                  ),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(switch (activity.progressState) {
                      'completed' => 'Đã hoàn thành',
                      'skipped' => 'Đã bỏ qua',
                      _ => 'Đã lên kế hoạch',
                    }),
                  ),
                  const Icon(Icons.expand_more, size: 18),
                ],
              ),
            ),
          ),
        ],
      ),
    ),
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
  late final TextEditingController _dayStart;
  late final TextEditingController _dayEnd;
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
    _dayStart = TextEditingController(
      text: trip?.dayStart.substring(0, 5) ?? '07:00',
    );
    _dayEnd = TextEditingController(
      text: trip?.dayEnd.substring(0, 5) ?? '21:00',
    );
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
    _dayStart.dispose();
    _dayEnd.dispose();
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.pop(context, {
      'title': _title.text.trim(),
      'start_date': isoDate(_start),
      'end_date': isoDate(_start.add(Duration(days: _days - 1))),
      'day_start': '${_dayStart.text.trim()}:00',
      'day_end': '${_dayEnd.text.trim()}:00',
      'travelers': int.parse(_travelers.text),
      'budget_vnd': int.parse(_budget.text),
      'transport': _transport,
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.trip == null ? 'Tạo chuyến đi' : 'Sửa chuyến đi'),
    ),
    bottomNavigationBar: Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        minimum: const EdgeInsets.all(16),
        child: FilledButton(
          key: const Key('save-trip-button'),
          onPressed: _save,
          child: Text(widget.trip == null ? 'Tạo chuyến đi' : 'Lưu thay đổi'),
        ),
      ),
    ),
    body: Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Thông tin chuyến đi',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 14),
              const Text(
                'Điểm đến: Đà Nẵng. Bạn có thể tự thêm hoạt động hoặc lập lịch sau khi tạo.',
              ),
              const SizedBox(height: 16),
              TextFormField(
                key: const Key('trip-title-field'),
                controller: _title,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Tên chuyến đi'),
                validator: _required,
              ),
              const SizedBox(height: 10),
              InkWell(
                key: const Key('trip-start-date-field'),
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
              DropdownButtonFormField<int>(
                isExpanded: true,
                key: const Key('trip-duration-field'),
                initialValue: _days,
                decoration: const InputDecoration(labelText: 'Số ngày'),
                items: List.generate(
                  14,
                  (i) => DropdownMenuItem(
                    value: i + 1,
                    child: Text('${i + 1} ngày'),
                  ),
                ),
                onChanged: (value) => setState(() => _days = value!),
              ),
              const SizedBox(height: 24),
              Text(
                'Người đi và ngân sách',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('trip-travelers-field'),
                controller: _travelers,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Số người'),
                validator: (value) {
                  final count = int.tryParse(value?.trim() ?? '');
                  return count != null && count >= 1 && count <= 20
                      ? null
                      : 'Nhập từ 1 đến 20 người';
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('trip-budget-field'),
                controller: _budget,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Ngân sách (VND)',
                  helperText: 'Tổng ngân sách cho cả nhóm',
                ),
                validator: _nonNegative,
              ),
              const SizedBox(height: 24),
              Text(
                'Di chuyển và giờ hoạt động',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                isExpanded: true,
                key: const Key('trip-transport-field'),
                initialValue: _transport,
                decoration: const InputDecoration(labelText: 'Di chuyển'),
                items: [
                  const DropdownMenuItem(
                    value: 'motorbike',
                    child: Text('Xe máy'),
                  ),
                  const DropdownMenuItem(value: 'car', child: Text('Ô tô')),
                  const DropdownMenuItem(
                    value: 'walking',
                    child: Text('Đi bộ'),
                  ),
                  const DropdownMenuItem(
                    value: 'mixed',
                    child: Text('Kết hợp phương tiện'),
                  ),
                  const DropdownMenuItem(value: 'taxi', child: Text('Taxi')),
                  const DropdownMenuItem(
                    value: 'bicycle',
                    child: Text('Xe đạp'),
                  ),
                  if (![
                    'motorbike',
                    'car',
                    'walking',
                    'mixed',
                    'taxi',
                    'bicycle',
                  ].contains(_transport))
                    DropdownMenuItem(
                      value: _transport,
                      child: const Text('Phương tiện đã lưu'),
                    ),
                ],
                onChanged: (value) => setState(() => _transport = value!),
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('trip-day-start-field'),
                controller: _dayStart,
                keyboardType: TextInputType.datetime,
                decoration: const InputDecoration(
                  labelText: 'Bắt đầu mỗi ngày',
                  hintText: '07:00',
                ),
                validator: _validTime,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('trip-day-end-field'),
                controller: _dayEnd,
                keyboardType: TextInputType.datetime,
                decoration: const InputDecoration(
                  labelText: 'Kết thúc mỗi ngày',
                  hintText: '21:00',
                ),
                validator: (value) {
                  final error = _validTime(value);
                  if (error != null) return error;
                  if (_validTime(_dayStart.text) == null &&
                      value!.trim().compareTo(_dayStart.text.trim()) <= 0) {
                    return 'Giờ kết thúc phải sau giờ bắt đầu';
                  }
                  return null;
                },
              ),
            ],
          ),
        ),
      ),
    ),
  );

  String? _validTime(String? value) =>
      RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(value?.trim() ?? '')
      ? null
      : 'Nhập giờ theo HH:MM (ví dụ 08:30)';
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

  Future<void> _showPoiDetails(PoiItem result) async {
    PoiItem place = result;
    try {
      place = await widget.state.getPoiDetails(result.id);
    } catch (_) {
      // Search result details remain usable when the detail request is offline.
    }
    if (!mounted) return;
    final selected = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  place.name,
                  style: Theme.of(sheetContext).textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                Text(place.type),
                const SizedBox(height: 12),
                _PoiEvidenceRow(
                  label: 'Xác minh',
                  value: place.verified
                      ? 'Đã xác minh'
                      : 'Chưa xác minh · cần kiểm tra',
                ),
                _PoiEvidenceRow(
                  label: 'Nguồn',
                  value: place.source ?? 'Không rõ nguồn',
                ),
                _PoiEvidenceRow(
                  label: 'Phiên bản',
                  value: place.snapshotVersion ?? 'Không rõ phiên bản',
                ),
                _PoiEvidenceRow(
                  label: 'Giờ mở cửa',
                  value: place.openingHours.isEmpty
                      ? 'Chưa có dữ liệu'
                      : place.openingHours.join(', '),
                ),
                _PoiEvidenceRow(
                  label: 'Giá',
                  value: place.priceState == 'unknown'
                      ? 'Chưa có dữ liệu'
                      : (place.ticketNote ??
                            (place.fee == null
                                ? (place.priceLevel == null
                                      ? 'Có dữ liệu mức giá'
                                      : 'Mức giá ${place.priceLevel}')
                                : '${place.fee} ₫')),
                ),
                if (place.fetchedAt != null)
                  _PoiEvidenceRow(
                    label: 'Cập nhật nguồn',
                    value: place.fetchedAt!,
                  ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => Navigator.pop(sheetContext, true),
                    icon: const Icon(Icons.add_location_alt_outlined),
                    label: const Text('Thêm vào hoạt động'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    if (selected == true && mounted) _selectPoi(place);
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    final parts = _time.text.split(':');
    final tripDate =
        widget.activity?.startAt ??
        widget.state.selectedTripDate ??
        widget.state.activeTrip!.startDate;
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
              'Chọn địa điểm có sẵn để hiển thị trên tuyến bản đồ. Hoạt động riêng được lưu vào lịch trình.',
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
                      labelText: 'Tìm địa điểm',
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
                      subtitle: Text(
                        '${poi.type} · ${poi.verified ? 'Đã xác minh' : 'Chưa xác minh'}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: IconButton(
                        tooltip: 'Chi tiết và nguồn dữ liệu',
                        icon: Icon(
                          poi.verified
                              ? Icons.verified_outlined
                              : Icons.info_outline,
                          size: 19,
                          color: poi.verified
                              ? AppColors.primary
                              : AppColors.warning,
                        ),
                        onPressed: () => _showPoiDetails(poi),
                      ),
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
                    isExpanded: true,
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

class _PoiEvidenceRow extends StatelessWidget {
  const _PoiEvidenceRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 104,
          child: Text(
            label,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
        Expanded(child: Text(value)),
      ],
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
