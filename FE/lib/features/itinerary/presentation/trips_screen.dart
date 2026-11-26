import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../../profile/presentation/profile_screen.dart';
import 'itinerary_screen.dart';

class TripsScreen extends StatefulWidget {
  const TripsScreen({
    super.key,
    required this.state,
    required this.onOpenMap,
    this.onOpenGroups,
    this.onOpenManualMap,
    this.detailRequest = 0,
    this.collectionRequest = 0,
  });
  final AppState state;
  final VoidCallback onOpenMap;
  final VoidCallback? onOpenGroups;
  final VoidCallback? onOpenManualMap;
  final int detailRequest;
  final int collectionRequest;

  static Future<Trip?> createTrip(BuildContext context, AppState state) async {
    if (state.isMutating || state.isPlanning) return null;
    if (state.activeProfile == null) {
      final profile = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (_) => const ProfileEditor(),
      );
      if (profile == null || !context.mounted) return null;
      await state.createProfile(profile);
    }
    if (!context.mounted) return null;
    final data = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => const TripEditor()),
    );
    if (data == null || !context.mounted) return null;
    final previous = state.activeTrip?.id;
    await state.createTrip(data);
    final created = state.activeTrip;
    return created?.id == previous ? null : created;
  }

  @override
  State<TripsScreen> createState() => _TripsScreenState();
}

class _TripsScreenState extends State<TripsScreen> {
  bool _detail = false;

  @override
  void didUpdateWidget(covariant TripsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.detailRequest != widget.detailRequest) _detail = true;
    if (oldWidget.collectionRequest != widget.collectionRequest) {
      _detail = false;
    }
  }

  Future<void> _create() async {
    try {
      final created = await TripsScreen.createTrip(context, widget.state);
      if (mounted && created != null) setState(() => _detail = true);
    } catch (_) {
      _error();
    }
  }

  Future<void> _open(Trip trip) async {
    try {
      await widget.state.selectTrip(trip);
      if (mounted) setState(() => _detail = true);
    } catch (_) {
      _error();
    }
  }

  void _error() {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          widget.state.errorMessage ?? 'Không thể mở chuyến đi. Hãy thử lại.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    if (_detail && state.activeTrip != null) {
      return PopScope(
        canPop: false,
        onPopInvokedWithResult: (didPop, _) {
          if (!didPop) setState(() => _detail = false);
        },
        child: ItineraryScreen(
          state: state,
          onOpenMap: widget.onOpenMap,
          onOpenManualMap: widget.onOpenManualMap,
          onBack: () => setState(() => _detail = false),
        ),
      );
    }
    return Column(
      children: [
        const AppHeader(section: 'Davel Trace'),
        Expanded(
          child: RefreshIndicator(
            onRefresh: state.refresh,
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                  sliver: SliverToBoxAdapter(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Chuyến đi của bạn',
                          style: Theme.of(context).textTheme.displaySmall,
                        ),
                        if (state.isDemoManagement) ...[
                          const SizedBox(height: 10),
                          const Text(
                            'Bạn đang xem thử. Thay đổi chỉ lưu trên thiết bị này.',
                            key: Key('trip-demo-notice'),
                          ),
                        ],
                        if (widget.onOpenGroups != null) ...[
                          const SizedBox(height: 16),
                          _GroupEntry(onTap: widget.onOpenGroups!),
                        ],
                        if (state.trips.isNotEmpty) ...[
                          const SizedBox(height: 20),
                          Text(
                            widget.onOpenGroups == null
                                ? 'Chuyến đã lưu'
                                : 'Chuyến do bạn tạo',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                if (state.trips.isEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    sliver: SliverToBoxAdapter(
                      child: SurfaceCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.onOpenGroups == null
                                  ? 'Chưa có chuyến đi'
                                  : 'Bạn chưa tạo chuyến nào',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Tạo chuyến để chọn ngày đi và lên lịch khám phá.',
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverList.builder(
                    itemCount: state.trips.length,
                    itemBuilder: (context, index) {
                      final trip = state.trips[index];
                      return Padding(
                        key: ValueKey(trip.id),
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _TripCard(
                          trip: trip,
                          selected: state.activeTrip?.id == trip.id,
                          onTap: state.isMutating || state.isPlanning
                              ? null
                              : () => _open(trip),
                        ),
                      );
                    },
                  ),
                ),
                if (state.archivedTrips.isNotEmpty ||
                    state.deletedTrips.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 10,
                    ),
                    sliver: SliverToBoxAdapter(
                      child: TripArchiveButton(state: state),
                    ),
                  ),
                const SliverToBoxAdapter(child: SizedBox(height: 12)),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
          child: SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              key: const Key('create-trip-button'),
              onPressed: state.isMutating || state.isPlanning ? null : _create,
              icon: const Icon(Icons.add),
              label: const Text('Tạo chuyến đi'),
            ),
          ),
        ),
      ],
    );
  }
}

class _GroupEntry extends StatelessWidget {
  const _GroupEntry({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: AppColors.sand,
    borderRadius: BorderRadius.circular(16),
    clipBehavior: Clip.antiAlias,
    child: ListTile(
      key: const Key('open-group-trips'),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      leading: const Icon(Icons.group_outlined, color: AppColors.primary),
      title: Text(
        'Chuyến đi nhóm',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      subtitle: const Text('Cùng chọn lịch, trò chuyện và chia chi phí'),
      trailing: const Icon(
        Icons.arrow_forward_rounded,
        color: AppColors.primary,
      ),
      onTap: onTap,
    ),
  );
}

class _TripCard extends StatelessWidget {
  const _TripCard({
    required this.trip,
    required this.selected,
    required this.onTap,
  });
  final Trip trip;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: selected ? AppColors.sand : AppColors.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: AppColors.outline),
    ),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      key: Key('open-trip-${trip.id}'),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    trip.title,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                const Icon(Icons.chevron_right_rounded),
              ],
            ),
            const SizedBox(height: 6),
            Text('${_date(trip.startDate)} đến ${_date(trip.endDate)}'),
            const SizedBox(height: 4),
            Text(
              '${trip.travelers} người · ${moneyVnd(trip.budgetVnd)}${selected ? ' · Đang xem' : ''}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    ),
  );

  String _date(DateTime date) => '${date.day}/${date.month}/${date.year}';
}
