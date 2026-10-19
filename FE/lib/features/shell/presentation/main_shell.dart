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
      backgroundColor: AppColors.sand,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final appWidth = constraints.maxWidth > 600
              ? 440.0
              : constraints.maxWidth;
          return SafeArea(
            child: Center(
              child: SizedBox(
                width: appWidth,
                height: constraints.maxHeight,
                child: Material(
                  color: AppColors.canvas,
                  elevation: constraints.maxWidth > 600 ? 10 : 0,
                  clipBehavior: Clip.antiAlias,
                  borderRadius: constraints.maxWidth > 600
                      ? BorderRadius.circular(26)
                      : BorderRadius.zero,
                  child: Column(
                    children: [
                      if (state.isMutating)
                        const LinearProgressIndicator(minHeight: 2),
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
                            icon: Icon(Icons.route_outlined, size: 21),
                            selectedIcon: Icon(Icons.route_rounded, size: 21),
                            label: 'Lịch trình',
                          ),
                          NavigationDestination(
                            icon: Icon(Icons.map_outlined, size: 21),
                            selectedIcon: Icon(Icons.map_rounded, size: 21),
                            label: 'Bản đồ',
                          ),
                          NavigationDestination(
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
                            icon: Icon(Icons.person_outline_rounded, size: 21),
                            selectedIcon: Icon(Icons.person_rounded, size: 21),
                            label: 'Hồ sơ',
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
