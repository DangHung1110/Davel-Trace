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

  void _showGeneratedPlan(List<TripStop> stops) {
    setState(() {
      _routeStops = stops;
      _planRevision++;
      _selectedIndex = 1;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFE3E8F2),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final appWidth = constraints.maxWidth > 600
              ? 430.0
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
                              onPlanGenerated: _showGeneratedPlan,
                            ),
                            MapScreen(
                              stops: _routeStops,
                              planRevision: _planRevision,
                            ),
                            const ExpensesScreen(),
                          ],
                        ),
                      ),
                      NavigationBar(
                        selectedIndex: _selectedIndex,
                        onDestinationSelected: (index) =>
                            setState(() => _selectedIndex = index),
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
