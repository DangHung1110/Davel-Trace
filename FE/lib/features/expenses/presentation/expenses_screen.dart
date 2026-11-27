import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';

class ExpensesScreen extends StatefulWidget {
  const ExpensesScreen({super.key, required this.state, this.onOpenTrips});
  final AppState state;
  final VoidCallback? onOpenTrips;

  @override
  State<ExpensesScreen> createState() => _ExpensesScreenState();
}

enum _ExpenseAction { edit, delete }

class _ExpensesScreenState extends State<ExpensesScreen> {
  String _category = 'all';
  String _date = 'all';

  Future<void> _edit({ExpenseItem? expense}) async {
    if (widget.state.activeTrip == null) return;
    final data = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => ExpenseEditor(
        expense: expense,
        initialDate: widget.state.selectedTripDate,
      ),
    );
    if (data == null || !mounted) return;
    try {
      await widget.state.saveExpense(existing: expense, data: data);
    } catch (_) {
      if (mounted) _error(widget.state.errorMessage);
    }
  }

  Future<void> _delete(ExpenseItem expense) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Xóa khoản chi?'),
        content: Text('${expense.label} · ${moneyVnd(expense.amountVnd)}'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Hủy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Xóa khoản chi'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await widget.state.deleteExpense(expense);
    } catch (_) {
      if (mounted) _error(widget.state.errorMessage);
    }
  }

  Future<void> _export() async {
    try {
      final payload = await widget.state.exportExpenses(
        date: _date == 'all' ? null : _date,
        category: _category == 'all' ? null : _category,
      );
      await Clipboard.setData(
        ClipboardData(
          text: const JsonEncoder.withIndent('  ').convert(payload),
        ),
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Đã sao chép dữ liệu chi tiêu.')),
        );
      }
    } catch (_) {
      if (mounted) _error(widget.state.errorMessage);
    }
  }

  void _error(String? message) => ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message ?? 'Không thể hoàn tất thao tác.')),
  );

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final trip = state.activeTrip;
    final summary = state.expenseSummary;
    final pendingSync =
        state.syncStatus?.usingStaleCache == true ||
        (state.syncStatus?.pendingCount ?? 0) > 0;
    final visible = state.expenses.where((expense) {
      final expenseDate =
          '${expense.spentAt.year.toString().padLeft(4, '0')}-${expense.spentAt.month.toString().padLeft(2, '0')}-${expense.spentAt.day.toString().padLeft(2, '0')}';
      return (_category == 'all' || expense.category == _category) &&
          (_date == 'all' || expenseDate == _date);
    }).toList();
    final progress = summary.budgetVnd == 0
        ? 0.0
        : (summary.spentVnd / summary.budgetVnd).clamp(0.0, 1.0);
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          AppHeader(
            compact: true,
            section: 'Chi tiêu',
            trailing: TextButton(
              onPressed: widget.onOpenTrips,
              child: const Text('Đổi chuyến'),
            ),
          ),
          Expanded(
            child: trip == null
                ? _NoTripExpense(onOpenTrips: widget.onOpenTrips)
                : ListView(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
                    children: [
                      Text(
                        'Ngân sách chuyến đi',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(trip.title),
                      const SizedBox(height: 12),
                      if (state.isDemoManagement || pendingSync) ...[
                        Text(
                          state.isDemoManagement
                              ? 'Khoản chi thử chỉ được lưu trên thiết bị trong phiên này.'
                              : 'Thay đổi chi tiêu sẽ được lưu vào tài khoản khi kết nối lại.',
                          key: const Key('expense-source-status'),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 12),
                      ],
                      SurfaceCard(
                        color: AppColors.sand,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Tổng ngân sách',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                            const SizedBox(height: 5),
                            Text(
                              moneyVnd(summary.budgetVnd),
                              style: const TextStyle(
                                color: AppColors.ink,
                                fontSize: 27,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            Text(
                              'Đã chi ${moneyVnd(summary.spentVnd)}',
                              style: const TextStyle(
                                color: AppColors.muted,
                                fontSize: 13,
                              ),
                            ),
                            const SizedBox(height: 12),
                            LinearProgressIndicator(
                              value: progress,
                              semanticsLabel: 'Ngân sách đã sử dụng',
                              minHeight: 7,
                              borderRadius: BorderRadius.circular(8),
                              backgroundColor: AppColors.surfaceHigh,
                              color: summary.alert == '100'
                                  ? AppColors.error
                                  : AppColors.primary,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      _BudgetMetrics(
                        remainingVnd: summary.remainingVnd,
                        averageVnd: summary.averageVnd,
                      ),
                      if (summary.alert != 'none') ...[
                        const SizedBox(height: 10),
                        SurfaceCard(
                          color: const Color(0xFFFFF1E3),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.notifications_active_outlined,
                                color: AppColors.warning,
                              ),
                              const SizedBox(width: 9),
                              Expanded(
                                child: Text(
                                  summary.alert == '100'
                                      ? 'Bạn đã chạm hoặc vượt ngân sách.'
                                      : 'Bạn đã dùng hơn 80% ngân sách.',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                      const SizedBox(height: 16),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(right: 7),
                              child: ChoiceChip(
                                label: const Text('Mọi ngày'),
                                selected: _date == 'all',
                                onSelected: (_) =>
                                    setState(() => _date = 'all'),
                              ),
                            ),
                            ...state.tripDates.map((date) {
                              final key =
                                  '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
                              return Padding(
                                padding: const EdgeInsets.only(right: 7),
                                child: ChoiceChip(
                                  label: Text('${date.day}/${date.month}'),
                                  selected: _date == key,
                                  onSelected: (_) =>
                                      setState(() => _date = key),
                                ),
                              );
                            }),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children:
                              {
                                'all': 'Tất cả',
                                'food': 'Ăn uống',
                                'ticket': 'Vé',
                                'transport': 'Di chuyển',
                                'accommodation': 'Lưu trú',
                                'shopping': 'Mua sắm',
                                'other': 'Khác',
                              }.entries.map((entry) {
                                return Padding(
                                  padding: const EdgeInsets.only(right: 7),
                                  child: ChoiceChip(
                                    label: Text(entry.value),
                                    selected: _category == entry.key,
                                    onSelected: (_) =>
                                        setState(() => _category = entry.key),
                                  ),
                                );
                              }).toList(),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Chi tiết khoản chi',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                          Text(
                            '${visible.length} mục',
                            style: const TextStyle(fontSize: 11),
                          ),
                          const SizedBox(width: 6),
                          IconButton(
                            key: const Key('export-expenses-button'),
                            tooltip: 'Sao chép dữ liệu chi tiêu',
                            onPressed: state.isMutating ? null : _export,
                            icon: const Icon(
                              Icons.ios_share_outlined,
                              size: 19,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (visible.isEmpty)
                        const SurfaceCard(
                          color: AppColors.softSurface,
                          child: Text('Chưa có khoản chi trong nhóm này.'),
                        )
                      else
                        ...visible.map(
                          (expense) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: SurfaceCard(
                              child: Row(
                                children: [
                                  Container(
                                    width: 40,
                                    height: 40,
                                    decoration: BoxDecoration(
                                      color: AppColors.sand,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Icon(
                                      _icon(expense.category),
                                      color: AppColors.primary,
                                      size: 20,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          expense.label,
                                          style: const TextStyle(
                                            color: AppColors.ink,
                                            fontWeight: FontWeight.w800,
                                          ),
                                        ),
                                        Text(
                                          '${_categoryLabel(expense.category)} · ${expense.spentAt.day}/${expense.spentAt.month}',
                                          style: const TextStyle(fontSize: 11),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Flexible(
                                    child: Text(
                                      moneyVnd(expense.amountVnd),
                                      textAlign: TextAlign.end,
                                      style: const TextStyle(
                                        color: AppColors.ink,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  PopupMenuButton<_ExpenseAction>(
                                    tooltip: 'Tùy chọn khoản chi',
                                    enabled: !state.isMutating,
                                    onSelected: (action) async {
                                      switch (action) {
                                        case _ExpenseAction.edit:
                                          await _edit(expense: expense);
                                        case _ExpenseAction.delete:
                                          await _delete(expense);
                                      }
                                    },
                                    itemBuilder: (context) => const [
                                      PopupMenuItem(
                                        value: _ExpenseAction.edit,
                                        child: Text('Sửa khoản chi'),
                                      ),
                                      PopupMenuItem(
                                        value: _ExpenseAction.delete,
                                        child: Text('Xóa khoản chi'),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
          ),
          if (trip != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 6, 14, 12),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  key: const Key('add-expense-button'),
                  onPressed: state.isMutating ? null : () => _edit(),
                  icon: const Icon(Icons.add_rounded),
                  label: const Text('Thêm khoản chi'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _BudgetMetrics extends StatelessWidget {
  const _BudgetMetrics({required this.remainingVnd, required this.averageVnd});

  final int remainingVnd;
  final int averageVnd;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: _BudgetMetric(
          label: 'Còn lại',
          value: moneyVnd(remainingVnd),
          tint: AppColors.sand,
          valueColor: AppColors.primary,
        ),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: _BudgetMetric(
          label: 'Chi trung bình',
          value: moneyVnd(averageVnd),
          tint: const Color(0xFFFFF1E3),
          valueColor: AppColors.secondary,
        ),
      ),
    ],
  );
}

class _BudgetMetric extends StatelessWidget {
  const _BudgetMetric({
    required this.label,
    required this.value,
    required this.tint,
    required this.valueColor,
  });

  final String label;
  final String value;
  final Color tint;
  final Color valueColor;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: tint,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10)),
        const SizedBox(height: 3),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: valueColor,
            fontSize: 14,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    ),
  );
}

class _NoTripExpense extends StatelessWidget {
  const _NoTripExpense({this.onOpenTrips});
  final VoidCallback? onOpenTrips;

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(24),
    children: [
      const Text('Chọn chuyến đi để xem chi tiêu.'),
      const SizedBox(height: 16),
      FilledButton(onPressed: onOpenTrips, child: const Text('Chọn chuyến đi')),
    ],
  );
}

class ExpenseEditor extends StatefulWidget {
  const ExpenseEditor({super.key, this.expense, this.initialDate});
  final ExpenseItem? expense;
  final DateTime? initialDate;

  @override
  State<ExpenseEditor> createState() => _ExpenseEditorState();
}

class _ExpenseEditorState extends State<ExpenseEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _label;
  late final TextEditingController _amount;
  late final TextEditingController _notes;
  late String _category;
  late DateTime _spentAt;

  @override
  void initState() {
    super.initState();
    _label = TextEditingController(text: widget.expense?.label ?? '');
    _amount = TextEditingController(text: '${widget.expense?.amountVnd ?? ''}');
    _notes = TextEditingController(text: widget.expense?.notes ?? '');
    _category = widget.expense?.category ?? 'food';
    _spentAt = widget.expense?.spentAt ?? widget.initialDate ?? DateTime.now();
  }

  @override
  void dispose() {
    _label.dispose();
    _amount.dispose();
    _notes.dispose();
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.pop(context, {
      'label': _label.text.trim(),
      'amount_vnd': int.parse(_amount.text),
      'category': _category,
      'spent_at': _spentAt.toIso8601String(),
      'notes': _notes.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      18,
      4,
      18,
      MediaQuery.viewInsetsOf(context).bottom + 18,
    ),
    child: SingleChildScrollView(
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.expense == null ? 'Thêm khoản chi' : 'Sửa khoản chi',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 14),
            TextFormField(
              key: const Key('expense-title-field'),
              controller: _label,
              decoration: const InputDecoration(labelText: 'Nội dung'),
              validator: (value) => value == null || value.trim().isEmpty
                  ? 'Nhập nội dung'
                  : null,
            ),
            const SizedBox(height: 10),
            TextFormField(
              key: const Key('expense-amount-field'),
              controller: _amount,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Số tiền (VND)'),
              validator: (value) {
                final amount = int.tryParse(value ?? '');
                return amount == null || amount <= 0
                    ? 'Nhập số tiền lớn hơn 0'
                    : null;
              },
            ),
            const SizedBox(height: 10),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.calendar_today_outlined),
              title: const Text('Ngày chi'),
              subtitle: Text(
                '${_spentAt.day}/${_spentAt.month}/${_spentAt.year}',
              ),
              trailing: const Icon(Icons.edit_calendar_outlined),
              onTap: () async {
                final picked = await showDatePicker(
                  context: context,
                  initialDate: _spentAt,
                  firstDate: DateTime(2020),
                  lastDate: DateTime(2100),
                );
                if (picked != null) {
                  setState(
                    () => _spentAt = DateTime(
                      picked.year,
                      picked.month,
                      picked.day,
                      _spentAt.hour,
                      _spentAt.minute,
                    ),
                  );
                }
              },
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              isExpanded: true,
              initialValue: _category,
              decoration: const InputDecoration(labelText: 'Nhóm chi'),
              items: const [
                DropdownMenuItem(value: 'food', child: Text('Ăn uống')),
                DropdownMenuItem(value: 'ticket', child: Text('Vé')),
                DropdownMenuItem(value: 'transport', child: Text('Di chuyển')),
                DropdownMenuItem(
                  value: 'accommodation',
                  child: Text('Lưu trú'),
                ),
                DropdownMenuItem(value: 'shopping', child: Text('Mua sắm')),
                DropdownMenuItem(value: 'other', child: Text('Khác')),
              ],
              onChanged: (value) => setState(() => _category = value!),
            ),
            const SizedBox(height: 10),
            TextFormField(
              controller: _notes,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Ghi chú'),
            ),
            const SizedBox(height: 14),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                key: const Key('save-expense-button'),
                onPressed: _save,
                child: const Text('Lưu khoản chi'),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

IconData _icon(String category) => switch (category) {
  'food' => Icons.restaurant_outlined,
  'ticket' => Icons.local_activity_outlined,
  'transport' => Icons.directions_outlined,
  'accommodation' => Icons.hotel_outlined,
  'shopping' => Icons.shopping_bag_outlined,
  _ => Icons.receipt_long_outlined,
};

String _categoryLabel(String category) => switch (category) {
  'food' => 'Ăn uống',
  'ticket' => 'Vé',
  'transport' => 'Di chuyển',
  'accommodation' => 'Lưu trú',
  'shopping' => 'Mua sắm',
  _ => 'Khác',
};
