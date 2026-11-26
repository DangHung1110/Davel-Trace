import 'dart:convert';

import 'package:davel_trace/core/networking/api_client.dart';
import 'package:davel_trace/features/groups/data/group_repository.dart';
import 'package:davel_trace/features/groups/presentation/group_trips_screen.dart';
import 'package:davel_trace/features/management/domain/models.dart';
import 'package:davel_trace/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _captureUi = bool.fromEnvironment('CAPTURE_UI');
const _trip = 'group-trip';
const _plan = 'shared-plan';
const _round = 'shared-round';

class _GroupFixture {
  _GroupFixture({required this.role});

  final String role;
  bool voted = false;
  bool published = false;
  String? postedText;
  String? expenseKey;
  Json? expense;
  Json? contribution;
  String? contributionKey;
  Json? joinRequest;

  Json get info => {
    'trip_id': _trip,
    'title': 'Đà Nẵng cùng gia đình',
    'start_date': '2026-12-02',
    'end_date': '2026-12-02',
    'traveler_count': 10,
    'role': role,
  };

  Json get detail => {
    ...info,
    'member_id': role == 'leader' ? 'leader' : 'member',
    'budget_vnd': 3000000,
    'members': [
      {'id': 'leader', 'display_name': 'Vân', 'role': 'leader', 'active': true},
      {'id': 'member', 'display_name': 'An', 'role': 'member', 'active': true},
    ],
    'suggestions': [
      {
        'id': 'place-idea',
        'member_id': 'member',
        'poi_id': 'cham',
        'title': 'Bảo tàng Chăm',
        'kind': 'place',
        'notes': '',
        'priority': true,
        'votes': 2,
        'support_count': 2,
      },
    ],
    'expenses': expense == null
        ? []
        : [
            {...expense!, 'id': 'expense-1', 'author_id': 'member'},
          ],
    'spent_vnd': expense?['amount_vnd'] ?? 0,
    'balance': {},
    'fund': {
      'balance_vnd':
          integerField(contribution ?? {}, 'amount_vnd') -
          (expense?['source'] == 'fund'
              ? integerField(expense!, 'amount_vnd')
              : 0),
      'contributed_vnd': integerField(contribution ?? {}, 'amount_vnd'),
      'spent_vnd': expense?['source'] == 'fund'
          ? integerField(expense!, 'amount_vnd')
          : 0,
      'demo_payment_available': true,
      'contributions': [
        if (contribution case final contribution?)
          {
            ...contribution,
            'id': 'fund-entry',
            'payer_id': contribution['member_id'],
            'author_id': contribution['member_id'],
            'kind': 'contribution',
            'label': 'Đóng quỹ',
          },
      ],
    },
  };

  Json get alternative => {
    'id': _plan,
    'rank': 1,
    'profile': 'balanced',
    'total_cost_vnd': 625000,
    'vote_count': voted ? 2 : 1,
    'activities': [
      {
        'poi_id': 'cham',
        'name': 'Bảo tàng Chăm',
        'start': '09:00',
        'end': '10:00',
        'day': 1,
      },
    ],
  };

  Json get plans => {
    'active': published ? alternative : null,
    'round': published
        ? null
        : {
            'id': _round,
            'status': 'completed',
            'alternatives': [alternative],
            'my_vote': voted ? _plan : null,
          },
  };

  ApiClient createApi() => ApiClient(
    baseUrl: 'https://groups.test',
    client: MockClient((request) async {
      final path = request.url.path;
      final method = request.method;
      if (path == '/v1/trip-groups') {
        return _response({
          'items': [info],
        });
      }
      if (path == '/v1/trip-groups/join') {
        joinRequest = jsonObject(jsonDecode(request.body));
        return _response(detail);
      }
      if (path == '/v1/trip-groups/$_trip') return _response(detail);
      if (path == '/v1/trip-groups/$_trip/plans') return _response(plans);
      if (path == '/v1/trip-groups/$_trip/plans/$_round/vote') {
        voted = jsonObject(jsonDecode(request.body))['alternative_id'] == _plan;
        return _response(plans);
      }
      if (path == '/v1/itinerary-alternatives/$_plan/accept') {
        expect(role, 'leader');
        expect(request.headers['idempotency-key'], isNotEmpty);
        published = true;
        return _response({});
      }
      if (path == '/v1/trip-groups/$_trip/invites') {
        return _response({'items': []});
      }
      if (path == '/v1/trip-groups/$_trip/chat') {
        if (method == 'POST') {
          postedText = jsonObject(jsonDecode(request.body))['text'] as String;
          return _response({
            'id': 'message',
            'member_id': 'member',
            'text': postedText,
            'created_at': '2026-12-01T07:30:00Z',
            'kind': 'message',
          });
        }
        return _response({
          'items': [
            {
              'id': 'system',
              'text': 'Có phương án mới để cả nhóm góp ý.',
              'created_at': '2026-12-01T07:00:00Z',
              'kind': 'system',
            },
          ],
          'has_more': false,
        });
      }
      if (path == '/v1/trip-groups/$_trip/expenses') {
        expenseKey = request.headers['idempotency-key'];
        expense = jsonObject(jsonDecode(request.body));
        return _response(detail);
      }
      if (path == '/v1/trip-groups/$_trip/fund/contributions') {
        contributionKey = request.headers['idempotency-key'];
        contribution = jsonObject(jsonDecode(request.body));
        return _response(detail, 201);
      }
      return _response({'error': 'UNEXPECTED_TEST_REQUEST'}, 500);
    }),
  );
}

http.Response _response(Json value, [int status = 200]) => http.Response(
  jsonEncode(value),
  status,
  headers: {'content-type': 'application/json; charset=utf-8'},
);

void _viewport(WidgetTester tester, Size size, {double scale = 1}) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

Future<Finder> _show(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  if (target.evaluate().isNotEmpty) {
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
  }
  if (target.hitTestable().evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      target.hitTestable(),
      160,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.pumpAndSettle();
  return target.hitTestable();
}

Future<void> _tap(WidgetTester tester, String key) async {
  await tester.tap(await _show(tester, key));
  await tester.pumpAndSettle();
}

Future<void> _start(WidgetTester tester, _GroupFixture fixture) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: GroupTripsScreen(
        api: fixture.createApi(),
        ownedTrips: const [],
        openPlanning: (_) async {},
      ),
    ),
  );
  await tester.pumpAndSettle();
  await _tap(tester, 'open-group-$_trip');
}

void main() {
  setUpAll(() async {
    final font = FontLoader('Be Vietnam Pro')
      ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-Regular.ttf'))
      ..addFont(rootBundle.load('assets/fonts/BeVietnamPro-SemiBold.ttf'));
    await font.load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  testWidgets('members see and vote for the same proposed schedule at 320px', (
    tester,
  ) async {
    _viewport(tester, const Size(320, 640), scale: 1.6);
    final fixture = _GroupFixture(role: 'member');
    await _start(tester, fixture);
    await _tap(tester, 'open-group-plans');
    expect(find.text('Lịch của nhóm'), findsOneWidget);
    final vote = await _show(tester, 'vote-group-alternative-$_plan');
    expect(find.text('Bình chọn · 1'), findsOneWidget);
    expect(
      find.byKey(const Key('accept-group-alternative-$_plan')),
      findsNothing,
    );
    expect(find.byKey(const Key('open-group-planner')), findsNothing);
    await tester.tap(vote);
    await tester.pumpAndSettle();
    expect(fixture.voted, isTrue);
    expect(find.text('Đã chọn · 2'), findsOneWidget);
    await _tap(tester, 'open-group-alternative-$_plan');
    expect(find.text('Bảo tàng Chăm'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('leader can publish a shared option after confirming', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final fixture = _GroupFixture(role: 'leader');
    await _start(tester, fixture);
    if (_captureUi) {
      // Capture the complete mobile surface before opening the nested screen.
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('../build/ui-review/group-overview-390.png'),
      );
    }
    await _tap(tester, 'open-group-plans');
    expect(find.byKey(const Key('open-group-planner')), findsOneWidget);
    if (_captureUi) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('../build/ui-review/group-plans-390.png'),
      );
    }
    await _tap(tester, 'accept-group-alternative-$_plan');
    expect(fixture.published, isFalse);
    await tester.tap(find.text('Chốt lịch'));
    await tester.pumpAndSettle();
    expect(fixture.published, isTrue);
    expect(find.byKey(const Key('open-group-active-plan')), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('member joins with an invitation and sees chat updates', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final fixture = _GroupFixture(role: 'member');
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: GroupTripsScreen(
          api: fixture.createApi(),
          ownedTrips: const [],
          openPlanning: (_) async {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    await _tap(tester, 'join-group-trip');
    await tester.enterText(
      find.byKey(const Key('group-invite-code')),
      'invite-test-code-23',
    );
    await _tap(tester, 'submit-group-join');
    expect(fixture.joinRequest?['code'], 'invite-test-code-23');
    await _tap(tester, 'open-group-chat');
    expect(find.text('Có phương án mới để cả nhóm góp ý.'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('group-chat-draft')),
      'Cả nhà gặp nhau lúc 9 giờ.',
    );
    await _tap(tester, 'send-group-message');
    expect(fixture.postedText, 'Cả nhà gặp nhau lúc 9 giờ.');
    expect(find.text('Cả nhà gặp nhau lúc 9 giờ.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('expense excludes an attendee who did not use the service', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final fixture = _GroupFixture(role: 'member');
    await _start(tester, fixture);
    await _tap(tester, 'open-group-expenses');
    await _tap(tester, 'add-group-expense');
    expect(find.byKey(const Key('group-expense-source')), findsNothing);
    await tester.enterText(find.byKey(const Key('group-expense-name')), 'Taxi');
    await tester.enterText(
      find.byKey(const Key('group-expense-amount')),
      '120000',
    );
    final exclude = find.widgetWithText(CheckboxListTile, 'Vân');
    await tester.ensureVisible(exclude);
    await tester.tap(exclude);
    await tester.pumpAndSettle();
    await _tap(tester, 'save-group-expense');
    expect(fixture.expense?['member_ids'], ['member']);
    expect(fixture.expense?['amount_vnd'], 120000);
    expect(fixture.expenseKey, isNotEmpty);
    expect(find.text('Taxi'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('leader records a demo contribution and spends from the fund', (
    tester,
  ) async {
    _viewport(tester, const Size(390, 844));
    final fixture = _GroupFixture(role: 'leader');
    await _start(tester, fixture);
    await _tap(tester, 'open-group-expenses');
    await _tap(tester, 'add-group-contribution');
    await tester.enterText(
      find.byKey(const Key('group-contribution-amount')),
      '300000',
    );
    await tester.enterText(
      find.byKey(const Key('group-contribution-note')),
      'Đợt đầu',
    );
    await _tap(tester, 'group-contribution-demo');
    await _tap(tester, 'save-group-contribution');
    expect(fixture.contribution, isNull);
    await tester.tap(find.text('Xác nhận mô phỏng'));
    await tester.pumpAndSettle();
    expect(fixture.contribution, {
      'member_id': 'leader',
      'amount_vnd': 300000,
      'note': 'Đợt đầu',
      'method': 'demo',
    });
    expect(fixture.contributionKey, isNotEmpty);
    expect(
      tester.widget<Text>(find.byKey(const Key('group-fund-balance'))).data,
      moneyVnd(300000),
    );

    await _tap(tester, 'view-group-contributions');
    expect(find.text('Đã góp theo từng người'), findsOneWidget);
    expect(find.textContaining('Mô phỏng · Đợt đầu'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await _tap(tester, 'add-group-expense');
    await tester.enterText(
      find.byKey(const Key('group-expense-name')),
      'Vé tham quan',
    );
    await tester.enterText(
      find.byKey(const Key('group-expense-amount')),
      '120000',
    );
    await tester.enterText(
      find.byKey(const Key('group-expense-note')),
      'Vé đã mua trực tiếp',
    );
    final exclude = find.widgetWithText(CheckboxListTile, 'An');
    await tester.ensureVisible(exclude);
    await tester.tap(exclude);
    await tester.pumpAndSettle();
    await _tap(tester, 'save-group-expense');
    expect(fixture.expense?['source'], 'fund');
    expect(fixture.expense?['note'], 'Vé đã mua trực tiếp');
    expect(fixture.expense?['member_ids'], ['leader']);
    expect(
      tester.widget<Text>(find.byKey(const Key('group-fund-balance'))).data,
      moneyVnd(180000),
    );
    expect(find.text('Vé tham quan'), findsOneWidget);
    if (_captureUi) {
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('../build/ui-review/group-fund-390.png'),
      );
    }
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
