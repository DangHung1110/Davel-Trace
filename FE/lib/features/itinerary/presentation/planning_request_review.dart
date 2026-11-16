import 'package:flutter/material.dart';

import '../../management/data/management_repository.dart';
import '../../management/domain/models.dart';

/// Editable confirmation; place IDs remain data, never text the traveler must enter.
class PlanningRequestReview extends StatefulWidget {
  const PlanningRequestReview({
    super.key,
    required this.values,
    required this.repository,
  });
  final Map<String, dynamic> values;
  final ManagementRepository repository;

  @override
  State<PlanningRequestReview> createState() => _PlanningRequestReviewState();
}

class _PlanningRequestReviewState extends State<PlanningRequestReview> {
  final _form = GlobalKey<FormState>();
  static const _labels = {
    'indicative_budget': 'Ngân sách (VND)',
    'traveler_count': 'Số người',
    'day_start': 'Bắt đầu (HH:MM)',
    'day_end': 'Kết thúc (HH:MM)',
    'accessibility': 'Nhu cầu hỗ trợ tiếp cận',
    'activities': 'Hoạt động yêu thích',
    'food_preferences': 'Sở thích ăn uống',
  };
  late final Map<String, TextEditingController> _fields;
  late final Map<String, List<String>> _places;
  final _names = <String, Future<PoiItem?>>{};

  @override
  void initState() {
    super.initState();
    _fields = {
      for (final key in _labels.keys)
        key: TextEditingController(
          text: widget.values[key] is List
              ? (widget.values[key] as List).join(', ')
              : widget.values[key]?.toString() ?? '',
        ),
    };
    _places = {
      for (final key in ['must_visit', 'avoid'])
        key: (widget.values[key] as List? ?? [])
            .map((value) => value.toString())
            .toList(),
    };
  }

  @override
  void dispose() {
    for (final field in _fields.values) {
      field.dispose();
    }
    super.dispose();
  }

  Future<PoiItem?> _name(String id) => _names.putIfAbsent(id, () async {
    try {
      return await widget.repository.getPoiDetails(id);
    } catch (_) {
      return null;
    }
  });

  String? _validate(String key, String? raw) {
    final text = raw?.trim() ?? '';
    if (text.isEmpty) return null;
    if (key == 'indicative_budget' || key == 'traveler_count') {
      final n = int.tryParse(text);
      if (n == null || n < 0) return 'Nhập số hợp lệ';
      if (key == 'traveler_count' && (n < 1 || n > 20)) {
        return 'Nhập từ 1 đến 20 người';
      }
    }
    if (key == 'day_start' || key == 'day_end') {
      if (!RegExp(r'^([01]\d|2[0-3]):[0-5]\d$').hasMatch(text)) {
        return 'Nhập giờ theo HH:MM';
      }
      if (key == 'day_end' &&
          _fields['day_start']!.text.isNotEmpty &&
          text.compareTo(_fields['day_start']!.text.trim()) <= 0) {
        return 'Giờ kết thúc phải sau giờ bắt đầu';
      }
    }
    return null;
  }

  void _save() {
    if (!_form.currentState!.validate()) return;
    final result = <String, dynamic>{...widget.values, ..._places};
    for (final entry in _fields.entries) {
      final text = entry.value.text.trim();
      if (text.isEmpty) {
        result.remove(entry.key);
        continue;
      }
      result[entry.key] = switch (entry.key) {
        'indicative_budget' || 'traveler_count' => int.parse(text),
        'day_start' || 'day_end' => text,
        _ =>
          text
              .split(',')
              .map((s) => s.trim())
              .where((s) => s.isNotEmpty)
              .toList(),
      };
    }
    Navigator.pop(context, result);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Kiểm tra yêu cầu')),
    body: Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Chỉnh lại thông tin trợ lý AI đã hiểu. Địa điểm được giữ theo lựa chọn bên dưới; bạn có thể bỏ địa điểm không đúng.',
          ),
          const SizedBox(height: 20),
          for (final entry in _labels.entries) ...[
            TextFormField(
              key: Key('review-${entry.key}'),
              controller: _fields[entry.key],
              decoration: InputDecoration(labelText: entry.value),
              validator: (value) => _validate(entry.key, value),
            ),
            const SizedBox(height: 12),
          ],
          for (final entry in _places.entries) ...[
            const SizedBox(height: 12),
            Text(
              entry.key == 'must_visit'
                  ? 'Địa điểm muốn ghé'
                  : 'Địa điểm muốn tránh',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (entry.value.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('Chưa chọn địa điểm.'),
              ),
            for (final id in entry.value)
              FutureBuilder<PoiItem?>(
                future: _name(id),
                builder: (_, snapshot) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    snapshot.data?.name ??
                        (snapshot.connectionState == ConnectionState.waiting
                            ? 'Đang tải tên địa điểm…'
                            : 'Chưa tải được tên địa điểm'),
                  ),
                  trailing: IconButton(
                    tooltip: 'Bỏ địa điểm',
                    icon: const Icon(Icons.close),
                    onPressed: () => setState(() => entry.value.remove(id)),
                  ),
                ),
              ),
          ],
          const SizedBox(height: 20),
          FilledButton(
            key: const Key('save-planning-review'),
            onPressed: _save,
            child: const Text('Xác nhận và lập lịch'),
          ),
        ],
      ),
    ),
  );
}
