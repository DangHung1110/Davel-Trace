import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

class AppHeader extends StatelessWidget {
  const AppHeader({super.key, this.trailing, this.compact = false});

  final Widget? trailing;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: compact ? 50 : 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      color: Colors.white,
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppColors.blue,
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Icon(
              Icons.flight_takeoff_rounded,
              color: Colors.white,
              size: 17,
            ),
          ),
          const SizedBox(width: 9),
          const Text(
            'Davel Trace',
            style: TextStyle(
              color: AppColors.deepBlue,
              fontSize: 14,
              fontWeight: FontWeight.w800,
            ),
          ),
          const Spacer(),
          trailing ??
              const CircleAvatar(
                radius: 14,
                backgroundColor: Color(0xFFE9DDCF),
                child: Icon(
                  Icons.person_rounded,
                  color: Color(0xFF695446),
                  size: 18,
                ),
              ),
        ],
      ),
    );
  }
}
