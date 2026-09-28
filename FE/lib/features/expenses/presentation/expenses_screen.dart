import 'package:flutter/material.dart';

import '../../../shared/widgets/app_header.dart';
import '../../../theme/app_theme.dart';

class ExpensesScreen extends StatefulWidget {
  const ExpensesScreen({super.key});

  @override
  State<ExpensesScreen> createState() => _ExpensesScreenState();
}

class _ExpensesScreenState extends State<ExpensesScreen> {
  static const _budget = 4000000;
  String _selectedCategory = 'Tất cả';
  final List<_Expense> _expenses = [
    const _Expense(
      'Hải sản Bé Mặn',
      'Ăn uống',
      750000,
      Icons.restaurant_outlined,
      AppColors.amber,
    ),
    const _Expense(
      'Thuê xe máy',
      'Di chuyển',
      350000,
      Icons.two_wheeler_outlined,
      AppColors.blue,
    ),
    const _Expense(
      'Khách sạn ven sông',
      'Khách sạn',
      1800000,
      Icons.hotel_outlined,
      AppColors.success,
    ),
    const _Expense(
      'Vé & trải nghiệm',
      'Vui chơi',
      350000,
      Icons.local_activity_outlined,
      AppColors.coral,
    ),
  ];

  int get _spent => _expenses.fold(0, (sum, expense) => sum + expense.amount);
  Iterable<(int, _Expense)> get _visibleExpenses => _expenses.indexed.where(
    (entry) =>
        _selectedCategory == 'Tất cả' || entry.$2.category == _selectedCategory,
  );

  Future<void> _addExpense() async {
    final expense = await showModalBottomSheet<_Expense>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      useSafeArea: true,
      builder: (context) => const _AddExpenseSheet(),
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
      if (index > 0 && (digits.length - index) % 3 == 0) buffer.write('.');
      buffer.write(digits[index]);
    }
    return '${buffer.toString()} ₫';
  }

  @override
  Widget build(BuildContext context) {
    final spentPercent = (_spent / _budget).clamp(0.0, 1.0);
    return ColoredBox(
      color: AppColors.canvas,
      child: Column(
        children: [
          const AppHeader(compact: true, section: 'Chi tiêu'),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Quản lý chi tiêu',
                              style: Theme.of(context).textTheme.headlineMedium,
                            ),
                            const SizedBox(height: 3),
                            const Text(
                              'Theo dõi ngân sách cho chuyến đi Đà Nẵng.',
                            ),
                          ],
                        ),
                      ),
                      IconButton.filledTonal(
                        tooltip: 'Chia sẻ',
                        onPressed: () => ScaffoldMessenger.of(context)
                            .showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Bản tổng hợp đã sẵn sàng để chia sẻ.',
                                ),
                              ),
                            ),
                        icon: const Icon(Icons.ios_share_rounded, size: 17),
                      ),
                      const SizedBox(width: 4),
                      const _CurrencyPill(),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [AppColors.primary, Color(0xFF315B52)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(22),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x33173C35),
                          blurRadius: 20,
                          offset: Offset(0, 9),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Text(
                              'Ngân sách còn lại',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Spacer(),
                            Icon(
                              Icons.account_balance_wallet_outlined,
                              color: Colors.white,
                              size: 17,
                            ),
                          ],
                        ),
                        const SizedBox(height: 5),
                        Text(
                          _money(_budget - _spent),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 25,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            const Text(
                              'Tiến độ ngân sách',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 8,
                              ),
                            ),
                            const Spacer(),
                            Text(
                              'Đã dùng ${(spentPercent * 100).round()}%',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 8,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 5),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: LinearProgressIndicator(
                            minHeight: 6,
                            value: spentPercent,
                            backgroundColor: Colors.white24,
                            valueColor: const AlwaysStoppedAnimation(
                              AppColors.accent,
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: _BudgetMetric(
                                label: 'Tổng ngân sách',
                                value: _money(_budget),
                              ),
                            ),
                            Container(
                              width: 1,
                              height: 30,
                              color: Colors.white24,
                            ),
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.only(left: 14),
                                child: _BudgetMetric(
                                  label: 'Đã chi',
                                  value: _money(_spent),
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Đã chi ${_money(_spent)}',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 8,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'Danh mục',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children:
                          {
                            'Tất cả': Icons.apps_rounded,
                            'Ăn uống': Icons.restaurant_outlined,
                            'Di chuyển': Icons.two_wheeler_outlined,
                            'Vui chơi': Icons.local_activity_outlined,
                          }.entries.map((entry) {
                            final selected = _selectedCategory == entry.key;
                            return Padding(
                              padding: const EdgeInsets.only(right: 7),
                              child: ChoiceChip(
                                selected: selected,
                                showCheckmark: false,
                                avatar: Icon(
                                  entry.value,
                                  size: 13,
                                  color: selected
                                      ? Colors.white
                                      : AppColors.blue,
                                ),
                                label: Text(entry.key),
                                selectedColor: AppColors.blue,
                                backgroundColor: Colors.white,
                                labelStyle: TextStyle(
                                  color: selected
                                      ? Colors.white
                                      : AppColors.navy,
                                ),
                                side: BorderSide(
                                  color: selected
                                      ? AppColors.blue
                                      : AppColors.outline,
                                ),
                                onSelected: (_) => setState(
                                  () => _selectedCategory = entry.key,
                                ),
                              ),
                            );
                          }).toList(),
                    ),
                  ),
                  const SizedBox(height: 13),
                  const _SavingBanner(),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Khoản chi gần đây',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      const Text(
                        'Hôm nay, 24 Th10',
                        style: TextStyle(fontSize: 8, color: AppColors.muted),
                      ),
                    ],
                  ),
                  const SizedBox(height: 9),
                  ..._visibleExpenses.map(
                    (entry) => _ExpenseTile(
                      expense: entry.$2,
                      money: _money,
                      onDelete: () => _removeExpense(entry.$1),
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 6, 14, 12),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: const Key('add-expense-button'),
                onPressed: _addExpense,
                icon: const Icon(Icons.add_rounded, size: 17),
                label: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 10),
                  child: Text('Thêm khoản chi'),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CurrencyPill extends StatelessWidget {
  const _CurrencyPill();
  @override
  Widget build(BuildContext context) => Container(
    height: 40,
    padding: const EdgeInsets.symmetric(horizontal: 9),
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: AppColors.outline),
    ),
    child: const Text(
      '₫ VND',
      style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800),
    ),
  );
}

class _BudgetMetric extends StatelessWidget {
  const _BudgetMetric({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: Colors.white70, fontSize: 8)),
      const SizedBox(height: 2),
      Text(
        value,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    ],
  );
}

class _SavingBanner extends StatelessWidget {
  const _SavingBanner();
  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(16),
    child: SizedBox(
      height: 78,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            'https://lh3.googleusercontent.com/aida-public/AB6AXuDCKWrRty_e3JfQkK0rha6i5x4PeK_7AXjTDFRi2ZatSEBr_3mPbTvB1Pe3ADtnW9Bp5BptBZjF6bUQZIodFnwLl4ffSvNNfY8Nrn1SHja25Wd5pSWobvxFBhjSlXJ5kFBGy_dlZxE_ijqmu4I6-_AJYKwZT1iF7Z9WPoalwaXK06RahHjFwKHhzMsr2HZzB0_p71G4xt7rK0A_sRDFNrpfDw1IvuPhq7QYEqbMX3wrpE7AqZfLc-ZX',
            fit: BoxFit.cover,
            errorBuilder: (_, error, stackTrace) =>
                const ColoredBox(color: Color(0xFF113B55)),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xD9002437), Color(0x22002437)],
              ),
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  'MẸO TIẾT KIỆM',
                  style: TextStyle(
                    color: Color(0xFF70F0C6),
                    fontSize: 8,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                SizedBox(height: 3),
                Text(
                  'Ăn đêm tại Chợ Helio tiết\nkiệm hơn 30%',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _ExpenseTile extends StatelessWidget {
  const _ExpenseTile({
    required this.expense,
    required this.money,
    required this.onDelete,
  });
  final _Expense expense;
  final String Function(int) money;
  final VoidCallback onDelete;
  @override
  Widget build(BuildContext context) => Dismissible(
    key: ValueKey('${expense.title}-${expense.amount}'),
    direction: DismissDirection.endToStart,
    onDismissed: (_) => onDelete(),
    background: Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: 18),
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: AppColors.coral,
        borderRadius: BorderRadius.circular(15),
      ),
      child: const Icon(Icons.delete_outline, color: Colors.white),
    ),
    child: Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: AppColors.outline),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: expense.color.withValues(alpha: .13),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(expense.icon, color: expense.color, size: 19),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  expense.title,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '${expense.category} · Hôm nay',
                  style: const TextStyle(fontSize: 8, color: AppColors.muted),
                ),
              ],
            ),
          ),
          Text(
            '- ${money(expense.amount)}',
            style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800),
          ),
          IconButton(
            tooltip: 'Xóa',
            onPressed: onDelete,
            visualDensity: VisualDensity.compact,
            icon: const Icon(
              Icons.delete_outline,
              size: 15,
              color: AppColors.muted,
            ),
          ),
        ],
      ),
    ),
  );
}

class _AddExpenseSheet extends StatefulWidget {
  const _AddExpenseSheet();
  @override
  State<_AddExpenseSheet> createState() => _AddExpenseSheetState();
}

class _AddExpenseSheetState extends State<_AddExpenseSheet> {
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
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.fromLTRB(
      18,
      0,
      18,
      MediaQuery.viewInsetsOf(context).bottom + 20,
    ),
    child: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Thêm khoản chi', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          TextField(
            key: const Key('expense-title-field'),
            controller: _titleController,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Nội dung',
              hintText: 'Ví dụ: Cà phê ven biển',
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _category,
            decoration: const InputDecoration(labelText: 'Danh mục'),
            items: ['Ăn uống', 'Di chuyển', 'Vui chơi', 'Khách sạn']
                .map(
                  (value) => DropdownMenuItem(value: value, child: Text(value)),
                )
                .toList(),
            onChanged: (value) {
              if (value != null) setState(() => _category = value);
            },
          ),
          const SizedBox(height: 10),
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
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Hủy'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton(
                  key: const Key('save-expense-button'),
                  onPressed: _submit,
                  child: const Text('Thêm'),
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class _Expense {
  const _Expense(this.title, this.category, this.amount, this.icon, this.color);
  factory _Expense.fromCategory(String title, String category, int amount) =>
      switch (category) {
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
  final String title;
  final String category;
  final int amount;
  final IconData icon;
  final Color color;
}
