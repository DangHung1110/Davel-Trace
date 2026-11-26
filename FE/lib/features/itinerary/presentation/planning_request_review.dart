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
    this.trip,
    this.useGroupDetails = false,
  });
  final Map<String, dynamic> values;
  final ManagementRepository repository;
  final List<PlaceNameResolution> placeResolutions;
  final Trip? trip;
  final bool useGroupDetails;

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

  Map<String, String> get _savedDetails {
    final trip = widget.trip;
    return trip == null
        ? const {}
        : {
            'indicative_budget': '${trip.budgetVnd}',
            'traveler_count': '${trip.travelers}',
            'day_start': trip.dayStart.substring(0, 5),
            'day_end': trip.dayEnd.substring(0, 5),
          };
  }

  bool _showField(String key) {
    if (widget.trip == null) return true;
    final proposed = widget.values[key];
    if (proposed == null || proposed is List && proposed.isEmpty) return false;
    final saved = _savedDetails[key];
    return saved == null || !widget.useGroupDetails && '$proposed' != saved;
  }

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
      String counterpart(String other) {
        final entered = _fields[other]!.text.trim();
        return _showField(other) && entered.isNotEmpty
            ? entered
            : _savedDetails[other] ?? '';
      }

      final other = counterpart(key == 'day_start' ? 'day_end' : 'day_start');
      final start = key == 'day_start' ? text : other;
      final end = key == 'day_end' ? text : other;
      if (start.isNotEmpty && end.isNotEmpty && end.compareTo(start) <= 0) {
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
      if (!_showField(entry.key) || text.isEmpty) {
        if (widget.values.containsKey(entry.key)) result[entry.key] = null;
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
          if (widget.trip case final trip?)
            Text(
              '${trip.travelers} người · ${moneyVnd(trip.budgetVnd)} · '
              '${_savedDetails['day_start']}–${_savedDetails['day_end']} đã lưu trong chuyến',
            ),
          const SizedBox(height: 8),
          Text(
            widget.useGroupDetails
                ? 'Kiểm tra các mong muốn bên dưới. Đổi số người, ngân sách hoặc giờ đi trong Cài đặt chuyến.'
                : 'Kiểm tra mong muốn AI vừa đọc. Bạn chỉ cần sửa những mục muốn thay đổi cho lần lập lịch này.',
          ),
          const SizedBox(height: 20),
          for (final entry in _labels.entries.where(
            (entry) => _showField(entry.key),
          )) ...[
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
