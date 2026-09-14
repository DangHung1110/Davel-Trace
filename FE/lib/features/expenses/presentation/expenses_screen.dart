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

  void _addSampleExpense() {
    setState(() {
      _expenses.insert(
        0,
        const _Expense(
          'Cà phê ven biển',
          'Ăn uống',
          45000,
          Icons.local_cafe_outlined,
          AppColors.success,
        ),
      );
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Đã thêm khoản chi mẫu 45.000 ₫.')),
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
                onPressed: _addSampleExpense,
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
                    ListTile(
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
                      trailing: Text(
                        _money(expense.amount),
                        style: const TextStyle(fontWeight: FontWeight.w800),
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

class _Expense {
  const _Expense(this.title, this.category, this.amount, this.icon, this.color);

  final String title;
  final String category;
  final int amount;
  final IconData icon;
  final Color color;
}
