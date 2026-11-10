import 'dart:convert';

import 'package:davel_trace/features/management/data/offline_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final now = DateTime.utc(2026, 11, 10, 8);

  test(
    'round-trips and coalesces one resource at its first server version',
    () {
      var envelope = OfflineEnvelope.empty('account-a', now);
      envelope = envelope.queueEdit(
        PendingEdit.create(
          kind: OfflineOperationKind.updateExpense,
          resourceId: 'expense-1',
          expectedVersion: 4,
          payload: {'label': 'Bữa sáng', 'version': 4, 'password': 'drop-me'},
          now: now,
        ),
      );
      envelope = envelope.queueEdit(
        PendingEdit.create(
          kind: OfflineOperationKind.updateExpense,
          resourceId: 'expense-1',
          expectedVersion: 5,
          payload: {'amount_vnd': 90000, 'version': 5},
          now: now.add(const Duration(minutes: 1)),
        ),
      );

      final decoded = OfflineEnvelope.decode(
        jsonEncode(envelope.toJson()),
        accountId: 'account-a',
        now: now,
      );

      expect(decoded.queue, hasLength(1));
      expect(decoded.queue.single.expectedVersion, 4);
      expect(decoded.queue.single.payload['label'], 'Bữa sáng');
      expect(decoded.queue.single.payload['amount_vnd'], 90000);
      expect(decoded.queue.single.payload['version'], 4);
      expect(decoded.queue.single.payload, isNot(contains('password')));
    },
  );

  test('rejects another account, expired data, and unsupported schema', () {
    final value = jsonEncode(OfflineEnvelope.empty('account-a', now).toJson());
    expect(
      () => OfflineEnvelope.decode(value, accountId: 'account-b', now: now),
      throwsFormatException,
    );
    expect(
      () => OfflineEnvelope.decode(
        value,
        accountId: 'account-a',
        now: now.add(const Duration(days: 31)),
      ),
      throwsFormatException,
    );
    final unsupported = jsonDecode(value) as Map<String, dynamic>
      ..['schema_version'] = 2;
    expect(
      () => OfflineEnvelope.decode(
        jsonEncode(unsupported),
        accountId: 'account-a',
        now: now,
      ),
      throwsFormatException,
    );
  });

  test('rejects the 101st independent queued edit', () {
    var envelope = OfflineEnvelope.empty('account-a', now);
    for (var index = 0; index < 100; index++) {
      envelope = envelope.queueEdit(
        PendingEdit.create(
          kind: OfflineOperationKind.updateExpense,
          resourceId: 'expense-$index',
          expectedVersion: 1,
          payload: {'label': 'Item $index', 'version': 1},
          now: now,
        ),
      );
    }

    expect(
      () => envelope.queueEdit(
        PendingEdit.create(
          kind: OfflineOperationKind.updateExpense,
          resourceId: 'expense-overflow',
          expectedVersion: 1,
          payload: {'label': 'Overflow', 'version': 1},
          now: now,
        ),
      ),
      throwsA(isA<OfflineQueueFullException>()),
    );
  });
}
