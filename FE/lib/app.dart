import 'dart:async';

import 'package:flutter/material.dart';

import 'app_state.dart';
import 'features/management/data/demo_management_repository.dart';
import 'features/management/data/management_repository.dart';
import 'features/management/data/offline_management_repository.dart';
import 'features/profile/presentation/profile_screen.dart';
import 'features/auth/application/auth_controller.dart';
import 'features/auth/presentation/auth_gate.dart';
import 'features/auth/data/http_auth_repository.dart';
import 'features/planning/data/planning_repository.dart';
import 'core/networking/api_client.dart';
import 'core/offline/secure_offline_persistence.dart';
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
  ApiClient? _liveApi;
  String? _offlineAccountId;
  bool _managesLiveComposition = false;

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
        _liveApi = api;
        _managesLiveComposition = true;
        _auth = AuthController(repository: HttpAuthRepository(client: api));
      }
      _auth!.addListener(_syncAuthenticatedState);
      _auth!.initialize();
    }
  }

  void _syncAuthenticatedState() {
    final accountId = _auth?.account?.id;
    if (_auth?.status == AuthStatus.authenticated &&
        _managesLiveComposition &&
        accountId != null &&
        (_liveState == null || _offlineAccountId != accountId)) {
      _liveState?.dispose();
      final api = _liveApi!;
      final repository = OfflineManagementRepository(
        live: HttpManagementRepository(api),
        persistence: const SecureOfflinePersistence(),
        accountId: accountId,
      );
      final live = AppState(
        repository,
        planningRepository: HttpPlanningRepository(api),
      );
      _liveState = live;
      _offlineAccountId = accountId;
      _liveStarted = true;
      unawaited(live.initialize());
      if (mounted) setState(() {});
    } else if (_auth?.status != AuthStatus.authenticated &&
        _liveState != null &&
        _liveStarted) {
      final live = _liveState!;
      _liveStarted = false;
      live.clearForSignOut();
      unawaited(live.clearOfflineAccount());
      live.dispose();
      _liveState = null;
      _offlineAccountId = null;
      if (mounted) setState(() {});
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
