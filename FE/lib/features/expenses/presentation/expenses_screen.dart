import 'package:flutter/material.dart';

import '../../../shared/widgets/surface_card.dart';
import '../../../theme/app_theme.dart';

class ExpensesScreen extends StatefulWidget {
  const ExpensesScreen({super.key});

  @override
  State<ExpensesScreen> createState() => _ExpensesScreenState();
}

class _ExpensesScreenState extends State<ExpensesScreen> {
  final List<_Expense> _expenses = [
    const _Expense(
      'Mì Quảng Bà Mua',
      'Ăn uống',
      120000,
      Icons.restaurant_outlined,
      AppColors.amber,
    ),
    const _Expense(
      'Thuê xe máy',
      'Di chuyển',
      150000,
      Icons.two_wheeler_outlined,
      AppColors.blue,
    ),
    const _Expense(
      'Vé tham quan',
      'Vui chơi',
      80000,
      Icons.local_activity_outlined,
      AppColors.coral,
    ),
  ];

  int get _spent => _expenses.fold(0, (sum, expense) => sum + expense.amount);

  Future<void> _addExpense() async {
    final expense = await showDialog<_Expense>(
      context: context,
      builder: (dialogContext) => const _AddExpenseDialog(),
    );

    if (expense == null || !mounted) return;

    setState(() => _expenses.insert(0, expense));
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text('Đã thêm ${expense.title}.')));
  }

  void _removeExpense(int index) {
    final removed = _expenses[index];
    setState(() => _expenses.removeAt(index));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Đã xóa ${removed.title}.'),
        action: SnackBarAction(
          label: 'Hoàn tác',
          onPressed: () => setState(() => _expenses.insert(index, removed)),
        ),
      ),
    );
  }

  String _money(int value) {
    final digits = value.toString();
    final buffer = StringBuffer();
    for (var index = 0; index < digits.length; index++) {
      if (index > 0 && (digits.length - index) % 3 == 0) {
        buffer.write('.');
      }
      buffer.write(digits[index]);
    }
    return '${buffer.toString()} ₫';
  }

  @override
  Widget build(BuildContext context) {
    const budget = 2000000;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quản lý chi tiêu',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 6),
          const Text('Theo dõi ngân sách cho chuyến đi Đà Nẵng.'),
          const SizedBox(height: 22),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF1D5EEA), Color(0xFF6A85FF)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Ngân sách còn lại',
                  style: TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 6),
                Text(
                  _money(budget - _spent),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 18),
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: LinearProgressIndicator(
                    minHeight: 8,
                    value: _spent / budget,
                    backgroundColor: Colors.white24,
                    valueColor: const AlwaysStoppedAnimation(Colors.white),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  'Đã chi ${_money(_spent)} / ${_money(budget)}',
                  style: const TextStyle(color: Colors.white),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Khoản chi gần đây',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              FilledButton.tonalIcon(
                key: const Key('add-expense-button'),
                onPressed: _addExpense,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Thêm'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SurfaceCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: _expenses.indexed.map((entry) {
                final expense = entry.$2;
                return Column(
                  children: [
                    Dismissible(
                      key: ValueKey(
                        '${expense.title}-${expense.amount}-$entry',
                      ),
                      direction: DismissDirection.endToStart,
                      onDismissed: (_) => _removeExpense(entry.$1),
                      background: Container(
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 20),
                        color: AppColors.coral,
                        child: const Icon(
                          Icons.delete_outline,
                          color: Colors.white,
                        ),
                      ),
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 5,
                        ),
                        leading: Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: expense.color.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Icon(expense.icon, color: expense.color),
                        ),
                        title: Text(
                          expense.title,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        subtitle: Text(expense.category),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              _money(expense.amount),
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            IconButton(
                              tooltip: 'Xóa',
                              onPressed: () => _removeExpense(entry.$1),
                              icon: const Icon(Icons.close, size: 18),
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (entry.$1 != _expenses.length - 1)
                      const Divider(height: 1, indent: 76),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

class _AddExpenseDialog extends StatefulWidget {
  const _AddExpenseDialog();

  @override
  State<_AddExpenseDialog> createState() => _AddExpenseDialogState();
}

class _AddExpenseDialogState extends State<_AddExpenseDialog> {
  final _titleController = TextEditingController();
  final _amountController = TextEditingController();
  String _category = 'Ăn uống';

  @override
  void dispose() {
    _titleController.dispose();
    _amountController.dispose();
    super.dispose();
  }

  void _submit() {
    final title = _titleController.text.trim();
    final amount = int.tryParse(
      _amountController.text.replaceAll(RegExp(r'[^0-9]'), ''),
    );
    if (title.isEmpty || amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Nhập nội dung và số tiền hợp lệ.')),
      );
      return;
    }
    Navigator.pop(context, _Expense.fromCategory(title, _category, amount));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Thêm khoản chi'),
      content: SingleChildScrollView(
        child: SizedBox(
          width: 360,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                key: const Key('expense-title-field'),
                controller: _titleController,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Nội dung',
                  hintText: 'Ví dụ: Cà phê ven biển',
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _category,
                decoration: const InputDecoration(labelText: 'Danh mục'),
                items: ['Ăn uống', 'Di chuyển', 'Vui chơi', 'Khách sạn']
                    .map(
                      (value) =>
                          DropdownMenuItem(value: value, child: Text(value)),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) setState(() => _category = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('expense-amount-field'),
                controller: _amountController,
                keyboardType: TextInputType.number,
                onSubmitted: (_) => _submit(),
                decoration: const InputDecoration(
                  labelText: 'Số tiền',
                  suffixText: '₫',
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Hủy'),
        ),
        FilledButton(
          key: const Key('save-expense-button'),
          onPressed: _submit,
          child: const Text('Thêm'),
        ),
      ],
    );
  }
}

class _Expense {
  const _Expense(this.title, this.category, this.amount, this.icon, this.color);

  factory _Expense.fromCategory(String title, String category, int amount) {
    return switch (category) {
      'Di chuyển' => _Expense(
        title,
        category,
        amount,
        Icons.two_wheeler_outlined,
        AppColors.blue,
      ),
      'Vui chơi' => _Expense(
        title,
        category,
        amount,
        Icons.local_activity_outlined,
        AppColors.coral,
      ),
      'Khách sạn' => _Expense(
        title,
        category,
        amount,
        Icons.hotel_outlined,
        AppColors.success,
      ),
      _ => _Expense(
        title,
        category,
        amount,
        Icons.restaurant_outlined,
        AppColors.amber,
      ),
    };
  }

  final String title;
  final String category;
  final int amount;
  final IconData icon;
  final Color color;
}
