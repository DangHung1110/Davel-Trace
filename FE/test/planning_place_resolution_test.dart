import 'package:davel_trace/features/itinerary/presentation/planning_request_review.dart';
import 'package:davel_trace/features/planning/domain/models.dart';
import 'package:davel_trace/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/fake_management_repository.dart';

const _visit = PlaceNameResolution(
  constraint: 'must_visit',
  name: 'cà phê An',
  status: 'ambiguous',
  candidates: [
    PlaceNameCandidate(
      id: 'an-1',
      name: 'Cà phê An',
      latitude: 16.1,
      longitude: 108.1,
    ),
    PlaceNameCandidate(
      id: 'an-2',
      name: 'Cà phê An',
      latitude: 16.2,
      longitude: 108.2,
    ),
  ],
);
const _avoid = PlaceNameResolution(
  constraint: 'avoid',
  name: 'quán Bình',
  status: 'ambiguous',
  candidates: [
    PlaceNameCandidate(id: 'binh-1', name: 'Quán Bình 1', address: 'Đường A'),
    PlaceNameCandidate(id: 'binh-2', name: 'Quán Bình 2', address: 'Đường B'),
  ],
);
const _missing = PlaceNameResolution(
  constraint: 'must_visit',
  name: 'Địa điểm chưa có',
  status: 'not_found',
  candidates: [],
);

Future<void> _tap(WidgetTester tester, Key key) async {
  final finder = find.byKey(key);
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      finder,
      200,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> _open(
  WidgetTester tester,
  List<PlaceNameResolution> resolutions,
  void Function(Map<String, dynamic>?) onResult, {
  Map<String, dynamic> values = const {
    'traveler_count': 2,
    'must_visit': ['dragon-bridge'],
  },
}) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = const Size(390, 844);
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            child: const Text('Review'),
            onPressed: () async => onResult(
              await Navigator.of(context).push<Map<String, dynamic>>(
                MaterialPageRoute(
                  builder: (_) => PlanningRequestReview(
                    values: values,
                    placeResolutions: resolutions,
                    repository: FakeManagementRepository(seeded: true),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Review'));
  await tester.pumpAndSettle();
}

void main() {
  test('API candidates parse separately from planner overrides; old responses still work', () {
    final proposal = AiInterpretationProposal.fromJson({
      'proposal_id': 'one',
      'hard_constraints': {
        'must_visit': ['bridge'],
      },
      'place_resolutions': [
        {
          'constraint': 'must_visit',
          'name': 'An',
          'status': 'ambiguous',
          'candidates': [
            {'poi_id': 'an-1', 'name': 'An', 'lat': 16, 'lon': 108},
          ],
        },
      ],
    });
    expect(proposal.placeResolutions.single.candidates.single.latitude, 16);
    expect(proposal.confirmedOverrides, {
      'must_visit': ['bridge'],
    });
    expect(
      AiInterpretationProposal.fromJson({'proposal_id': 'old'})
          .placeResolutions,
      isEmpty,
    );
  });

  testWidgets(
    'ambiguous places have no default and require an explicit choice or removal',
    (tester) async {
      Map<String, dynamic>? saved;
      await _open(tester, [_visit], (result) => saved = result);
      await _tap(tester, const Key('save-planning-review'));
      expect(saved, isNull);
      expect(find.text('Chọn địa điểm hoặc bỏ yêu cầu này.'), findsOneWidget);
      await _tap(tester, const Key('choose-place-resolution-0'));
      expect(find.text('16.10000, 108.10000'), findsWidgets);
      await tester.tap(find.text('16.20000, 108.20000').last);
      await tester.pumpAndSettle();
      await _tap(tester, const Key('save-planning-review'));
      expect(saved?['must_visit'], ['dragon-bridge', 'an-2']);
      expect(saved?['avoid'], isEmpty);
      expect(saved.toString(), isNot(contains('place_resolutions')));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('visit and avoid choices stay separate in confirmed payload', (
    tester,
  ) async {
    Map<String, dynamic>? saved;
    await _open(tester, [_visit, _avoid], (result) => saved = result);
    await _tap(tester, const Key('choose-place-resolution-0'));
    await tester.tap(find.text('16.20000, 108.20000').last);
    await tester.pumpAndSettle();
    await _tap(tester, const Key('choose-place-resolution-1'));
    await tester.tap(find.text('Quán Bình 1').last);
    await tester.pumpAndSettle();
    await _tap(tester, const Key('save-planning-review'));
    expect(saved?['must_visit'], ['dragon-bridge', 'an-2']);
    expect(saved?['avoid'], ['binh-1']);
  });

  testWidgets('unknown places block submit until explicitly removed', (
    tester,
  ) async {
    Map<String, dynamic>? saved;
    await _open(tester, [_missing], (result) => saved = result);
    await _tap(tester, const Key('save-planning-review'));
    expect(saved, isNull);
    expect(
      find.text('Chưa tìm thấy địa điểm đã xác minh trong dữ liệu.'),
      findsOneWidget,
    );
    await _tap(tester, const Key('remove-place-resolution-0'));
    await _tap(tester, const Key('save-planning-review'));
    expect(saved?['must_visit'], ['dragon-bridge']);
    expect(saved.toString(), isNot(contains('Địa điểm chưa có')));
  });

  testWidgets('cancel returns no planner corrections', (tester) async {
    var returned = false;
    Map<String, dynamic>? saved;
    await _open(tester, [_visit], (result) {
      returned = true;
      saved = result;
    });
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(returned, isTrue);
    expect(saved, isNull);
  });

  testWidgets('the same place cannot be both must-visit and avoid', (
    tester,
  ) async {
    Map<String, dynamic>? saved;
    await _open(
      tester,
      [],
      (result) => saved = result,
      values: const {
        'must_visit': ['dragon-bridge'],
        'avoid': ['dragon-bridge'],
      },
    );
    await _tap(tester, const Key('save-planning-review'));
    expect(saved, isNull);
    expect(
      find.text('Một địa điểm không thể vừa muốn ghé vừa muốn tránh.'),
      findsOneWidget,
    );
  });
}
