import 'package:flutter/material.dart';

import 'features/shell/presentation/main_shell.dart';
import 'theme/app_theme.dart';

class DavelTraceApp extends StatelessWidget {
  const DavelTraceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Davel Trace',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const MainShell(),
    );
  }
}
