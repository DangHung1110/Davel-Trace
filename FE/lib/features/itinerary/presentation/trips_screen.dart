import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/coastal_scene.dart';
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
    this.detailRequest = 0,
    this.collectionRequest = 0,
  });
  final AppState state;
  final VoidCallback onOpenMap;
  final int detailRequest;
  final int collectionRequest;

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
    final state = widget.state;
    if (state.activeProfile == null) {
      final data = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (_) => const ProfileEditor(),
      );
      if (data == null || !mounted) return;
      try {
        await state.createProfile(data);
      } catch (_) {
        _error();
        return;
      }
    }
    if (!mounted) return;
    final previous = state.activeTrip?.id;
    await ItineraryScreen(
      state: state,
      onOpenMap: widget.onOpenMap,
    ).openTripEditor(context);
    if (mounted &&
        state.activeTrip != null &&
        state.activeTrip!.id != previous) {
      setState(() => _detail = true);
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
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              children: [
                Text(
                  'Hành trình của bạn',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Một nơi cho lịch trình, bản đồ và những khoản chi.',
                ),
                const SizedBox(height: 20),
                FilledButton.icon(
                  key: const Key('create-trip-button'),
                  onPressed: state.isMutating || state.isPlanning
                      ? null
                      : _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Tạo chuyến đi'),
                ),
                const SizedBox(height: 16),
                if (state.isDemoManagement)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 16),
                    child: Text(
                      'Bản demo · Thay đổi chưa được lưu vào tài khoản.',
                      key: Key('trip-demo-notice'),
                      style: TextStyle(fontSize: 12),
                    ),
                  ),
                if (state.trips.isEmpty)
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.luggage_outlined,
                          size: 36,
                          color: AppColors.primary,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Chưa có chuyến đi',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Bắt đầu với ngày đi, ngân sách và những nơi bạn muốn khám phá.',
                        ),
                      ],
                    ),
                  ),
                for (final trip in state.trips) ...[
                  _TripCard(
                    trip: trip,
                    selected: state.activeTrip?.id == trip.id,
                    onTap: state.isMutating || state.isPlanning
                        ? null
                        : () => _open(trip),
                  ),
                  const SizedBox(height: 12),
                ],
                if (state.archivedTrips.isNotEmpty ||
                    state.deletedTrips.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  TripArchiveButton(state: state),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
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
    color: AppColors.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(24),
      side: BorderSide(
        color: selected ? AppColors.surfaceHigh : AppColors.outline,
      ),
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
            if (selected) ...[
              const CoastalScene(
                child: Align(
                  alignment: Alignment.topLeft,
                  child: Padding(
                    padding: EdgeInsets.all(14),
                    child: Text(
                      'DÀNH THỜI GIAN CHO NHỮNG ĐIỀU BẠN THÍCH',
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w600,
                        letterSpacing: .6,
                        color: AppColors.primaryDark,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
            ],
            Row(
              children: [
                const Icon(Icons.luggage_outlined, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    selected ? 'Đang xem' : 'Đà Nẵng',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.primary,
                    ),
                  ),
                ),
                const Icon(Icons.chevron_right_rounded),
              ],
            ),
            const SizedBox(height: 12),
            Text(trip.title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text('${_date(trip.startDate)} đến ${_date(trip.endDate)}'),
            const SizedBox(height: 4),
            Text(
              '${trip.travelers} người · ${moneyVnd(trip.budgetVnd)}',
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: AppColors.surfaceLow,
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Row(
                children: [
                  Expanded(
                    child: Text(
                      'Mở lịch trình',
                      style: TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  Icon(
                    Icons.arrow_forward_rounded,
                    size: 18,
                    color: AppColors.primary,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );

  String _date(DateTime date) => '${date.day}/${date.month}/${date.year}';
}
