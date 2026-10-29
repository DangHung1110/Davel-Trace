import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../theme/app_theme.dart';
import '../../expenses/presentation/expenses_screen.dart';
import '../../itinerary/presentation/itinerary_screen.dart';
import '../../map/presentation/map_screen.dart';
import '../../map/presentation/map_stop.dart';
import '../../profile/presentation/profile_screen.dart';

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
        .map(MapStop.fromActivity)
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
