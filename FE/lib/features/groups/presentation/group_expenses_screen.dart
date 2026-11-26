import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/observability/correlation_id.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';
import '../data/group_repository.dart';
import 'group_shared.dart';

class GroupExpensesScreen extends StatefulWidget {
  const GroupExpensesScreen({super.key, required this.group});
  final GroupState group;

  @override
  State<GroupExpensesScreen> createState() => _GroupExpensesScreenState();
}

class _GroupExpensesScreenState extends State<GroupExpensesScreen> {
  GroupState get group => widget.group;
  bool _busy = false;

  Future<void> _edit({Json? existing, bool repayment = false}) async {
    final response = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => _GroupExpenseEditor(
          group: group,
          existing: existing,
          repayment: repayment,
        ),
      ),
    );
    if (response != null && mounted) group.update(response);
  }

  Future<void> _delete(Json item) async {
    final agreed = await confirmGroupAction(
      context,
      title: item['kind'] == 'settlement'
          ? 'Bỏ ghi nhận hoàn tiền?'
          : 'Xóa khoản chi?',
      description: 'Số tiền cần hoàn giữa các thành viên sẽ được tính lại.',
      action: 'Xác nhận xóa',
    );
    if (!agreed || !mounted || _busy) return;
    setState(() => _busy = true);
    try {
      group.update(
        await group.repository.delete(group.tripId, '/expenses/${item['id']}'),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(groupError(error))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _history(Json item) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _GroupExpenseDetails(group: group, item: item),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => GroupPolling(
    onRefresh: group.refresh,
    child: ListenableBuilder(
      listenable: group,
      builder: (context, _) {
        final detail = group.detail ?? {};
        final entries = jsonObjects(detail['expenses']);
        final balance = jsonObject(detail['balance']);
        final spent = integerField(detail, 'spent_vnd');
        final budget = integerField(detail, 'budget_vnd');
        return Scaffold(
          appBar: AppBar(
            title: const Text('Chi tiêu chung'),
            actions: [
              if (group.canEdit &&
                  balance.values.any((value) => value is num && value != 0))
                PopupMenuButton<String>(
                  tooltip: 'Tùy chọn chi tiêu chung',
                  onSelected: (_) => _edit(repayment: true),
                  itemBuilder: (_) => const [
                    PopupMenuItem(
                      value: 'settlement',
                      child: Text('Ghi đã hoàn tiền'),
                    ),
                  ],
                ),
            ],
          ),
          body: SafeArea(
            bottom: false,
            child: RefreshIndicator(
              onRefresh: group.refresh,
              child: ListView.builder(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                itemCount: entries.length + 1,
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (group.failure case String failure)
                          GroupProblem(
                            message: failure,
                            onRetry: group.refresh,
                          ),
                        if (group.detail != null) ...[
                          Text(
                            'Cả nhóm đã chi',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            moneyVnd(spent),
                            style: Theme.of(context).textTheme.displaySmall,
                          ),
                          if (budget > 0) ...[
                            const SizedBox(height: 6),
                            Text('Ngân sách chuyến: ${moneyVnd(budget)}'),
                          ],
                          const SizedBox(height: 20),
                          Text(
                            'Còn phải hoàn',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 6),
                          if (balance.values.every((value) => value == 0))
                            const Text('Không còn khoản phải hoàn.')
                          else
                            for (final person in group.allMembers.where(
                              (person) =>
                                  integerField(
                                    balance,
                                    textField(person, 'id'),
                                  ) !=
                                  0,
                            ))
                              _BalanceRow(
                                group: group,
                                person: person,
                                amount: integerField(
                                  balance,
                                  textField(person, 'id'),
                                ),
                              ),
                          const SizedBox(height: 18),
                          Text(
                            'Khoản đã ghi',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: 6),
                          if (entries.isEmpty)
                            const GroupStatus(
                              icon: Icons.receipt_long_outlined,
                              text: 'Chưa có khoản chi chung. Thêm khoản chi và chọn người cùng chia.',
                            ),
                        ],
                      ],
                    );
                  }
                  final item = entries[index - 1];
                  final id = textField(item, 'id');
                  final repayment = item['kind'] == 'settlement';
                  final payer = group.name(textField(item, 'payer_id'));
                  final attendees = item['member_ids'] as List? ?? const [];
                  final canChange =
                      group.canEdit && item['author_id'] == group.memberId;
                  return Column(
                    key: ValueKey('group-expense-$id'),
                    children: [
                      const Divider(height: 1),
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          repayment
                              ? Icons.currency_exchange_outlined
                              : Icons.receipt_long_outlined,
                        ),
                        title: Text(textField(item, 'label')),
                        subtitle: Text(
                          '${moneyVnd(integerField(item, 'amount_vnd'))} · ${repayment && attendees.isNotEmpty ? '$payer hoàn cho ${group.name(attendees.first.toString())}' : '$payer đã trả · ${attendees.length} người chia'}',
                        ),
                        onTap: () => _history(item),
                        trailing: canChange
                            ? PopupMenuButton<String>(
                                tooltip: 'Tùy chọn khoản chi',
                                enabled: !_busy,
                                onSelected: (action) async {
                                  if (action == 'edit') {
                                    await _edit(existing: item);
                                  } else {
                                    await _delete(item);
                                  }
                                },
                                itemBuilder: (_) => [
                                  if (!repayment)
                                    const PopupMenuItem(
                                      value: 'edit',
                                      child: Text('Sửa khoản chi'),
                                    ),
                                  const PopupMenuItem(
                                    value: 'delete',
                                    child: Text('Xóa khoản đã ghi'),
                                  ),
                                ],
                              )
                            : const Icon(Icons.chevron_right),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
          bottomNavigationBar: !group.canEdit
              ? null
              : GroupActions(
                  children: [
                    FilledButton.icon(
                      key: const Key('add-group-expense'),
                      onPressed: _busy ? null : () => _edit(),
                      icon: const Icon(Icons.add),
                      label: const Text('Thêm khoản chi chung'),
                    ),
                  ],
                ),
        );
      },
    ),
  );
}

class _BalanceRow extends StatelessWidget {
  const _BalanceRow({
    required this.group,
    required this.person,
    required this.amount,
  });
  final GroupState group;
  final Json person;
  final int amount;

  @override
  Widget build(BuildContext context) {
    final mine = person['id'] == group.memberId;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(mine ? 'Bạn' : textField(person, 'display_name')),
      subtitle: Text(
        amount > 0
            ? 'Sẽ nhận lại ${moneyVnd(amount)}'
            : 'Cần hoàn ${moneyVnd(amount.abs())}',
      ),
      leading: Icon(
        amount > 0 ? Icons.south_west_outlined : Icons.north_east_outlined,
        color: amount > 0 ? AppColors.primary : AppColors.warning,
        size: 20,
      ),
    );
  }
}

class _GroupExpenseEditor extends StatefulWidget {
  const _GroupExpenseEditor({
    required this.group,
    this.existing,
    required this.repayment,
  });
  final GroupState group;
  final Json? existing;
  final bool repayment;

  @override
  State<_GroupExpenseEditor> createState() => _GroupExpenseEditorState();
}

class _GroupExpenseEditorState extends State<_GroupExpenseEditor> {
  GroupState get group => widget.group;
  final _form = GlobalKey<FormState>();
  final _requestId = CorrelationId.create();
  late final _label = TextEditingController(
    text: widget.repayment
        ? 'Hoàn tiền'
        : textField(widget.existing ?? {}, 'label'),
  );
  late final _amount = TextEditingController(
    text: widget.existing?['amount_vnd']?.toString() ?? '',
  );
  late final _balance = jsonObject(group.detail?['balance']);
  late final _included = <String>{
    if (!widget.repayment)
      ...((widget.existing?['member_ids'] as List?)?.map(
            (id) => id.toString(),
          ) ??
          group.members.map((person) => textField(person, 'id'))),
  };
  late String _payer =
      (widget.existing?['payer_id'] as String?) ?? group.memberId;
  String? _recipient;
  String? _failure;
  bool _busy = false;

  List<Json> get _eligible => widget.repayment
      ? group.allMembers
            .where(
              (person) => integerField(_balance, textField(person, 'id')) != 0,
            )
            .toList()
      : group.allMembers
            .where(
              (person) =>
                  person['active'] != false ||
                  _included.contains(person['id']) ||
                  person['id'] == widget.existing?['payer_id'],
            )
            .toList();

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    if (_payer.isEmpty ||
        (!widget.repayment && _included.isEmpty) ||
        (widget.repayment && (_recipient == null || _payer == _recipient))) {
      setState(
        () => _failure = widget.repayment
            ? 'Chọn người hoàn và người nhận.'
            : 'Chọn ít nhất một người cùng chia.',
      );
      return;
    }
    if (widget.repayment) {
      final accepted = await confirmGroupAction(
        context,
        title: 'Ghi nhận đã hoàn tiền?',
        description:
            '${group.name(_payer)} đã gửi ${moneyVnd(int.parse(_amount.text))} cho ${group.name(_recipient!)}.',
        action: 'Ghi đã hoàn',
      );
      if (!accepted || !mounted) return;
    }
    setState(() {
      _busy = true;
      _failure = null;
    });
    final body = {
      'kind': widget.repayment ? 'settlement' : 'expense',
      'label': _label.text.trim(),
      'payer_id': _payer,
      'member_ids': widget.repayment ? [_recipient!] : _included.toList(),
      'amount_vnd': int.parse(_amount.text),
      if (widget.existing?['version'] != null)
        'version': widget.existing!['version'],
    };
    try {
      final id = widget.existing?['id'];
      final detail = id == null
          ? await group.repository.createExpense(group.tripId, body, _requestId)
          : await group.repository.patch(group.tripId, '/expenses/$id', body);
      if (mounted) Navigator.pop(context, detail);
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
    _label.dispose();
    _amount.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final payers = _eligible
        .where(
          (member) =>
              !widget.repayment ||
              integerField(_balance, textField(member, 'id')) < 0,
        )
        .toList();
    final recipients = _eligible
        .where(
          (member) =>
              member['id'] != _payer &&
              integerField(_balance, textField(member, 'id')) > 0,
        )
        .toList();
    final title = widget.repayment
        ? 'Ghi đã hoàn tiền'
        : widget.existing == null
        ? 'Thêm khoản chi chung'
        : 'Sửa khoản chi';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.repayment) ...[
                  const Text(
                    'Chỉ ghi khoản tiền đã chuyển giữa các thành viên.',
                  ),
                  const SizedBox(height: 16),
                ] else ...[
                  TextFormField(
                    key: const Key('group-expense-name'),
                    controller: _label,
                    maxLength: 120,
                    enabled: !_busy,
                    decoration: const InputDecoration(
                      labelText: 'Tên khoản chi',
                      hintText: 'Ví dụ: Taxi đến khách sạn',
                    ),
                    validator: (value) => value == null || value.trim().isEmpty
                        ? 'Nhập tên khoản chi.'
                        : null,
                  ),
                  const SizedBox(height: 12),
                ],
                TextFormField(
                  key: const Key('group-expense-amount'),
                  controller: _amount,
                  maxLength: 11,
                  enabled: !_busy,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  decoration: const InputDecoration(
                    labelText: 'Số tiền',
                    suffixText: '₫',
                  ),
                  validator: (value) => (int.tryParse(value ?? '') ?? 0) <= 0
                      ? 'Nhập số tiền lớn hơn 0.'
                      : null,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: payers.any((person) => person['id'] == _payer)
                      ? _payer
                      : null,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: widget.repayment
                        ? 'Người đã hoàn'
                        : 'Người đã trả',
                  ),
                  items: [
                    for (final person in payers)
                      DropdownMenuItem(
                        value: textField(person, 'id'),
                        child: Text(
                          textField(person, 'display_name'),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  validator: (value) =>
                      value == null ? 'Chọn người đã trả.' : null,
                  onChanged: _busy
                      ? null
                      : (value) {
                          if (value != null) setState(() => _payer = value);
                        },
                ),
                const SizedBox(height: 16),
                if (widget.repayment)
                  DropdownButtonFormField<String>(
                    initialValue: _recipient,
                    isExpanded: true,
                    decoration: const InputDecoration(labelText: 'Người nhận'),
                    items: [
                      for (final person in recipients)
                        DropdownMenuItem(
                          value: textField(person, 'id'),
                          child: Text(
                            textField(person, 'display_name'),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    validator: (value) =>
                        value == null ? 'Chọn người nhận.' : null,
                    onChanged: _busy
                        ? null
                        : (value) => setState(() => _recipient = value),
                  )
                else ...[
                  Text(
                    'Chia đều cho',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 4),
                  for (final person in _eligible)
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      value: _included.contains(person['id']),
                      title: Text(textField(person, 'display_name')),
                      onChanged: _busy
                          ? null
                          : (selected) => setState(() {
                              final id = textField(person, 'id');
                              if (selected == true) {
                                _included.add(id);
                              } else {
                                _included.remove(id);
                              }
                            }),
                    ),
                ],
                if (_failure case String failure)
                  Text(
                    failure,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                const SizedBox(height: 16),
                FilledButton(
                  key: const Key('save-group-expense'),
                  onPressed: _busy ? null : _submit,
                  child: Text(
                    _busy
                        ? 'Đang lưu…'
                        : widget.repayment
                        ? 'Ghi đã hoàn'
                        : 'Lưu khoản chi',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _GroupExpenseDetails extends StatefulWidget {
  const _GroupExpenseDetails({required this.group, required this.item});
  final GroupState group;
  final Json item;

  @override
  State<_GroupExpenseDetails> createState() => _GroupExpenseDetailsState();
}

class _GroupExpenseDetailsState extends State<_GroupExpenseDetails> {
  late Future<Json> _history = _load();

  Future<Json> _load() => widget.group.repository.get(
    widget.group.tripId,
    '/expenses/${widget.item['id']}/history',
  );

  @override
  Widget build(BuildContext context) {
    final expense = widget.item;
    final group = widget.group;
    final portions = jsonObject(expense['split']);
    return Scaffold(
      appBar: AppBar(title: Text(textField(expense, 'label'))),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              moneyVnd(integerField(expense, 'amount_vnd')),
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 4),
            Text('${group.name(textField(expense, 'payer_id'))} đã trả'),
            const SizedBox(height: 16),
            if (expense['kind'] != 'settlement') ...[
              Text(
                'Phần của từng người',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              for (final portion in portions.entries)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(group.name(portion.key)),
                  subtitle: Text(moneyVnd((portion.value as num).round())),
                ),
              const Divider(),
            ],
            Text(
              'Lịch sử thay đổi',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            FutureBuilder(
              future: _history,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const LinearProgressIndicator();
                }
                if (snapshot.hasError) {
                  return GroupProblem(
                    message: groupError(snapshot.error!),
                    onRetry: () => setState(() => _history = _load()),
                  );
                }
                final entries = jsonObjects(snapshot.data?['items']);
                if (entries.isEmpty) return const Text('Chưa có thay đổi.');
                return Column(
                  children: [
                    for (final entry in entries)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(switch (entry['action']) {
                          'create' || 'created' => 'Đã thêm',
                          'delete' || 'deleted' => 'Đã xóa',
                          _ => 'Đã sửa',
                        }),
                        subtitle: Text(
                          groupDate(textField(entry, 'created_at')),
                        ),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
