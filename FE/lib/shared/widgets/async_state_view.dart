import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

class AsyncStateView extends StatelessWidget {
  const AsyncStateView({
    super.key,
    required this.loading,
    required this.child,
    this.error,
    this.onRetry,
  });

  final bool loading;
  final String? error;
  final VoidCallback? onRetry;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (error == null) return child;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.cloud_off_outlined,
                  size: 52,
                  color: AppColors.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  'Backend chưa sẵn sàng',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(error!, textAlign: TextAlign.center),
                const SizedBox(height: 18),
                FilledButton.icon(
                  key: const Key('retry-api-button'),
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Thử kết nối lại'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
