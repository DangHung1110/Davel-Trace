import 'package:flutter/material.dart';

import '../data/group_repository.dart';
import 'group_shared.dart';

class GroupSuggestionImport extends StatefulWidget {
  const GroupSuggestionImport({super.key, required this.group});

  final GroupState group;

  @override
  State<GroupSuggestionImport> createState() => _GroupSuggestionImportState();
}

class _GroupSuggestionImportState extends State<GroupSuggestionImport> {
  final _draft = TextEditingController();
  final _selected = <int>{};
  final _choices = <int, Json>{};
  List<Json>? _items;
  List<String> _unresolved = [];
  bool _busy = false;
  String? _failure;

  Future<void> _interpret() async {
    if (_busy) return;
    final draft = _draft.text.trim();
    if (draft.isEmpty) {
      setState(() => _failure = 'Nhập điều bạn mong muốn cho chuyến đi.');
      return;
    }
    FocusScope.of(context).unfocus();
    final group = widget.group;
    setState(() {
      _busy = true;
      _failure = null;
    });
    try {
      final result = await group.repository.post(
        group.tripId,
        '/suggestions/interpret',
        {'text': draft},
      );
      if (!mounted) return;
      setState(() {
        _items = jsonObjects(result['items']);
        _unresolved = (result['unresolved'] as List? ?? const [])
            .map((value) => value.toString())
            .toList();
        _selected.clear();
        _choices.clear();
      });
    } catch (error) {
      if (mounted) {
        setState(
          () => _failure =
              'Chưa đọc được góp ý. ${groupError(error)} Bạn vẫn có thể gửi bằng cách chọn từng mục.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (_busy || _selected.isEmpty) return;
    final group = widget.group;
    final items = _items!;
    final values = <Json>[
      for (final index in _selected)
        {
          'kind': textField(items[index], 'kind'),
          'title': _choices[index]?['name'] ?? items[index]['title'],
          'poi_id': ?(_choices[index]?['poi_id'] ?? items[index]['poi_id']),
        },
    ];
    setState(() {
      _busy = true;
      _failure = null;
    });
    try {
      final detail = await group.repository.post(
        group.tripId,
        '/suggestions/bulk',
        {'items': values},
      );
      if (mounted) Navigator.pop(context, detail);
    } catch (error) {
      if (mounted) setState(() => _failure = groupError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _draft.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(
        title: Text(items == null ? 'Nhập góp ý bằng lời' : 'Kiểm tra góp ý'),
      ),
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          children: [
            if (items == null) ...[
              TextField(
                key: const Key('group-text-idea'),
                controller: _draft,
                maxLength: 1600,
                minLines: 4,
                maxLines: 7,
                enabled: !_busy,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Bạn muốn nhóm lưu ý điều gì?',
                  hintText:
                      'Ví dụ: Muốn ghé Bảo tàng Chăm và ăn món địa phương.',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Nội dung bạn nhập được gửi đến nhà cung cấp AI để đọc ý chính. Chỉ những mục bạn xác nhận mới được chia sẻ với nhóm.',
              ),
            ] else ...[
              const Text(
                'Chọn các mục muốn gửi. Nếu địa điểm có nhiều kết quả, hãy chọn đúng nơi bạn muốn.',
              ),
              const SizedBox(height: 12),
              if (items.isEmpty)
                const GroupStatus(
                  icon: Icons.info_outline,
                  text: 'Chưa tìm thấy góp ý có thể gửi. Hãy sửa nội dung hoặc nhập từng mục.',
                ),
              for (final (index, item) in items.indexed) ...[
                const Divider(height: 1),
                _resultTile(context, index, item),
              ],
              if (_unresolved.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Chưa xác định',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                for (final item in _unresolved)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(item),
                  ),
              ],
            ],
            if (_failure case final failure?)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    failure,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
      bottomNavigationBar: GroupActions(
        children: [
          FilledButton(
            key: const Key('submit-group-text-idea'),
            onPressed: _busy || (items != null && _selected.isEmpty)
                ? null
                : items == null
                ? _interpret
                : _save,
            child: Text(
              _busy
                  ? 'Đang xử lý…'
                  : items == null
                  ? 'Đọc góp ý'
                  : 'Gửi ${_selected.length} mục đã chọn',
            ),
          ),
          if (items != null)
            TextButton(
              onPressed: _busy
                  ? null
                  : () => setState(() {
                      _items = null;
                      _failure = null;
                    }),
              child: const Text('Sửa nội dung'),
            ),
        ],
      ),
    );
  }

  Widget _resultTile(BuildContext context, int index, Json item) {
    final candidates = jsonObjects(item['candidates']);
    final isPlace = item['kind'] == 'place' || item['kind'] == 'avoid';
    final chosen = _choices[index];
    final needsChoice = isPlace && item['poi_id'] == null;
    final enabled = !_busy && (!needsChoice || chosen != null);
    return Column(
      children: [
        CheckboxListTile(
          key: ValueKey('include-group-text-idea-$index'),
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: _selected.contains(index),
          title: Text(textField(item, 'title')),
          subtitle: needsChoice && candidates.isEmpty
              ? const Text('Chưa tìm thấy địa điểm phù hợp.')
              : Text(switch (item['kind']) {
                  'place' => 'Điểm muốn ghé',
                  'avoid' => 'Điểm nên tránh',
                  'food' => 'Ăn uống',
                  'accessibility' => 'Hỗ trợ di chuyển',
                  _ => 'Sở thích',
                }),
          onChanged: enabled
              ? (value) => setState(() {
                  if (value == true) {
                    _selected.add(index);
                  } else {
                    _selected.remove(index);
                  }
                })
              : null,
        ),
        if (needsChoice && candidates.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: DropdownButtonFormField<String>(
              initialValue: chosen?['poi_id'] as String?,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Chọn địa điểm'),
              items: [
                for (final candidate in candidates)
                  DropdownMenuItem(
                    value: textField(candidate, 'poi_id'),
                    child: Text(
                      [
                        textField(candidate, 'name'),
                        if (textField(candidate, 'address').isNotEmpty)
                          textField(candidate, 'address'),
                      ].join(' · '),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: _busy
                  ? null
                  : (value) {
                      if (value == null) return;
                      setState(() {
                        _choices[index] = candidates.firstWhere(
                          (entry) => entry['poi_id'] == value,
                        );
                        _selected.remove(index);
                      });
                    },
            ),
          ),
      ],
    );
  }
}
