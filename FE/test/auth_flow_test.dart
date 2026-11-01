import 'package:davel_trace/core/auth/auth_session_store.dart';
import 'package:davel_trace/features/auth/application/auth_controller.dart';
import 'package:davel_trace/features/auth/presentation/auth_gate.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'auth_controller_test.dart';

void main() {
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
