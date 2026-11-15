import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../theme/app_theme.dart';
import '../../expenses/expenses.dart';
import '../../itinerary/itinerary.dart';
import '../../map/map.dart';
import '../../profile/profile.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key, required this.state});
  final AppState state;

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _selectedIndex = 0;
  final Set<int> _visited = {0};

  void _select(int index) {
    setState(() {
      _selectedIndex = index;
      _visited.add(index);
    });
    if (index == 1) widget.state.loadRoutePreview();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final stops = (state.itinerary?.activities ?? const [])
        .where((activity) => activity.poiId != null)
        .map(
          (activity) => MapStop.fromActivity(
            activity,
            place: state.mapPlaces[activity.poiId],
          ),
        )
        .toList();
    return Scaffold(
      backgroundColor: AppColors.surfaceHigh,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isDesktopPreview = constraints.maxWidth > 600;
          final appWidth = isDesktopPreview ? 390.0 : constraints.maxWidth;
          final appHeight = isDesktopPreview && constraints.maxHeight > 876
              ? 844.0
              : constraints.maxHeight;
          return SafeArea(
            child: Center(
              child: SizedBox(
                key: const Key('desktop-phone-frame'),
                width: appWidth,
                height: appHeight,
                child: Material(
                  color: AppColors.canvas,
                  elevation: isDesktopPreview ? 14 : 0,
                  clipBehavior: Clip.antiAlias,
                  borderRadius: isDesktopPreview
                      ? BorderRadius.circular(32)
                      : BorderRadius.zero,
                  child: Column(
                    children: [
                      if (state.isMutating)
                        const LinearProgressIndicator(minHeight: 2),
                      if (state.syncStatus case final sync?
                          when sync.usingStaleCache ||
                              sync.pendingCount > 0 ||
                              sync.conflictCount > 0 ||
                              sync.failedCount > 0)
                        OfflineSyncBanner(state: state),
                      if (state.errorMessage != null &&
                          state.profiles.isNotEmpty)
                        _StaleDataBanner(
                          message: state.errorMessage!,
                          onRetry: state.refresh,
                        ),
                      Expanded(
                        child: IndexedStack(
                          index: _selectedIndex,
                          children: [
                            ItineraryScreen(
                              state: state,
                              onOpenMap: () => _select(1),
                            ),
                            if (_visited.contains(1))
                              MapScreen(
                                stops: stops,
                                planRevision: state.itinerary?.version ?? 0,
                                tripTitle: state.activeTrip?.title,
                                routePreview: state.routePreview,
                                onOpenItinerary: () => _select(0),
                              )
                            else
                              const SizedBox.shrink(),
                            ExpensesScreen(state: state),
                            ProfileScreen(
                              state: state,
                              onReady: () => _select(0),
                            ),
                          ],
                        ),
                      ),
                      NavigationBar(
                        selectedIndex: _selectedIndex,
                        onDestinationSelected: _select,
                        destinations: const [
                          NavigationDestination(
                            key: Key('itinerary-tab'),
                            icon: Icon(Icons.route_outlined, size: 21),
                            selectedIcon: Icon(Icons.route_rounded, size: 21),
                            label: 'Lịch trình',
                          ),
                          NavigationDestination(
                            key: Key('map-tab'),
                            icon: Icon(Icons.map_outlined, size: 21),
                            selectedIcon: Icon(Icons.map_rounded, size: 21),
                            label: 'Bản đồ',
                          ),
                          NavigationDestination(
                            key: Key('expenses-tab'),
                            icon: Icon(
                              Icons.account_balance_wallet_outlined,
                              size: 21,
                            ),
                            selectedIcon: Icon(
                              Icons.account_balance_wallet_rounded,
                              size: 21,
                            ),
                            label: 'Chi tiêu',
                          ),
                          NavigationDestination(
                            key: Key('profile-tab'),
                            icon: Icon(Icons.person_outline_rounded, size: 21),
                            selectedIcon: Icon(Icons.person_rounded, size: 21),
                            label: 'Cá nhân',
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class OfflineSyncBanner extends StatelessWidget {
  const OfflineSyncBanner({super.key, required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final sync = state.syncStatus!;
    final hasConflict = sync.conflictCount > 0 || sync.failedCount > 0;
    final last = sync.lastSuccessAt?.toLocal();
    final timestamp = last == null
        ? 'chưa có lần đồng bộ thành công'
        : '${last.hour.toString().padLeft(2, '0')}:${last.minute.toString().padLeft(2, '0')} '
              '${last.day.toString().padLeft(2, '0')}/${last.month.toString().padLeft(2, '0')}';
    final title = hasConflict
        ? '${sync.conflictCount + sync.failedCount} thay đổi cần xử lý'
        : sync.pendingCount > 0
        ? '${sync.pendingCount} thay đổi đang chờ đồng bộ'
        : 'Đang xem dữ liệu ngoại tuyến';
    return Material(
      key: const Key('offline-sync-banner'),
      color: hasConflict ? const Color(0xFFFFE4E6) : const Color(0xFFE6FFFB),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 7, 8, 7),
        child: Row(
          children: [
            Icon(
              hasConflict
                  ? Icons.sync_problem_rounded
                  : Icons.cloud_off_outlined,
              color: hasConflict ? Colors.red.shade700 : AppColors.primary,
              size: 18,
            ),
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
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'Lần gần nhất: $timestamp',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 10),
                  ),
                ],
              ),
            ),
            if (hasConflict)
              TextButton(
                key: const Key('discard-offline-conflicts-button'),
                onPressed: state.isMutating
                    ? null
                    : () => unawaited(state.discardOfflineConflicts()),
                child: const Text('Dùng máy chủ'),
              )
            else
              TextButton(
                key: const Key('sync-offline-changes-button'),
                onPressed: state.isMutating
                    ? null
                    : () => unawaited(state.synchronizeOfflineChanges()),
                child: const Text('Đồng bộ'),
              ),
          ],
        ),
      ),
    );
  }
}

class _StaleDataBanner extends StatelessWidget {
  const _StaleDataBanner({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Material(
    key: const Key('stale-data-error-banner'),
    color: const Color(0xFFFFF7ED),
    child: Padding(
      padding: const EdgeInsets.fromLTRB(14, 8, 8, 8),
      child: Row(
        children: [
          const Icon(
            Icons.cloud_off_outlined,
            color: AppColors.warning,
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '$message Dữ liệu gần nhất vẫn được giữ.',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.ink,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          TextButton(
            key: const Key('retry-stale-data-button'),
            onPressed: onRetry,
            child: const Text('Thử lại'),
          ),
        ],
      ),
    ),
  );
}
