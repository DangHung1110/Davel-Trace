import 'package:flutter/material.dart';

import '../../management/data/management_repository.dart';
import '../../management/domain/models.dart';
import '../../planning/domain/models.dart';

/// Editable confirmation; place IDs remain data, never text the traveler must enter.
class PlanningRequestReview extends StatefulWidget {
  const PlanningRequestReview({
    super.key,
    required this.values,
    required this.repository,
    this.placeResolutions = const [],
  });
  final Map<String, dynamic> values;
  final ManagementRepository repository;
  final List<PlaceNameResolution> placeResolutions;

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
  final _choices = <int, String>{};
  final _removedResolutions = <int>{};
  String? _placeError;

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
    final places = {
      for (final entry in _places.entries) entry.key: [...entry.value],
    };
    for (var index = 0; index < widget.placeResolutions.length; index++) {
      if (_removedResolutions.contains(index)) continue;
      final selected = _choices[index];
      if (selected == null) return;
      places[widget.placeResolutions[index].constraint]!.add(selected);
    }
    if (places['must_visit']!
        .toSet()
        .intersection(places['avoid']!.toSet())
        .isNotEmpty) {
      setState(
        () =>
            _placeError = 'Một địa điểm không thể vừa muốn ghé vừa muốn tránh.',
      );
      return;
    }
    final result = <String, dynamic>{
      ...widget.values,
      for (final entry in places.entries)
        entry.key: entry.value.toSet().toList(),
    };
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

  Widget _resolutionField(int index) {
    final resolution = widget.placeResolutions[index];
    return Card(
      key: Key('place-resolution-$index'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${resolution.constraint == 'must_visit' ? 'Muốn ghé' : 'Muốn tránh'}: ${resolution.name}',
                  ),
                ),
                IconButton(
                  key: Key('remove-place-resolution-$index'),
                  tooltip: 'Bỏ yêu cầu địa điểm này',
                  onPressed: () => setState(() {
                    _removedResolutions.add(index);
                    _choices.remove(index);
                    _placeError = null;
                  }),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            if (resolution.candidates.isEmpty)
              FormField<String>(
                validator: (_) =>
                    'Bỏ yêu cầu này để tiếp tục hoặc quay lại sửa mong muốn.',
                builder: (field) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Chưa tìm thấy địa điểm đã xác minh trong dữ liệu.',
                    ),
                    if (field.hasError)
                      Text(
                        field.errorText!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                  ],
                ),
              )
            else ...[
              const Text('Có nhiều địa điểm phù hợp. Chọn đúng nơi bạn muốn.'),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                key: Key('choose-place-resolution-$index'),
                initialValue: _choices[index],
                isExpanded: true,
                itemHeight: null,
                menuMaxHeight: 360,
                decoration: const InputDecoration(labelText: 'Chọn địa điểm'),
                selectedItemBuilder: (_) => resolution.candidates
                    .map(
                      (candidate) => Text(
                        candidate.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    )
                    .toList(),
                items: resolution.candidates
                    .map(
                      (candidate) => DropdownMenuItem(
                        value: candidate.id,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(candidate.name),
                              if (candidate.description.isNotEmpty)
                                Text(
                                  candidate.description,
                                  style: const TextStyle(fontSize: 12),
                                ),
                            ],
                          ),
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() {
                  if (value != null) _choices[index] = value;
                  _placeError = null;
                }),
                validator: (value) =>
                    value == null ? 'Chọn địa điểm hoặc bỏ yêu cầu này.' : null,
              ),
              if (_choices[index] != null)
                Text(
                  resolution.candidates
                      .firstWhere(
                        (candidate) => candidate.id == _choices[index],
                      )
                      .description,
                ),
            ],
          ],
        ),
      ),
    );
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
          for (var index = 0; index < widget.placeResolutions.length; index++)
            if (!_removedResolutions.contains(index)) _resolutionField(index),
          if (_placeError != null)
            Text(
              _placeError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
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
