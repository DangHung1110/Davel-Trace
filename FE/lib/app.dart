import 'package:flutter/material.dart';

import 'app_state.dart';
import 'features/management/data/demo_management_repository.dart';
import 'features/management/data/management_repository.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/shell/presentation/main_shell.dart';
import 'shared/widgets/async_state_view.dart';
import 'theme/app_theme.dart';

class DavelTraceApp extends StatefulWidget {
  const DavelTraceApp({super.key, this.repository});
  final ManagementRepository? repository;

  @override
  State<DavelTraceApp> createState() => _DavelTraceAppState();
}

class _DavelTraceAppState extends State<DavelTraceApp> {
  late final AppState _state;

  @override
  void initState() {
    super.initState();
    _state = AppState(widget.repository ?? DemoManagementRepository());
    _state.initialize();
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _state,
    builder: (context, _) => MaterialApp(
      title: 'Davel Trace',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: _Root(state: _state),
    ),
  );
}

class _Root extends StatelessWidget {
  const _Root({required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) {
    final content = state.activeProfile == null
        ? Scaffold(body: ProfileScreen(state: state))
        : MainShell(state: state);
    return AsyncStateView(
      loading: state.isLoading,
      error: state.profiles.isEmpty ? state.errorMessage : null,
      onRetry: state.refresh,
      child: content,
    );
  }
}
