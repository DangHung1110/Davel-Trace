import 'package:flutter/material.dart';

import '../../../app_state.dart';
import '../../../shared/widgets/app_header.dart';
import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';
import '../../management/domain/models.dart';

class ExpensesScreen extends StatefulWidget {
  const ExpensesScreen({super.key, required this.state});
  final AppState state;

  @override
  State<ExpensesScreen> createState() => _ExpensesScreenState();
}

class _ExpensesScreenState extends State<ExpensesScreen> {
  String _category = 'all';

  Future<void> _edit({ExpenseItem? expense}) async {
    if (widget.state.activeTrip == null) return;
    final data = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (_) => ExpenseEditor(expense: expense),
    );
    if (data == null || !mounted) return;
    try {
      await widget.state.saveExpense(existing: expense, data: data);
    } catch (_) {
      if (mounted) _error(widget.state.errorMessage);
    }
  }

  Future<void> _delete(ExpenseItem expense) async {
    try {
      await widget.state.deleteExpense(expense);
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
    final visible = state.expenses.where(
      (expense) => _category == 'all' || expense.category == _category,
    );
    final progress = summary.budgetVnd == 0
        ? 0.0
        : (summary.spentVnd / summary.budgetVnd).clamp(0.0, 1.0);
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          const AppHeader(compact: true, section: 'Chi tiêu'),
          Expanded(
            child: trip == null
                ? const _NoTripExpense()
                : ListView(
                    padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
                    children: [
                      Text(
                        'Ngân sách chuyến đi',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(trip.title),
                      const SizedBox(height: 14),
                      SurfaceCard(
                        color: AppColors.primary,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'ĐÃ CHI',
                              style: TextStyle(
                                color: Color(0xFFDDE9E4),
                                fontSize: 10,
                                fontWeight: FontWeight.w800,
                                letterSpacing: .8,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              moneyVnd(summary.spentVnd),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 27,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              'Còn ${moneyVnd(summary.remainingVnd)} trên ${moneyVnd(summary.budgetVnd)}',
                              style: const TextStyle(
                                color: Color(0xFFDDE9E4),
                                fontSize: 11,
                              ),
                            ),
                            const SizedBox(height: 12),
                            LinearProgressIndicator(
                              value: progress,
                              minHeight: 7,
                              borderRadius: BorderRadius.circular(8),
                              backgroundColor: const Color(0xFF31564F),
                              color: summary.alert == '100'
                                  ? AppColors.coral
                                  : const Color(0xFFE9CFAF),
                            ),
                          ],
                        ),
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
                          children:
                              {
                                'all': 'Tất cả',
                                'food': 'Ăn uống',
                                'ticket': 'Vé',
                                'transport': 'Di chuyển',
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
                              'Khoản chi',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                          Text(
                            '${visible.length} mục',
                            style: const TextStyle(fontSize: 11),
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
                                  Column(
                                    crossAxisAlignment: CrossAxisAlignment.end,
                                    children: [
                                      Text(
                                        moneyVnd(expense.amountVnd),
                                        style: const TextStyle(
                                          color: AppColors.ink,
                                          fontWeight: FontWeight.w800,
                                        ),
                                      ),
                                      Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          IconButton(
                                            visualDensity:
                                                VisualDensity.compact,
                                            tooltip: 'Sửa',
                                            onPressed: state.isMutating
                                                ? null
                                                : () => _edit(expense: expense),
                                            icon: const Icon(
                                              Icons.edit_outlined,
                                              size: 17,
                                            ),
                                          ),
                                          IconButton(
                                            visualDensity:
                                                VisualDensity.compact,
                                            tooltip: 'Xóa',
                                            onPressed: state.isMutating
                                                ? null
                                                : () => _delete(expense),
                                            icon: const Icon(
                                              Icons.delete_outline,
                                              size: 17,
                                            ),
                                          ),
                                        ],
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

class _NoTripExpense extends StatelessWidget {
  const _NoTripExpense();

  @override
  Widget build(BuildContext context) => const Center(
    child: Padding(
      padding: EdgeInsets.all(28),
      child: Text(
        'Hãy tạo hoặc chọn một chuyến đi ở tab Lịch trình trước khi ghi chi tiêu.',
        textAlign: TextAlign.center,
      ),
    ),
  );
}

class ExpenseEditor extends StatefulWidget {
  const ExpenseEditor({super.key, this.expense});
  final ExpenseItem? expense;

  @override
  State<ExpenseEditor> createState() => _ExpenseEditorState();
}

class _ExpenseEditorState extends State<ExpenseEditor> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _label;
  late final TextEditingController _amount;
  late final TextEditingController _notes;
  late String _category;

  @override
  void initState() {
    super.initState();
    _label = TextEditingController(text: widget.expense?.label ?? '');
    _amount = TextEditingController(text: '${widget.expense?.amountVnd ?? ''}');
    _notes = TextEditingController(text: widget.expense?.notes ?? '');
    _category = widget.expense?.category ?? 'food';
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
      'spent_at': (widget.expense?.spentAt ?? DateTime.now()).toIso8601String(),
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
                return amount == null || amount < 0
                    ? 'Nhập số tiền từ 0'
                    : null;
              },
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              initialValue: _category,
              decoration: const InputDecoration(labelText: 'Nhóm chi'),
              items: const [
                DropdownMenuItem(value: 'food', child: Text('Ăn uống')),
                DropdownMenuItem(value: 'ticket', child: Text('Vé')),
                DropdownMenuItem(value: 'transport', child: Text('Di chuyển')),
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
  _ => Icons.receipt_long_outlined,
};

String _categoryLabel(String category) => switch (category) {
  'food' => 'Ăn uống',
  'ticket' => 'Vé',
  'transport' => 'Di chuyển',
  _ => 'Khác',
};
