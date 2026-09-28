import 'package:flutter/material.dart';

import '../../expenses/presentation/expenses_screen.dart';
import '../../itinerary/domain/demo_trip.dart';
import '../../itinerary/presentation/itinerary_screen.dart';
import '../../map/presentation/map_screen.dart';
import '../../../theme/app_theme.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _selectedIndex = 0;
  int _planRevision = 0;
  List<TripStop> _routeStops = DemoTripData.defaultRoute;
  PlannerView _plannerView = PlannerView.onboarding;

  void _showGeneratedPlan(List<TripStop> stops) {
    setState(() {
      _routeStops = stops;
      _planRevision++;
      _plannerView = PlannerView.itinerary;
    });
  }

  void _showPlanner(PlannerView view) => setState(() {
    _plannerView = view;
    _selectedIndex = 0;
  });

  void _openMap() => setState(() => _selectedIndex = 1);

  void _selectSection(int index) => setState(() {
    _selectedIndex = index;
    if (index == 0 && _plannerView == PlannerView.onboarding) {
      _plannerView = PlannerView.planner;
    }
  });

  @override
  Widget build(BuildContext context) {
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
                  elevation: constraints.maxWidth > 600 ? 8 : 0,
                  child: Column(
                    children: [
                      Expanded(
                        child: IndexedStack(
                          index: _selectedIndex,
                          children: [
                            ItineraryScreen(
                              view: _plannerView,
                              onViewChanged: _showPlanner,
                              onPlanGenerated: _showGeneratedPlan,
                              onStartTrip: _openMap,
                            ),
                            MapScreen(
                              stops: _routeStops,
                              planRevision: _planRevision,
                              onOpenPoi: () => _showPlanner(PlannerView.poi),
                              onOpenReplan: () =>
                                  _showPlanner(PlannerView.replan),
                            ),
                            const ExpensesScreen(),
                          ],
                        ),
                      ),
                      if (_plannerView != PlannerView.onboarding ||
                          _selectedIndex != 0)
                        NavigationBar(
                          selectedIndex: _selectedIndex,
                          onDestinationSelected: _selectSection,
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
