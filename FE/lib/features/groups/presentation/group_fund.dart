import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/observability/correlation_id.dart';
import '../../management/domain/models.dart';
import '../data/group_repository.dart';
import 'group_shared.dart';

class GroupFundSummary extends StatelessWidget {
  const GroupFundSummary({super.key, required this.fund, required this.onView});

  final Json fund;
  final VoidCallback onView;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Số dư quỹ chung', style: theme.textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(
            moneyVnd(integerField(fund, 'balance_vnd')),
            key: const Key('group-fund-balance'),
            style: theme.textTheme.displaySmall,
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 18,
            runSpacing: 8,
            children: [
              _FundMetric('Đã góp', integerField(fund, 'contributed_vnd')),
              _FundMetric('Đã chi từ quỹ', integerField(fund, 'spent_vnd')),
            ],
          ),
          const SizedBox(height: 4),
          TextButton.icon(
            key: const Key('view-group-contributions'),
            onPressed: onView,
            icon: const Icon(Icons.people_outline, size: 20),
            label: const Text('Xem đóng góp'),
          ),
        ],
      ),
    );
  }
}

class _FundMetric extends StatelessWidget {
  const _FundMetric(this.label, this.amount);

  final String label;
  final int amount;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: Theme.of(context).textTheme.bodySmall),
      Text(moneyVnd(amount), style: Theme.of(context).textTheme.titleMedium),
    ],
  );
}

class GroupContributionsScreen extends StatelessWidget {
  const GroupContributionsScreen({
    super.key,
    required this.group,
    required this.onDetails,
    required this.onRemove,
  });

  final GroupState group;
  final ValueChanged<Json> onDetails;
  final ValueChanged<Json> onRemove;

  @override
  Widget build(BuildContext context) => GroupPolling(
    onRefresh: group.refresh,
    child: Scaffold(
      appBar: AppBar(title: const Text('Đóng góp quỹ chung')),
      body: SafeArea(
        child: ListenableBuilder(
          listenable: group,
          builder: (context, _) {
            final fund = jsonObject(group.detail?['fund']);
            final contributions = jsonObjects(fund['contributions']);
            final amounts = <String, int>{};
            for (final entry in contributions) {
              amounts.update(
                textField(entry, 'payer_id'),
                (amount) => amount + integerField(entry, 'amount_vnd'),
                ifAbsent: () => integerField(entry, 'amount_vnd'),
              );
            }
            return RefreshIndicator(
              onRefresh: group.refresh,
              child: CustomScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 10),
                    sliver: SliverToBoxAdapter(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (group.failure case final failure?)
                            GroupProblem(
                              message: failure,
                              onRetry: group.refresh,
                            ),
                          if (group.detail != null) ...[
                            Text(
                              'Đã góp theo từng người',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            for (final person in group.allMembers)
                              if (person['active'] != false ||
                                  amounts.containsKey(person['id']))
                                ListTile(
                                  contentPadding: EdgeInsets.zero,
                                  leading: const Icon(Icons.person_outline),
                                  title: Text(
                                    textField(person, 'display_name'),
                                  ),
                                  subtitle: Text(
                                    moneyVnd(amounts[person['id']] ?? 0),
                                  ),
                                ),
                            const SizedBox(height: 12),
                            Text(
                              'Các lần đóng quỹ',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            if (contributions.isEmpty)
                              const Padding(
                                padding: EdgeInsets.only(top: 8),
                                child: Text('Chưa có ai đóng quỹ.'),
                              ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                    sliver: SliverList.builder(
                      itemCount: contributions.length,
                      itemBuilder: (context, index) {
                        final entry = contributions[index];
                        final demo = entry['method'] == 'demo';
                        final note = textField(entry, 'note');
                        return ListTile(
                          key: ValueKey('group-contribution-${entry['id']}'),
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.add_card_outlined),
                          title: Text(
                            '${group.name(textField(entry, 'payer_id'))} · '
                            '${moneyVnd(integerField(entry, 'amount_vnd'))}',
                          ),
                          subtitle: Text(
                            [
                              groupDate(textField(entry, 'created_at')),
                              if (demo) 'Mô phỏng',
                              if (note.isNotEmpty) note,
                            ].where((item) => item.isNotEmpty).join(' · '),
                          ),
                          onTap: () => onDetails(entry),
                          trailing:
                              group.canEdit &&
                                  entry['author_id'] == group.memberId
                              ? PopupMenuButton<String>(
                                  tooltip: 'Tùy chọn khoản đóng quỹ',
                                  onSelected: (_) => onRemove(entry),
                                  itemBuilder: (_) => [
                                    const PopupMenuItem<String>(
                                      value: 'remove',
                                      child: Text('Hủy ghi nhận'),
                                    ),
                                  ],
                                )
                              : const Icon(Icons.chevron_right),
                        );
                      },
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    ),
  );
}

class GroupContributionEditor extends StatefulWidget {
  const GroupContributionEditor({super.key, required this.group});

  final GroupState group;

  @override
  State<GroupContributionEditor> createState() =>
      _GroupContributionEditorState();
}

class _GroupContributionEditorState extends State<GroupContributionEditor> {
  GroupState get group => widget.group;
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _note = TextEditingController();
  late String _contributor = group.memberId;
  late String _requestId = CorrelationId.create();
  Json? _lastSubmission;
  String? _failure;
  bool _demo = false;
  bool _busy = false;

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    final amount = int.parse(_amount.text);
    if (_demo) {
      final approved = await confirmGroupAction(
        context,
        title: 'Xác nhận mô phỏng thanh toán?',
        description:
            'Ghi ${moneyVnd(amount)} vào quỹ demo bằng thanh toán mô phỏng.',
        action: 'Xác nhận mô phỏng',
      );
      if (!approved || !mounted || _busy) return;
    }
    final submission = <String, dynamic>{
      'member_id': _contributor,
      'amount_vnd': amount,
      'note': _note.text.trim(),
      'method': _demo ? 'demo' : 'manual',
    };
    final last = _lastSubmission;
    if (last != null &&
        submission.entries.any((entry) => last[entry.key] != entry.value)) {
      _requestId = CorrelationId.create();
    }
    _lastSubmission = submission;
    setState(() {
      _busy = true;
      _failure = null;
    });
    try {
      final response = await group.repository.createFundContribution(
        group.tripId,
        submission,
        _requestId,
      );
      if (mounted) Navigator.pop(context, response);
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          _failure = groupError(error);
        });
      }
    }
  }

  @override
  void dispose() {
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canDemo =
        _contributor == group.memberId &&
        jsonObject(group.detail?['fund'])['demo_payment_available'] == true;
    return Scaffold(
      appBar: AppBar(title: const Text('Đóng quỹ')),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (group.isLeader) ...[
                DropdownButtonFormField<String>(
                  initialValue: _contributor,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Người đóng'),
                  items: [
                    for (final person in group.members)
                      DropdownMenuItem(
                        value: textField(person, 'id'),
                        child: Text(
                          person['id'] == group.memberId
                              ? 'Bạn'
                              : textField(person, 'display_name'),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: _busy
                      ? null
                      : (value) => setState(() {
                          _contributor = value ?? group.memberId;
                          if (_contributor != group.memberId) _demo = false;
                        }),
                ),
                const SizedBox(height: 16),
              ],
              TextFormField(
                key: const Key('group-contribution-amount'),
                controller: _amount,
                enabled: !_busy,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                maxLength: 13,
                decoration: const InputDecoration(
                  labelText: 'Số tiền đóng',
                  suffixText: '₫',
                ),
                validator: (value) {
                  final amount = int.tryParse(value ?? '') ?? 0;
                  if (amount <= 0) return 'Nhập số tiền lớn hơn 0.';
                  if (amount > 1_000_000_000_000) {
                    return 'Số tiền tối đa là ${moneyVnd(1_000_000_000_000)}.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: const Key('group-contribution-note'),
                controller: _note,
                enabled: !_busy,
                maxLength: 500,
                maxLines: 3,
                minLines: 1,
                decoration: const InputDecoration(
                  labelText: 'Ghi chú (tùy chọn)',
                  hintText: 'Ví dụ: Đóng quỹ đợt đầu',
                ),
              ),
              if (canDemo)
                SwitchListTile(
                  key: const Key('group-contribution-demo'),
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Mô phỏng thanh toán'),
                  subtitle: const Text('Chỉ dùng với quỹ demo.'),
                  value: _demo,
                  onChanged: _busy
                      ? null
                      : (value) => setState(() => _demo = value),
                ),
              const SizedBox(height: 8),
              if (_failure case final failure?)
                GroupProblem(message: failure, onRetry: _submit)
              else if (!_demo)
                const Text('Ghi nhận số tiền đã đóng trực tiếp cho nhóm.'),
              const SizedBox(height: 16),
              FilledButton(
                key: const Key('save-group-contribution'),
                onPressed: _busy ? null : _submit,
                child: Text(
                  _busy
                      ? 'Đang ghi…'
                      : _demo
                      ? 'Tiếp tục mô phỏng'
                      : 'Ghi đã đóng quỹ',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
