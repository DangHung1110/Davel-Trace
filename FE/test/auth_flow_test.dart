import 'package:davel_trace/core/auth/auth_session_store.dart';
import 'package:davel_trace/features/auth/application/auth_controller.dart';
import 'package:davel_trace/features/auth/presentation/auth_gate.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'auth_controller_test.dart';

void main() {
  testWidgets(
    'Google requires explicit terms and completes through the auth gate',
    (tester) async {
      final repository = FakeAuthRepository();
      var googleCalls = 0;
      final controller = AuthController(
        repository: repository,
        sessionStore: MemoryAuthSessionStore(),
        googleSignIn: () async {
          googleCalls++;
          return repository.login('demo@example.com', 'TravelDemo123');
        },
      );
      await controller.initialize();
      await tester.pumpWidget(
        MaterialApp(
          home: AuthGate(
            controller: controller,
            child: const Text('Signed in'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final button = find.widgetWithText(
        OutlinedButton,
        'Tiếp tục bằng Google',
      );
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pump();
      expect(googleCalls, 0);
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pump();
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(googleCalls, 1);
      expect(find.text('Signed in'), findsOneWidget);
    },
  );
  testWidgets('mobile auth screen fits and labels demo honestly', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AuthController(
      repository: FakeAuthRepository(),
      sessionStore: MemoryAuthSessionStore(),
    );
    await controller.initialize();
    await tester.pumpWidget(
      MaterialApp(
        home: AuthGate(controller: controller, child: const Text('Demo shell')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Davel Trace'), findsOneWidget);
    expect(find.text('Đăng nhập'), findsOneWidget);
    expect(find.text('Tiếp tục với dữ liệu demo'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Tiếp tục với dữ liệu demo'));
    await tester.pump();
    expect(find.text('Demo shell'), findsOneWidget);
  });

  testWidgets('primary auth actions remain reachable at 200% text scale', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    final controller = AuthController(
      repository: FakeAuthRepository(),
      sessionStore: MemoryAuthSessionStore(),
    );
    await controller.initialize();
    await tester.pumpWidget(
      MaterialApp(
        home: AuthGate(controller: controller, child: const Text('Demo shell')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Đăng nhập'), findsOneWidget);
    expect(find.text('Tạo tài khoản'), findsOneWidget);
    await tester.drag(find.byType(ListView), const Offset(0, -700));
    await tester.pumpAndSettle();
    expect(find.text('Quên mật khẩu?'), findsOneWidget);
    expect(find.text('Khôi phục tài khoản đang chờ xóa'), findsOneWidget);
    expect(find.text('Tiếp tục với dữ liệu demo'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
