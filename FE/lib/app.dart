import 'package:flutter/material.dart';

import 'app_state.dart';
import 'features/management/data/demo_management_repository.dart';
import 'features/management/data/management_repository.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/auth/application/auth_controller.dart';
import 'features/auth/presentation/auth_gate.dart';
import 'features/auth/data/http_auth_repository.dart';
import 'core/networking/api_client.dart';
import 'features/shell/presentation/main_shell.dart';
import 'shared/widgets/async_state_view.dart';
import 'theme/app_theme.dart';

class DavelTraceApp extends StatefulWidget {
  const DavelTraceApp({super.key, this.repository, this.authController});
  final ManagementRepository? repository;
  final AuthController? authController;

  @override
  State<DavelTraceApp> createState() => _DavelTraceAppState();
}

class _DavelTraceAppState extends State<DavelTraceApp> {
  late final AppState _state;
  AppState? _liveState;
  bool _liveStarted = false;
  AuthController? _auth;

  @override
  void initState() {
    super.initState();
    _state = AppState(widget.repository ?? DemoManagementRepository());
    _state.initialize();
    if (widget.repository == null || widget.authController != null) {
      if (widget.authController != null) {
        _auth = widget.authController;
      } else {
        final api = ApiClient();
        _auth = AuthController(repository: HttpAuthRepository(client: api));
        _liveState = AppState(HttpManagementRepository(api));
      }
      _auth!.addListener(_syncAuthenticatedState);
      _auth!.initialize();
    }
  }

  void _syncAuthenticatedState() {
    final live = _liveState;
    if (_auth?.status == AuthStatus.authenticated &&
        live != null &&
        !_liveStarted) {
      _liveStarted = true;
      live.initialize();
    } else if (_auth?.status != AuthStatus.authenticated &&
        live != null &&
        _liveStarted) {
      _liveStarted = false;
      live.clearForSignOut();
    }
  }

  @override
  void dispose() {
    _state.dispose();
    _liveState?.dispose();
    _auth?.removeListener(_syncAuthenticatedState);
    _auth?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: Listenable.merge([_state, ?_liveState]),
    builder: (context, _) => MaterialApp(
      title: 'Davel Trace',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: _auth == null
          ? _Root(state: _state)
          : AuthGate(
              controller: _auth!,
              authenticatedChild: _liveState == null
                  ? _Root(state: _state)
                  : _Root(state: _liveState!),
              child: _Root(state: _state),
            ),
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
