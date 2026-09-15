import 'package:flutter/material.dart';

import '../../expenses/presentation/expenses_screen.dart';
import '../../itinerary/domain/demo_trip.dart';
import '../../itinerary/presentation/itinerary_screen.dart';
import '../../map/presentation/map_screen.dart';

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
      body: SafeArea(
        child: IndexedStack(
          index: _selectedIndex,
          children: [
            ItineraryScreen(onPlanGenerated: _showGeneratedPlan),
            MapScreen(stops: _routeStops, planRevision: _planRevision),
            const ExpensesScreen(),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) =>
            setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            selectedIcon: Icon(Icons.auto_awesome),
            label: 'Lịch trình',
          ),
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: 'Bản đồ',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined),
            selectedIcon: Icon(Icons.account_balance_wallet),
            label: 'Chi tiêu',
          ),
        ],
      ),
    );
  }
}
